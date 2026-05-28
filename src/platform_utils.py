"""Cross-platform utilities for EverFlow."""

import os
import platform


def get_app_data_dir() -> str:
    """Return the platform-specific application data directory."""
    system = platform.system()
    if system == "Darwin":
        path = os.path.expanduser("~/Library/Application Support/EverFlow")
    elif system == "Windows":
        path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "EverFlow")
    else:
        path = os.path.expanduser("~/.config/EverFlow")
    os.makedirs(path, exist_ok=True)
    return path


def get_keys_path() -> str:
    """Return the path to keys.json in the app data directory."""
    return os.path.join(get_app_data_dir(), "keys.json")


def get_config_path() -> str:
    """Return the path to config.json in the app data directory."""
    return os.path.join(get_app_data_dir(), "config.json")


def get_log_path() -> str:
    """Return the path to router.log in the app data directory."""
    return os.path.join(get_app_data_dir(), "router.log")


def is_mac() -> bool:
    """Return True if the current platform is macOS."""
    return platform.system() == "Darwin"


def is_windows() -> bool:
    """Return True if the current platform is Windows."""
    return platform.system() == "Windows"