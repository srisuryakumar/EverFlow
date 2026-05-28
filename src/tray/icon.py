"""TrayIcon: system tray icon for EverFlow."""

import os
import sys
import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from src.proxy.server import ProxyServer


class TrayIcon:
    """System tray icon with context menu."""

    def __init__(
        self,
        on_open_dashboard: Callable,
        on_quit: Callable,
        proxy_server: ProxyServer,
    ):
        """Initialize the TrayIcon."""
        self._open_cb = on_open_dashboard
        self._quit_cb = on_quit
        self._proxy = proxy_server
        self._icon: Optional[pystray.Icon] = None

    def _make_image(self) -> Image.Image:
        """Load the icon from assets folder."""
        # Get the path to assets/logo.png relative to this file
        # Works for both development and PyInstaller builds
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Check for PyInstaller bundled path first
        if getattr(sys, 'frozen', False):
            # Running as compiled exe/app
            base_path = sys._MEIPASS

        icon_path = os.path.join(base_path, 'assets', 'logo.png')

        if os.path.exists(icon_path):
            img = Image.open(icon_path)
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            # Ensure correct size for system tray
            img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img

        # Fallback: generate a simple key icon if file not found
        img = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([6, 6, 30, 30], fill=(0, 0, 0, 255))
        draw.ellipse([11, 11, 25, 25], fill=(255, 255, 255, 255))
        draw.rectangle([18, 16, 56, 21], fill=(0, 0, 0, 255))
        draw.rectangle([36, 21, 40, 28], fill=(0, 0, 0, 255))
        draw.rectangle([44, 21, 48, 32], fill=(0, 0, 0, 255))
        draw.rectangle([52, 21, 56, 36], fill=(0, 0, 0, 255))
        return img

    def _make_menu(self) -> pystray.Menu:
        """Build the tray context menu."""
        def get_status(item):
            return "Proxy: Running ●" if self._proxy.is_running() else "Proxy: Stopped ○"

        return pystray.Menu(
            pystray.MenuItem("EverFlow", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Dashboard", lambda icon, item: self._open_cb()),
            pystray.MenuItem(get_status, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda icon, item: self._quit_cb()),
        )

    def start(self) -> None:
        """Start the tray icon. BLOCKING — call from main thread."""
        self._icon = pystray.Icon(
            name="EverFlow",
            icon=self._make_image(),
            title="EverFlow",
            menu=self._make_menu(),
        )
        self._icon.run()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass