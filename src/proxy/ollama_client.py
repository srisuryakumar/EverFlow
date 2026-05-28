"""OllamaClient: async HTTP client for ollama.com cloud API."""

import asyncio
import httpx
from typing import AsyncGenerator, Optional

from src.config.manager import ConfigManager


class OllamaClient:
    """Async HTTP client for Ollama cloud API."""

    def __init__(self, config: ConfigManager):
        """Initialize the OllamaClient."""
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    def _get_base_url(self) -> str:
        """Return the Ollama cloud base URL."""
        return self._config.get("ollama.cloud_base_url", "https://api.ollama.com")

    def _get_headers(self, api_key: str) -> dict:
        """Construct the headers for the Ollama cloud API."""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure the HTTP client is initialized and return it."""
        async with self._lock:
            if self._client is None:
                timeout = self._config.get("rotation.request_timeout_seconds", 120)
                self._client = httpx.AsyncClient(
                    timeout=float(timeout),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
                )
        return self._client

    async def call(
        self, api_key: str, payload: dict
    ) -> tuple[int, dict, dict]:
        """
        Make a single non-streaming POST to ollama.com/v1/messages.
        Returns: (status_code, response_body_dict, response_headers_dict)
        Never raises on 4xx/5xx.
        Raises: httpx.TimeoutException, httpx.ConnectError on network failure.
        """
        url = self._get_base_url() + "/v1/messages"
        headers = self._get_headers(api_key)

        client = await self._ensure_client()

        try:
            response = await client.post(url, json=payload, headers=headers)
            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text}
            return (response.status_code, body, dict(response.headers))
        except (httpx.RemoteProtocolError, httpx.RuntimeError) as exc:
            # If client becomes invalid, recreate it on next call
            async with self._lock:
                if self._client:
                    await self._client.aclose()
                    self._client = None
            raise exc
        except Exception:
            raise

    async def stream(
        self, api_key: str, payload: dict
    ) -> AsyncGenerator[bytes, None]:
        """
        Make a streaming POST. Yields raw SSE bytes.
        """
        payload = {**payload, "stream": True}
        url = self._get_base_url() + "/v1/messages"
        headers = self._get_headers(api_key)

        client = await self._ensure_client()
        async with client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        async with self._lock:
            if self._client:
                await self._client.aclose()
                self._client = None