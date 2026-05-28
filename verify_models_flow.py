import asyncio
import httpx
import json
import os

async def main():
    async with httpx.AsyncClient() as client:
        print("--- Testing Model Flow (using existing server) ---")
        base_url = "http://localhost:8000"
        
        # 1. Add a new model
        test_model_name = "TestModel-X"
        test_model_tag = "test-tag:latest"
        add_res = await client.post(
            f"{base_url}/dashboard/models",
            json={"name": test_model_name, "tag": test_model_tag}
        )
        print(f"Add Model Response: {add_res.status_code}")
        assert add_res.status_code == 200
        
        # 2. Set as default
        set_def_res = await client.patch(
            f"{base_url}/dashboard/config",
            json={"ollama": {"default_model": test_model_tag}}
        )
        print(f"Set Default Response: {set_def_res.status_code}")
        assert set_def_res.status_code == 200
        
        # 3. Verify via /dashboard/config
        config_res = await client.get(f"{base_url}/dashboard/all")
        config_data = config_res.json()
        default_model = config_data.get("config", {}).get("ollama", {}).get("default_model")
        print(f"Current Default Model in Config: {default_model}")
        assert default_model == test_model_tag
        
        print("\n✅ Model flow verification SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(main())
