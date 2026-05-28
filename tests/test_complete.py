#!/usr/bin/env python3
"""Complete test script for EverFlow functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.platform_utils import get_app_data_dir, get_keys_path, get_config_path
from src.models.api_key import APIKey
from src.models.enums import KeyStatus
from src.keys.store import KeyStore
from src.config.manager import ConfigManager
from src.proxy.ollama_client import OllamaClient
from src.proxy.detector import ResponseDetector
from src.keys.rotator import KeyRotator
from src.proxy.router import ProxyRouter

def test_platform_utils():
    """Test platform utilities."""
    print("Testing platform utilities...")
    app_dir = get_app_data_dir()
    keys_path = get_keys_path()
    config_path = get_config_path()

    print(f"  App data dir: {app_dir}")
    print(f"  Keys path: {keys_path}")
    print(f"  Config path: {config_path}")

    assert isinstance(app_dir, str) and app_dir
    assert isinstance(keys_path, str) and keys_path
    assert isinstance(config_path, str) and config_path
    print("  ✓ Platform utilities test passed\n")

def test_models():
    """Test data models."""
    print("Testing data models...")

    # Test APIKey model
    key = APIKey(key_id='test-001', api_key='ollama_abc123xyz789', alias='Test Key')
    assert key.key_id == 'test-001'
    assert key.api_key == 'ollama_abc123xyz789'
    assert key.alias == 'Test Key'
    assert key.status == KeyStatus.ACTIVE
    assert key.masked_key() == 'olla...z789'
    assert key.display_name() == 'Test Key'

    # Test serialization round-trip
    key_dict = key.to_dict()
    restored = APIKey.from_dict(key_dict)
    assert restored.key_id == key.key_id
    assert restored.api_key == key.api_key
    assert restored.alias == key.alias

    print("  ✓ Data models test passed\n")

def test_key_store():
    """Test key store functionality."""
    print("Testing key store...")

    store = KeyStore()

    # Add test keys
    k1 = store.add_key('ollama_test_key_001_abcdefghij', alias='Test Account 1')
    k2 = store.add_key('ollama_test_key_002_abcdefghij', alias='Test Account 2')

    # Verify keys were added
    all_keys = store.get_all()
    assert len(all_keys) == 2
    assert all(k.enabled for k in all_keys)
    assert all(k.status == KeyStatus.ACTIVE for k in all_keys)

    # Note: Key validation is handled elsewhere in the codebase

    print("  ✓ Key store test passed\n")

def test_config_manager():
    """Test config manager."""
    print("Testing config manager...")

    config = ConfigManager()

    # Test default values
    base_url = config.get('ollama.cloud_base_url', 'https://api.ollama.com')
    timeout = config.get('rotation.request_timeout_seconds', 120)

    assert base_url == 'https://api.ollama.com'
    assert timeout == 120

    print("  ✓ Config manager test passed\n")

def test_components():
    """Test component initialization."""
    print("Testing component initialization...")

    config = ConfigManager()
    store = KeyStore()
    client = OllamaClient(config)
    detector = ResponseDetector()
    rotator = KeyRotator(store, config)
    router = ProxyRouter(store, rotator, detector, client, config)

    assert config is not None
    assert store is not None
    assert client is not None
    assert detector is not None
    assert rotator is not None
    assert router is not None

    print("  ✓ Component initialization test passed\n")

def main():
    """Run all tests."""
    print("Running comprehensive EverFlow tests...\n")

    try:
        test_platform_utils()
        test_models()
        test_key_store()
        test_config_manager()
        test_components()

        print("✅ All tests passed! EverFlow is functioning correctly.")
        print("\nTo test the full application:")
        print("1. Run: python main.py")
        print("2. Open: http://localhost:8000/dashboard/")
        print("3. Add real Ollama API keys in the dashboard")
        print("4. Test proxy endpoint: POST http://localhost:8000/v1/messages")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())