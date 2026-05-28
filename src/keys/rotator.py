"""KeyRotator: selects next API key using configured rotation strategy."""

import random
import threading
import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.config.manager import ConfigManager
from src.exceptions import AllKeysExhaustedException
from src.keys.store import KeyStore
from src.models.api_key import APIKey
from src.models.enums import ErrorType, KeyStatus


class KeyRotator:
    """Manages key rotation strategy and records outcomes."""

    def __init__(self, key_store: KeyStore, config: ConfigManager):
        """Initialize the KeyRotator."""
        self._store = key_store
        self._config = config
        self._lock = threading.RLock()
        self._rr_pointer: int = self._config.get("rotation.last_used_key_index", 0)

    async def get_next_key(self, exclude: list[str] = None) -> APIKey:
        """Select the next available key using the sticky index-based strategy."""
        with self._lock:
            # Step 1: recover any cooled-down keys first
            self._store.recover_cooled_keys()

            # Step 2: get all keys and sort by sequence number to ensure deterministic order
            all_keys = sorted(self._store.get_all(), key=lambda k: k.sequence_number)
            if not all_keys:
                raise AllKeysExhaustedException(0)

            exclude_set = set(exclude or [])

            # Step 3: Sticky Cursor Logic
            # Use the internal pointer
            current_idx = self._rr_pointer

            # Reset cursor if it's out of bounds to ensure deterministic start
            if current_idx < 0 or current_idx >= len(all_keys):
                current_idx = 0

            # Try all keys in the pool starting from the current index
            for i in range(len(all_keys)):
                # Normalize index to be within the current key pool size
                idx = (current_idx + i) % len(all_keys)
                key = all_keys[idx]

                # A key is a valid match if it's available (ACTIVE/recovered) AND not excluded
                if key.is_available() and key.key_id not in exclude_set:
                    # Stick to this key: update internal pointer to this index
                    # If i == 0, we are sticking to the current key.
                    # If i > 0, we found a new key and should move the cursor.
                    if i > 0:
                        self._rr_pointer = idx
                        asyncio.create_task(asyncio.to_thread(self._config.set, "rotation.last_used_key_index", self._rr_pointer))
                    return key

            # Step 4: Raise if no suitable key found after checking the entire pool
            raise AllKeysExhaustedException(len(all_keys))

    def get_current_key_id(self) -> Optional[str]:
        """Return the ID of the most recently used key."""
        with self._lock:
            idx = self._rr_pointer
            all_keys = sorted(self._store.get_all(), key=lambda k: k.sequence_number)
            if 0 <= idx < len(all_keys):
                return all_keys[idx].key_id
            return None

    async def record_success(
        self, key_id: str, tokens_used: int, latency_ms: float
    ) -> None:
        """Record a successful API call on the key."""
        key = self._store.get_by_id(key_id)
        if not key:
            return
        key.total_requests += 1
        key.total_tokens += tokens_used
        key.last_used_at = datetime.now(timezone.utc)
        key.last_success_at = datetime.now(timezone.utc)
        await asyncio.to_thread(self._store.save)

    async def record_failure(
        self,
        key_id: str,
        error_type: ErrorType,
        http_status: int,
        retry_after: int = None,
    ) -> None:
        """Record a failed attempt and apply the appropriate key state change."""
        key = self._store.get_by_id(key_id)
        if not key:
            return
        key.last_error_at = datetime.now(timezone.utc)
        key.last_error_code = http_status
        key.total_requests += 1

        if error_type in (ErrorType.RATE_LIMITED, ErrorType.DAILY_LIMIT_EXCEEDED):
            cooldown = retry_after or self._config.get(
                "rotation.default_cooldown_seconds", 60
            )
            await asyncio.to_thread(self._store.mark_exhausted, key_id, cooldown)

        elif error_type == ErrorType.KEY_INVALID:
            await asyncio.to_thread(self._store.mark_invalid, key_id, http_status)

        else:
            # Network/server errors: save updated counters but don't change status
            await asyncio.to_thread(self._store.save)

    def calculate_backoff(self, attempt: int) -> float:
        """Exponential backoff with jitter. Returns seconds to wait."""
        base = self._config.get("rotation.base_backoff_seconds", 1.0)
        maximum = self._config.get("rotation.max_backoff_seconds", 60.0)
        jitter = random.uniform(0, base * 0.1)
        return min(base * (2**attempt) + jitter, maximum)