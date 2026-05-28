#!/usr/bin/env python3
"""Test script to verify Ollama client performance improvements."""

import asyncio
import time
import pytest
from src.config.manager import ConfigManager
from src.proxy.ollama_client import OllamaClient

@pytest.mark.asyncio
async def test_client_performance():
    """Test the Ollama client performance."""
    # ... (rest of function)
    print("Testing Ollama client performance...")

    config = ConfigManager()
    config.load()
    client = OllamaClient(config)

    # Test payload
    payload = {
        "model": "gemma4:31b-cloud",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 100
    }

    # Test multiple rapid requests to check for connection reuse
    start_time = time.time()

    for i in range(5):
        try:
            request_start = time.time()
            status, body, headers = await client.call("ollama_test_key_123", payload)
            request_time = time.time() - request_start
            print(f"Request {i+1}: {request_time:.3f}s, Status: {status}")

            # Small delay between requests
            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"Request {i+1} failed: {e}")

    total_time = time.time() - start_time
    print(f"Total time for 5 requests: {total_time:.3f}s")
    print(f"Average per request: {total_time/5:.3f}s")

    # Clean up
    await client.close()

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    asyncio.run(test_client_performance())