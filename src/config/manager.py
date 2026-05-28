"""Configuration management for EverFlow."""

import copy
import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from src.platform_utils import get_config_path


DEFAULT_CONFIG = {
    "proxy": {
        "port": 8000,
        "host": "127.0.0.1"
    },
    "dashboard": {
        "port": 8080,
        "refresh_interval_ms": 2000
    },
    "rotation": {
        "max_retries": 10,
        "last_used_key_index": 0,
        "request_timeout_seconds": 300,
        "default_cooldown_seconds": 60,
        "base_backoff_seconds": 1.0,
        "max_backoff_seconds": 60.0
    },
    "ollama": {
        "cloud_base_url": "https://ollama.com",
        "default_model": "gemma4:31b-cloud",
        "anthropic_version": "2023-06-01",
        "model_map": {
            "claude-opus-4-7": "gemma4:31b-cloud",
            "claude-sonnet-4-6": "gemma4:31b-cloud",
            "claude-haiku-4-5-20251001": "gemma4:31b-cloud",
            "claude-sonnet-4-5": "gemma4:31b-cloud",
            "claude-haiku-4-5": "gemma4:31b-cloud",
            "claude-3-5-sonnet-20241022": "gemma4:31b-cloud",
            "claude-3-5-sonnet-20240620": "gemma4:31b-cloud",
            "claude-3-5-haiku-20241022": "gemma4:31b-cloud",
            "claude-3-opus-20240229": "gemma4:31b-cloud",
            "claude-3-sonnet-20240229": "gemma4:31b-cloud",
            "claude-3-haiku-20240307": "gemma4:31b-cloud",
            "claude-opus-4": "gemma4:31b-cloud",
            "claude-sonnet-4": "gemma4:31b-cloud",
            "claude-haiku-4": "gemma4:31b-cloud",
            "claude-3-5-sonnet": "gemma4:31b-cloud",
            "claude-3-5-haiku": "gemma4:31b-cloud",
            "claude-3-opus": "gemma4:31b-cloud",
            "claude-3-sonnet": "gemma4:31b-cloud",
            "claude-3-haiku": "gemma4:31b-cloud"
        }
    },
    "available_models": [
        {"name": "DeepSeek V3.1", "tag": "gemma4:31b-cloud", "enabled": True},
        {"name": "GLM-5.1", "tag": "glm-5.1:cloud", "enabled": True},
        {"name": "Qwen3 Coder", "tag": "qwen3-coder:480b", "enabled": True}
    ]
}


class ConfigManager:
    """Manages application configuration stored in config.json."""

    def __init__(self):
        """Initialize the ConfigManager."""
        self._path = get_config_path()
        self._data: dict = {}
        self._lock = threading.RLock()
        self._pending_save = False
        self._save_timer: Optional[threading.Timer] = None

    def load(self) -> None:
        """Load configuration from disk, merging with defaults."""
        with self._lock:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                self._data = self._deep_merge(copy.deepcopy(DEFAULT_CONFIG), loaded_data)

                # Migrate available_models from List[str] to List[Dict]
                models = self._data.get("available_models", [])
                if models and isinstance(models[0], str):
                    migrated = []
                    for m in models:
                        if isinstance(m, str):
                            migrated.append({"name": m, "tag": m, "enabled": True})
                        else:
                            migrated.append(m)
                    self._data["available_models"] = migrated
                    self.save(immediate=True)
            else:
                self._data = copy.deepcopy(DEFAULT_CONFIG)
                self.save(immediate=True)

    def save(self, immediate: bool = False) -> None:
        """
        Atomically save configuration to disk.
        Uses debouncing to reduce frequent disk writes.
        """
        with self._lock:
            if immediate:
                self._do_save()
            else:
                self._debounced_save()

    def _do_save(self) -> None:
        """Perform the actual save operation with minimal lock contention."""
        with self._lock:
            data_to_save = copy.deepcopy(self._data)
            self._pending_save = False

        tmp_path = self._path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            with self._lock:
                self._pending_save = True

    def _debounced_save(self) -> None:
        """Debounce save operations to reduce disk I/O."""
        self._pending_save = True
        if self._save_timer:
            self._save_timer.cancel()

        def delayed_save():
            with self._lock:
                if self._pending_save:
                    self._do_save()

        self._save_timer = threading.Timer(2.0, delayed_save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def get(self, key_path: str, default=None):
        """Get a configuration value by dot-notation key path."""
        with self._lock:
            keys = key_path.split(".")
            value = self._data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            return value

    def set(self, key_path: str, value) -> None:
        """Set a configuration value by dot-notation key path and save."""
        with self._lock:
            keys = key_path.split(".")
            obj = self._data
            for key in keys[:-1]:
                if key not in obj:
                    obj[key] = {}
                obj = obj[key]
            obj[keys[-1]] = value
            self.save()

    def update(self, partial: dict) -> None:
        """Deep-merge a partial dict into configuration and save."""
        with self._lock:
            self._data = self._deep_merge(self._data, partial)
            self.save()

    def all(self) -> dict:
        """Return a deep copy of the entire configuration."""
        with self._lock:
            return copy.deepcopy(self._data)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep-merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base