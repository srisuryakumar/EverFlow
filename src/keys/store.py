"""KeyStore: persistence layer for Ollama API keys."""

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models.api_key import APIKey
from src.models.enums import KeyStatus
from src.platform_utils import get_keys_path


class KeyStore:
    """Manages persistent storage of Ollama API keys."""

    def __init__(self):
        """Initialize the KeyStore."""
        self._path = get_keys_path()
        self._keys: dict[str, APIKey] = {}
        self._lock = threading.RLock()
        self._pending_save = False
        self._save_timer = None
        # Cache for dashboard to reduce locking
        self._stats_cache: Optional[dict] = None
        self._stats_cache_time: Optional[datetime] = None

    def load(self) -> None:
        """Load keys from disk, creating empty store if file does not exist."""
        with self._lock:
            if os.path.exists(self._path):
                try:
                    with open(self._path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start with empty store to prevent crash
                    return

                keys_list = data.get("keys", [])
                for i, key_dict in enumerate(keys_list, start=1):
                    key = APIKey.from_dict(key_dict)
                    if key.sequence_number == 0:
                        key.sequence_number = i
                    self._keys[key.key_id] = key

                # If we assigned new sequence numbers, save immediately
                if any(k.sequence_number == 0 for k in self._keys.values()): # This check is actually for old keys
                    pass # Logic handled above
                # Simpler: if any key was modified (sequence number added), save.
                # Since we can't easily know if it changed without a flag, we just check
                # if any key in the original data lacked a sequence_number.
                if any("sequence_number" not in kd for kd in keys_list):
                    self.save(immediate=True)
            else:
                self.save(immediate=True)

    def save(self, immediate: bool = False) -> None:
        """
        Atomically save keys to disk.
        Uses debouncing to reduce frequent disk writes.
        """
        with self._lock:
            self._pending_save = True
            if immediate:
                self._do_save()
            else:
                self._debounced_save()

    def _do_save(self) -> None:
        """Perform the actual save operation with minimal lock contention."""
        # 1. Prepare data under lock
        with self._lock:
            if not self._pending_save:
                return
            data = {"version": 1, "keys": [k.to_dict() for k in self._keys.values()]}
            json_data = json.dumps(data, indent=2)
            self._pending_save = False

        # 2. Disk I/O outside lock
        tmp_path = self._path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_data)
            os.replace(tmp_path, self._path)
        except Exception:
            # If save fails, mark as pending again to retry
            with self._lock:
                self._pending_save = True

    def _debounced_save(self) -> None:
        """Debounce save operations to reduce disk I/O."""
        with self._lock:
            self._pending_save = True
            if self._save_timer:
                self._save_timer.cancel()

            # Use a timer to batch save operations
            def delayed_save():
                with self._lock:
                    if self._pending_save:
                        self._do_save()

            self._save_timer = threading.Timer(2.0, delayed_save)  # 2 second debounce
            self._save_timer.daemon = True
            self._save_timer.start()

    def _invalidate_cache(self) -> None:
        """Invalidate the stats cache."""
        self._stats_cache = None
        self._stats_cache_time = None

    def add_key(self, api_key: str, alias: str = "", weight: float = 1.0) -> APIKey:
        """Add a new API key to the store."""
        with self._lock:
            for existing in self._keys.values():
                if existing.api_key == api_key:
                    raise ValueError("Key already exists in store.")
            key_id = str(uuid.uuid4())

            # Assign next sequence number
            max_seq = 0
            if self._keys:
                max_seq = max(k.sequence_number for k in self._keys.values())

            key = APIKey(
                key_id=key_id,
                api_key=api_key,
                alias=alias,
                weight=weight,
                sequence_number=max_seq + 1
            )
            self._keys[key_id] = key
            self._invalidate_cache()  # Invalidate stats cache
            self.save(immediate=True)
            return key

    def add_keys_bulk(self, api_keys: list[str]) -> tuple[int, int]:
        """Add multiple API keys at once. Returns (added, skipped) counts."""
        with self._lock:
            added = 0
            skipped = 0
            existing_values = {k.api_key for k in self._keys.values()}

            # Calculate current max sequence number
            max_seq = 0
            if self._keys:
                max_seq = max(k.sequence_number for k in self._keys.values())

            for i, key_value in enumerate(api_keys):
                if not isinstance(key_value, str):
                    continue
                stripped = key_value.strip()
                if not stripped:
                    continue
                if stripped in existing_values:
                    skipped += 1
                    continue
                key_id = str(uuid.uuid4())
                key = APIKey(
                    key_id=key_id,
                    api_key=stripped,
                    sequence_number=max_seq + (i + 1)
                )
                self._keys[key_id] = key
                existing_values.add(stripped)
                added += 1
            if added > 0:
                self._invalidate_cache()  # Invalidate stats cache
                self.save(immediate=True)
            return (added, skipped)

    def remove_key(self, key_id: str) -> bool:
        """Remove a key from the store. Returns True if removed, False if not found."""
        with self._lock:
            if key_id in self._keys:
                del self._keys[key_id]
                self._invalidate_cache()  # Invalidate stats cache
                self.save(immediate=True)
                return True
            return False

    def get_all(self) -> list[APIKey]:
        """Return a list of all keys."""
        with self._lock:
            return list(self._keys.values())

    def get_active(self) -> list[APIKey]:
        """Return a list of all available (active) keys."""
        with self._lock:
            return [k for k in self._keys.values() if k.is_available()]

    def get_by_id(self, key_id: str) -> Optional[APIKey]:
        """Return a key by its ID, or None if not found."""
        with self._lock:
            return self._keys.get(key_id)

    def update_key(self, key_id: str, **kwargs) -> None:
        """Update specific allowed fields on a key."""
        ALLOWED_UPDATE_FIELDS = {'alias', 'weight'}
        with self._lock:
            key = self._keys.get(key_id)
            if not key:
                raise KeyError(f"Key not found: {key_id}")
            for k, v in kwargs.items():
                if k in ALLOWED_UPDATE_FIELDS:
                    setattr(key, k, v)
            self._invalidate_cache()  # Invalidate stats cache
            self.save()

    def mark_exhausted(self, key_id: str, cooldown_seconds: int) -> None:
        """Mark a key as exhausted with a cooldown period."""
        with self._lock:
            key = self._keys.get(key_id)
            if not key:
                return
            key.status = KeyStatus.EXHAUSTED
            key.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
            key.exhaustion_count += 1
            key.last_error_at = datetime.now(timezone.utc)
            self._invalidate_cache()  # Invalidate stats cache
            self.save()  # Debounced

    def mark_invalid(self, key_id: str, http_status: int) -> None:
        """Mark a key as permanently invalid."""
        with self._lock:
            key = self._keys.get(key_id)
            if not key:
                return
            key.status = KeyStatus.INVALID
            key.last_error_code = http_status
            key.last_error_at = datetime.now(timezone.utc)
            self._invalidate_cache()  # Invalidate stats cache
            self.save(immediate=True)  # Permanently invalid keys must be saved immediately

    def recover_cooled_keys(self) -> int:
        """Recover keys whose cooldown has expired. Returns count recovered."""
        with self._lock:
            now = datetime.now(timezone.utc)
            recovered = 0
            for key in self._keys.values():
                if key.status in (KeyStatus.EXHAUSTED, KeyStatus.COOLDOWN):
                    if key.cooldown_until and now >= key.cooldown_until:
                        key.status = KeyStatus.ACTIVE
                        key.cooldown_until = None
                        recovered += 1
            if recovered > 0:
                self._invalidate_cache()  # Invalidate stats cache
                self.save()  # Debounced
            return recovered

    def get_stats(self) -> dict:
        """Return statistics about the key pool."""
        # Use cache to reduce locking contention (cache for 2 seconds)
        now = datetime.now(timezone.utc)
        if (self._stats_cache and self._stats_cache_time and
            (now - self._stats_cache_time).total_seconds() < 2.0):
            return self._stats_cache

        # Get keys list quickly under lock, then process outside lock
        with self._lock:
            keys = list(self._keys.values())

        # Process stats outside the lock to reduce contention
        stats = {
            "total": len(keys),
            "active": sum(1 for k in keys if k.is_available()),
            "exhausted": sum(
                1 for k in keys
                if k.status == KeyStatus.EXHAUSTED and not k.is_available()
            ),
            "invalid": sum(1 for k in keys if k.status == KeyStatus.INVALID),
            "disabled": sum(1 for k in keys if k.status == KeyStatus.DISABLED),
            "total_requests_all": sum(k.total_requests for k in keys),
            "total_tokens_all": sum(k.total_tokens for k in keys),
        }

        # Update cache
        self._stats_cache = stats
        self._stats_cache_time = now

        return stats