"""EverFlowApp: main orchestrator for EverFlow."""

import os
import sys
import time

from src.config.manager import ConfigManager
from src.dashboard.api import dashboard_router, set_dependencies
from src.keys.rotator import KeyRotator
from src.keys.store import KeyStore
from src.proxy.detector import ResponseDetector
from src.proxy.ollama_client import OllamaClient
from src.proxy.router import ProxyRouter
from src.proxy.server import ProxyServer
from src.tray.icon import TrayIcon


class EverFlowApp:
    """Main application orchestrator."""

    def __init__(self):
        """Initialise and wire all components."""
        # Config (load first — everything else reads from it)
        self._config = ConfigManager()
        self._config.load()

        # Key storage
        self._key_store = KeyStore()
        self._key_store.load()

        # Rotation engine
        self._rotator = KeyRotator(self._key_store, self._config)

        # Proxy internals
        self._detector = ResponseDetector()
        self._client = OllamaClient(self._config)
        self._router = ProxyRouter(
            self._key_store,
            self._rotator,
            self._detector,
            self._client,
            self._config,
        )

        # Wire dashboard API dependencies (must happen before server starts)
        set_dependencies(self._router, self._key_store, self._config)

        # Proxy server
        self._proxy = ProxyServer(self._router, self._key_store, self._config)

        # Tray icon
        self._tray = TrayIcon(
            on_open_dashboard=self._open_dashboard,
            on_quit=self._quit,
            proxy_server=self._proxy,
        )

    def run(self) -> None:
        """
        Start the application.
        Order: proxy server → open browser dashboard → tray icon (blocking).
        pywebview is NOT used — browser opens automatically instead.
        pystray must be last because tray.start() is blocking on macOS.
        """
        print("Starting EverFlow proxy server...")
        self._proxy.start()

        ready = self._proxy.wait_ready(timeout=15.0)
        if ready:
            port = self._config.get("proxy.port", 8000)
            print(f"Proxy ready at http://127.0.0.1:{port}")
        else:
            print("Warning: proxy did not respond in time — continuing anyway")

        print("Opening dashboard in browser...")
        self._open_dashboard()

        print("Starting system tray icon...")
        print("Tip: click the tray icon in the menu bar to open dashboard or quit")
        self._tray.start()   # BLOCKING — must be last on macOS

    def _start_webview(self) -> None:
        """Removed — pywebview conflicts with pystray on macOS main thread."""
        pass

    def _open_dashboard(self) -> None:
        """Open the dashboard in the system default browser."""
        import webbrowser

        port = self._config.get("proxy.port", 8000)
        url = f"http://127.0.0.1:{port}/dashboard/"
        webbrowser.open(url)
        print(f"Dashboard opened at {url}")

    def _quit(self) -> None:
        """Called from tray menu: shut everything down."""
        print("Shutting down EverFlow...")
        self._proxy.stop()
        # Clean up HTTP client
        if hasattr(self, '_client') and self._client:
            import asyncio
            try:
                # Run async cleanup in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._client.close())
                loop.close()
            except Exception:
                pass
        if self._tray:
            self._tray.stop()
        print("EverFlow has shut down gracefully.")