#!/usr/bin/env python3
"""KeyStore performance test."""

import time
import threading
from src.keys.store import KeyStore
from src.config.manager import ConfigManager

def test_key_store_performance():
    """Test KeyStore performance with frequent operations."""
    print("Testing KeyStore performance...")

    # Create a test key store
    store = KeyStore()
    config = ConfigManager()
    config.load()

    # Add some test keys
    test_keys = [
        f"ollama_test_key_{i:03d}_abcdefghijklmnop" for i in range(20)
    ]

    start_time = time.time()

    # Add keys
    for i, key_value in enumerate(test_keys):
        store.add_key(key_value, alias=f"Test Key {i}")

    add_time = time.time() - start_time
    print(f"Added {len(test_keys)} keys in {add_time:.3f} seconds")

    # Test frequent stats access (simulating dashboard)
    stats_start = time.time()
    stats_calls = 100

    for i in range(stats_calls):
        stats = store.get_stats()
        # Simulate some processing
        time.sleep(0.001)

    stats_time = time.time() - stats_start
    print(f"Made {stats_calls} get_stats() calls in {stats_time:.3f} seconds")
    print(f"Average: {stats_time / stats_calls * 1000:.3f} ms per call")

    # Test concurrent access
    concurrent_start = time.time()

    def concurrent_stats(thread_id):
        for i in range(20):
            stats = store.get_stats()
            time.sleep(0.001)
        return True

    threads = []
    for i in range(5):
        thread = threading.Thread(target=concurrent_stats, args=(i,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    concurrent_time = time.time() - concurrent_start
    print(f"Concurrent stats access (5 threads × 20 calls): {concurrent_time:.3f} seconds")

    return add_time, stats_time, concurrent_time

if __name__ == "__main__":
    print("KeyStore Performance Test")
    print("=" * 40)

    try:
        add_time, stats_time, concurrent_time = test_key_store_performance()

        print(f"\nPerformance Summary:")
        print(f"- Key addition: {add_time:.3f}s")
        print(f"- Stats access: {stats_time:.3f}s ({stats_time / 100 * 1000:.3f} ms/call)")
        print(f"- Concurrent access: {concurrent_time:.3f}s")

    except Exception as e:
        print(f"Error during KeyStore test: {e}")
        import traceback
        traceback.print_exc()