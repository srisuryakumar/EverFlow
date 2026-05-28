"""ProxyServer: FastAPI/uvicorn server for EverFlow."""

import asyncio
import threading
import time
import json
from typing import Optional

import requests as requests_lib
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from src.config.manager import ConfigManager
from src.dashboard.api import dashboard_router
from src.exceptions import AllKeysExhaustedException, MaxRetriesExceededException
from src.keys.store import KeyStore
from src.proxy.router import ProxyRouter


def _anthropic_error(error_type: str, message: str) -> dict:
    """Return an Anthropic-format error response."""
    return {
        "type": "error",
        "error": {"type": error_type, "message": message}
    }


class ProxyServer:
    """FastAPI/uvicorn server that runs in a daemon thread."""

    def __init__(self, router: ProxyRouter, key_store: KeyStore, config: ConfigManager):
        """Initialize the ProxyServer."""
        self._router = router
        self._key_store = key_store
        self._config = config
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    def _build_app(self) -> FastAPI:
        """Build and configure the FastAPI application."""
        app = FastAPI(title="EverFlow Proxy", docs_url=None, redoc_url=None)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount dashboard routes
        app.include_router(dashboard_router)

        # POST /v1/messages — main proxy endpoint
        @app.post("/v1/messages")
        async def proxy_messages(request: Request):
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    _anthropic_error("invalid_request_error", "Invalid JSON body"),
                    status_code=400
                )

            is_stream = bool(body.get("stream", False))

            try:
                if is_stream:
                    async def stream_gen():
                        try:
                            async for chunk in self._router.route_stream(body):
                                yield chunk
                        except MaxRetriesExceededException as e:
                            yield f"data: {json.dumps({'error': {'type': 'api_error', 'message': f'Request failed after {e.attempts} attempts.'}})}\n\n".encode("utf-8")
                        except AllKeysExhaustedException:
                            yield f"data: {json.dumps({'error': {'type': 'overloaded_error', 'message': 'All Ollama cloud keys are exhausted.'}})}\n\n".encode("utf-8")
                        except Exception as e:
                            yield f"data: {json.dumps({'error': {'type': 'api_error', 'message': str(e)}})}\n\n".encode("utf-8")
                    return StreamingResponse(
                        stream_gen(),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "X-Accel-Buffering": "no",
                        },
                    )
                else:
                    result = await self._router.route(body)
                    return JSONResponse(content=result)

            except AllKeysExhaustedException:
                return JSONResponse(
                    _anthropic_error(
                        "overloaded_error",
                        "All Ollama cloud keys are exhausted. "
                        "Open EverFlow dashboard to add more keys."
                    ),
                    status_code=529,
                )
            except MaxRetriesExceededException as e:
                return JSONResponse(
                    _anthropic_error(
                        "api_error",
                        f"Request failed after {e.attempts} attempts."
                    ),
                    status_code=500,
                )
            except Exception as e:
                return JSONResponse(
                    _anthropic_error("api_error", str(e)),
                    status_code=500,
                )

        # GET /v1/models — Claude Code may call this
        @app.get("/v1/models")
        async def list_models():
            return JSONResponse({
                "object": "list",
                "data": [
                    {"id": "gemma4:31b-cloud", "object": "model",
                     "created": 1763596800, "owned_by": "ollama"},
                    {"id": "glm-5.1:cloud", "object": "model",
                     "created": 1770768000, "owned_by": "ollama"},
                    {"id": "qwen3-coder:480b", "object": "model",
                     "created": 1753142400, "owned_by": "ollama"},
                ]
            })

        # GET /health
        @app.get("/health")
        async def health():
            return JSONResponse({
                "status": "ok",
                "proxy": "running",
                "keys": self._key_store.get_stats(),
            })

        return app

    def start(self) -> None:
        """Start proxy server in a background daemon thread."""
        host = self._config.get("proxy.host", "127.0.0.1")
        port = int(self._config.get("proxy.port", 8000))
        app = self._build_app()
        cfg = uvicorn.Config(app, host=host, port=port,
                             log_level="warning", access_log=False, log_config=None)
        self._server = uvicorn.Server(cfg)

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._server.serve())

        self._thread = threading.Thread(
            target=run, daemon=True, name="ollama-proxy-server"
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the server to shut down."""
        if self._server:
            self._server.should_exit = True

    def is_running(self) -> bool:
        """True if the server thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def wait_ready(self, timeout: float = 15.0) -> bool:
        """
        Poll /health until 200 or timeout.
        Returns True if server is ready, False if timeout.
        """
        host = self._config.get("proxy.host", "127.0.0.1")
        port = int(self._config.get("proxy.port", 8000))
        url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = requests_lib.get(url, timeout=2)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False