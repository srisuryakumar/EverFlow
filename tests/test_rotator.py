"""Tests for src/keys/rotator.py."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil
import asyncio

from src.keys.rotator import KeyRotator
from src.keys.store import KeyStore
from src.models.api_key import APIKey
from src.models.enums import KeyStatus, ErrorType
from src.exceptions import AllKeysExhaustedException
from src.config.manager import ConfigManager
from src.platform_utils import get_keys_path, get_config_path


@pytest.fixture
def setup():
    """Create a fresh in-memory setup for each test."""
    keys_path = get_keys_path()
    config_path = get_config_path()

    if os.path.exists(keys_path):
        os.remove(keys_path)
    if os.path.exists(config_path):
        os.remove(config_path)

    config = ConfigManager()
    config.load()
    store = KeyStore()
    store.load()
    rotator = KeyRotator(store, config)
    return config, store, rotator


@pytest.mark.asyncio
async def test_exclude_list_respected(setup):
    """Excluded keys should not be returned."""
    config, store, rotator = setup

    keys = [
        store.add_key(f"ollama_key_exclude_{i:03d}_abcdef", alias=f"Key{i}")
        for i in range(5)
    ]

    exclude_ids = [k.key_id for k in keys[:4]]
    next_key = await rotator.get_next_key(exclude=exclude_ids)
    assert next_key.key_id == keys[4].key_id


@pytest.mark.asyncio
async def test_all_exhausted_raises(setup):
    """All keys exhausted should raise AllKeysExhaustedException."""
    config, store, rotator = setup

    keys = [
        store.add_key(f"ollama_key_exhausted_{i:03d}_abcdef", alias=f"Key{i}")
        for i in range(3)
    ]

    for k in keys:
        store.mark_exhausted(k.key_id, cooldown_seconds=86400)

    with pytest.raises(AllKeysExhaustedException) as exc_info:
        await rotator.get_next_key()

    assert exc_info.value.total_keys == 3


@pytest.mark.asyncio
async def test_recovery_on_get(setup):
    """Keys with expired cooldown should be recovered on get_next_key."""
    config, store, rotator = setup

    key = store.add_key("ollama_key_recovery_001_abcdef", alias="Key1")
    key.status = KeyStatus.EXHAUSTED
    key.cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=2)
    store.save()

    next_key = await rotator.get_next_key()
    assert next_key.key_id == key.key_id
    recovered_key = store.get_by_id(key.key_id)
    assert recovered_key.status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_record_success_updates_key(setup):
    """record_success should update key stats."""
    config, store, rotator = setup
    key = store.add_key("ollama_key_success_001_abcdef", alias="Key1")
    await rotator.record_success(key.key_id, tokens_used=500, latency_ms=800)
    updated_key = store.get_by_id(key.key_id)
    assert updated_key.total_requests == 1
    assert updated_key.total_tokens == 500
    assert updated_key.last_success_at is not None


@pytest.mark.asyncio
async def test_record_failure_rate_limit_marks_exhausted(setup):
    """record_failure with RATE_LIMITED should mark key as exhausted."""
    config, store, rotator = setup
    key = store.add_key("ollama_key_ratelimit_001_abcdef", alias="Key1")
    await rotator.record_failure(key.key_id, ErrorType.RATE_LIMITED, 429, retry_after=30)
    updated_key = store.get_by_id(key.key_id)
    assert updated_key.status == KeyStatus.EXHAUSTED
    assert updated_key.cooldown_until is not None


def test_backoff_increases(setup):
    """Backoff should increase monotonically up to max."""
    config, store, rotator = setup
    results = [rotator.calculate_backoff(i) for i in range(6)]
    for i in range(1, len(results)):
        assert results[i] > results[i - 1]
    assert all(r <= 60.5 for r in results)


@pytest.mark.asyncio
async def test_sticky_sequential_order(setup):
    """Sticky sequential should stick to a key until it is exhausted."""
    config, store, rotator = setup

    k1 = store.add_key("ollama_key_S01_abcdef", alias="Key1")
    k2 = store.add_key("ollama_key_S02_ghijkl", alias="Key2")
    k3 = store.add_key("ollama_key_S03_mnopqr", alias="Key3")

    # Should stick to k1 (lowest sequence number)
    for _ in range(3):
        assert (await rotator.get_next_key()).key_id == k1.key_id

    # Mark k1 exhausted, should move to k2
    store.mark_exhausted(k1.key_id, 60)
    assert (await rotator.get_next_key()).key_id == k2.key_id

    # Should stick to k2
    assert (await rotator.get_next_key()).key_id == k2.key_id


@pytest.mark.asyncio
async def test_sticky_sequential_wrap(setup):
    """Sticky sequential should wrap around to the first key after the last one."""
    config, store, rotator = setup

    keys = [
        store.add_key(f"ollama_key_W{i}_abcdef", alias=f"Key{i}")
        for i in range(2)
    ]
    sorted_keys = sorted(keys, key=lambda k: k.sequence_number)

    # Use the last key
    config.set("rotation.last_used_key_index", len(sorted_keys) - 1)

    # Mark the last key exhausted
    store.mark_exhausted(sorted_keys[-1].key_id, 60)

    # Should wrap back to the first key
    next_key = await rotator.get_next_key()
    assert next_key.key_id == sorted_keys[0].key_id


@pytest.mark.asyncio
async def test_sticky_sequential_persistence(setup):
    """Sticky sequential should remember the last used key index across restarts."""
    config, store, rotator = setup

    keys = [
        store.add_key(f"ollama_key_P{i}_abcdef", alias=f"Key{i}")
        for i in range(3)
    ]
    sorted_keys = sorted(keys, key=lambda k: k.sequence_number)

    # Manually set cursor to key index 1 (the second key)
    config.set("rotation.last_used_key_index", 1)

    # New rotator instance
    rotator_new = KeyRotator(store, config)

    # Should pick key at index 1
    next_key = await rotator_new.get_next_key()
    assert next_key.key_id == sorted_keys[1].key_id


@pytest.mark.asyncio
async def test_sticky_sequential_missing_cursor(setup):
    """Sticky sequential should default to index 0 if cursor is invalid."""
    config, store, rotator = setup
    config.set("rotation.last_used_key_index", 999) # Out of bounds

    keys = [
        store.add_key(f"ollama_key_M{i}_abcdef", alias=f"Key{i}")
        for i in range(2)
    ]
    sorted_keys = sorted(keys, key=lambda k: k.sequence_number)

    next_key = await rotator.get_next_key()
    assert next_key.key_id == sorted_keys[0].key_id


@pytest.mark.asyncio
async def test_sticky_sequential_exclude(setup):
    """Sticky sequential should skip excluded keys and move cursor forward."""
    config, store, rotator = setup

    keys = [
        store.add_key(f"ollama_key_E{i}_abcdef", alias=f"Key{i}")
        for i in range(3)
    ]
    sorted_keys = sorted(keys, key=lambda k: k.sequence_number)

    # Cursor at 0, but exclude key 0
    next_key = await rotator.get_next_key(exclude=[sorted_keys[0].key_id])

    # Should move to key 1
    assert next_key.key_id == sorted_keys[1].key_id

    # Give the background config save task a moment to complete
    await asyncio.sleep(0.1)
    assert config.get("rotation.last_used_key_index") == 1
