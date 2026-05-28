"""Dashboard API routes for EverFlow."""

import os
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, FileResponse

from src.models.enums import KeyStatus


# Module-level globals set by app before server starts
_router = None
_key_store = None
_config = None


def set_dependencies(router, key_store, config) -> None:
    """Set the module-level dependencies."""
    global _router, _key_store, _config
    _router = router
    _key_store = key_store
    _config = config


dashboard_router = APIRouter(tags=["dashboard"])


@dashboard_router.get("/dashboard/")
async def serve_dashboard():
    """Serve the dashboard HTML file."""
    try:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "dashboard", "index.html")
        if not os.path.exists(path):
            return JSONResponse({"error": "dashboard not found"}, status_code=404)
        return FileResponse(path)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.get("/dashboard/summary")
async def get_summary():
    """Return aggregate proxy statistics."""
    try:
        return JSONResponse(await _router.get_summary())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.get("/dashboard/keys")
async def get_keys():
    """Return all keys with stats."""
    try:
        keys = _key_store.get_all()
        stats = _key_store.get_stats()
        return JSONResponse({
            "keys": [k.to_dashboard_dict() for k in keys],
            "stats": stats,
            "current_key_id": _router._rotator.get_current_key_id()
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.get("/dashboard/logs")
async def get_logs(request: Request):
    """Return recent request logs."""
    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
        return JSONResponse({"logs": await _router.get_recent_logs(limit)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.get("/dashboard/chart/rpm")
async def get_rpm_chart():
    """Return requests-per-minute chart data."""
    try:
        return JSONResponse({"data": await _router.get_requests_per_minute()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)




@dashboard_router.get("/dashboard/all")
async def get_all_data(request: Request):
    """Return all dashboard data in a single combined response."""
    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)

        # Get all data in parallel, using to_thread for synchronous calls
        results = await asyncio.gather(
            _router.get_summary(),
            _router.get_recent_logs(limit),
            _router.get_requests_per_minute(),
            asyncio.to_thread(_key_store.get_all),
            asyncio.to_thread(_key_store.get_stats),
            asyncio.to_thread(_config.all),
            asyncio.to_thread(_router._rotator.get_current_key_id)
        )

        summary, logs, rpm_data, keys_data, stats, config_data, current_key_id = results

        return JSONResponse({
            "summary": summary,
            "keys": [k.to_dashboard_dict() for k in keys_data],
            "stats": stats,
            "logs": logs,
            "rpm": rpm_data,
            "config": config_data,
            "current_key_id": current_key_id
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.get("/dashboard/config")
async def get_config():
    """Return the current configuration."""
    try:
        return JSONResponse(_config.all())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.patch("/dashboard/config")

async def update_config(request: Request):
    """Update configuration with partial values."""
    try:
        body = await request.json()
        _config.update(body)
        return JSONResponse({"success": True, "config": _config.all()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@dashboard_router.get("/dashboard/performance")
async def get_performance():
    """Return performance metrics for monitoring."""
    try:
        import time
        import psutil
        import os

        process = psutil.Process(os.getpid())

        return JSONResponse({
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": process.cpu_percent(),
            "thread_count": process.num_threads(),
            "timestamp": time.time()
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.post("/dashboard/keys/add")
async def add_key(request: Request):
    """Add a single API key."""
    try:
        body = await request.json()
        api_key_val = body.get("api_key", "").strip()
        alias_val = body.get("alias", "")
        if not api_key_val:
            return JSONResponse({"error": "api_key required"}, status_code=400)
        key = _key_store.add_key(api_key_val, alias=alias_val)
        return JSONResponse({
            "success": True,
            "key_id": key.key_id,
            "display_name": key.display_name()
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.post("/dashboard/keys/bulk")
async def add_keys_bulk(request: Request):
    """Add multiple API keys at once."""
    try:
        body = await request.json()
        api_keys_list = body.get("api_keys", [])
        added, skipped = _key_store.add_keys_bulk(api_keys_list)
        return JSONResponse({"success": True, "added": added, "skipped": skipped})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.delete("/dashboard/keys/{key_id}")
async def remove_key(key_id: str):
    """Remove an API key."""
    try:
        result = _key_store.remove_key(key_id)
        return JSONResponse({"success": result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.post("/dashboard/keys/{key_id}/enable")
async def enable_key(key_id: str):
    """Enable an API key, resetting it to ACTIVE status regardless of previous state."""
    try:
        key = _key_store.get_by_id(key_id)
        if not key:
            return JSONResponse({"error": "Key not found"}, status_code=404)
        key.enabled = True
        key.status = KeyStatus.ACTIVE
        _key_store.save()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.post("/dashboard/keys/{key_id}/disable")
async def disable_key(key_id: str):
    """Disable an API key."""
    try:
        key = _key_store.get_by_id(key_id)
        if not key:
            return JSONResponse({"error": "Key not found"}, status_code=404)
        key.enabled = False
        key.status = KeyStatus.DISABLED
        _key_store.save()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.post("/dashboard/keys/{key_id}/reset")
async def reset_key(key_id: str):
    """Reset an API key to active state."""
    try:
        key = _key_store.get_by_id(key_id)
        if not key:
            return JSONResponse({"error": "Key not found"}, status_code=404)
        key.status = KeyStatus.ACTIVE
        key.cooldown_until = None
        key.exhaustion_count = 0
        key.last_error_at = None
        key.last_error_code = None
        key.enabled = True
        _key_store.save()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)




@dashboard_router.post("/dashboard/keys/enable-all")
async def enable_all_keys():
    """Enable all keys, including those marked as INVALID, resetting them to ACTIVE."""
    try:
        keys = _key_store.get_all()
        count = 0
        for key in keys:
            if not key.enabled or key.status in (KeyStatus.EXHAUSTED, KeyStatus.INVALID):
                key.enabled = True
                key.status = KeyStatus.ACTIVE
                count += 1
        if count > 0:
            _key_store.save()
        return JSONResponse({"success": True, "enabled_count": count})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.post("/dashboard/models")
async def add_model(request: Request):
    """Add a new model to the available models list."""
    try:
        body = await request.json()
        name = body.get("name", "").strip()
        tag = body.get("tag", "").strip()
        if not name or not tag:
            return JSONResponse({"error": "Both name and tag are required"}, status_code=400)

        models = _config.get("available_models", [])
        models.append({"name": name, "tag": tag, "enabled": True})
        _config.set("available_models", models)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.patch("/dashboard/models/{index}")
async def update_model(index: int, request: Request):
    """Update a model's properties at the given index."""
    try:
        body = await request.json()
        models = _config.get("available_models", [])
        if index < 0 or index >= len(models):
            return JSONResponse({"error": "Model index out of range"}, status_code=404)

        model = models[index]
        if "name" in body: model["name"] = body["name"]
        if "tag" in body: model["tag"] = body["tag"]
        if "enabled" in body: model["enabled"] = body["enabled"]

        _config.set("available_models", models)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@dashboard_router.delete("/dashboard/models/{index}")
async def delete_model(index: int):
    """Remove a model at the given index."""
    try:
        models = _config.get("available_models", [])
        if index < 0 or index >= len(models):
            return JSONResponse({"error": "Model index out of range"}, status_code=404)

        models.pop(index)
        _config.set("available_models", models)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
