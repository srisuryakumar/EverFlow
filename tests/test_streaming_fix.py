import asyncio
from src.config.manager import ConfigManager
from src.keys.store import KeyStore
from src.keys.rotator import KeyRotator
from src.proxy.detector import ResponseDetector
from src.proxy.router import ProxyRouter

async def mock_stream_gen():
    yield b"chunk 1"
    yield b"chunk 2"

class MockClient:
    def stream(self, key, payload):
        return mock_stream_gen()

async def test():
    config = ConfigManager()
    store = KeyStore()
    import os
    from src.platform_utils import get_keys_path
    p = get_keys_path()
    if os.path.exists(p): os.remove(p)
    store.add_key('test', 'test')
    
    rotator = KeyRotator(store, config)
    detector = ResponseDetector()
    client = MockClient()
    router = ProxyRouter(store, rotator, detector, client, config)
    
    print("Calling route_stream...")
    stream = router.route_stream({"model": "test", "stream": True})
    print("Stream object created.")
    
    chunks = []
    async for chunk in stream:
        print(f"Got chunk: {chunk}")
        chunks.append(chunk)
    
    print(f"Final chunks: {chunks}")
    assert chunks == [b"chunk 1", b"chunk 2"]

if __name__ == "__main__":
    asyncio.run(test())
