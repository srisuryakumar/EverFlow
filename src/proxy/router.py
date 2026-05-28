"""ProxyRouter: coordinates key rotation, API calls, and retry logic."""

import asyncio
import threading
import time
import uuid
import json
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional

from src.config.manager import ConfigManager
from src.exceptions import AllKeysExhaustedException, MaxRetriesExceededException
from src.keys.rotator import KeyRotator
from src.keys.store import KeyStore
from src.models.enums import ErrorType, RequestOutcome
from src.models.request_log import RequestLog
from src.proxy.detector import ResponseDetector
from src.proxy.ollama_client import OllamaClient


# Mapping from Anthropic model names to Ollama Cloud model names
# This is now handled via ConfigManager in DEFAULT_CONFIG

class ProxyRouter:
    """Routes requests through the key rotation engine with retry logic."""

    def __init__(
        self,
        key_store: KeyStore,
        rotator: KeyRotator,
        detector: ResponseDetector,
        client: OllamaClient,
        config: ConfigManager,
    ):
        """Initialize the ProxyRouter."""
        self._key_store = key_store
        self._rotator = rotator
        self._detector = detector
        self._client = client
        self._config = config
        # Thread-safe stats
        self._lock = asyncio.Lock()
        self._logs: deque = deque(maxlen=500)
        self._total_requests: int = 0
        self._successful_requests: int = 0
        self._failed_requests: int = 0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_tokens: int = 0
        self._started_at: datetime = datetime.now(timezone.utc)
        self._latency_samples: deque = deque(maxlen=100)
        # Cache for dashboard data to reduce locking
        self._summary_cache: Optional[dict] = None
        self._summary_cache_time: Optional[datetime] = None
        self._summary_cache_ttl = timedelta(seconds=5)  # Cache for 5 seconds
        # Track active requests per key
        self._active_requests: dict[str, int] = {}

    def _translate_model(self, requested_model: str) -> str:
        """Translate Anthropic model name to Ollama Cloud model name using config."""
        model_map = self._config.get("ollama.model_map", {})
        default_model = self._config.get("ollama.default_model", "gemma4:31b-cloud")

        # 1. Check if it's in the mapping
        if requested_model in model_map:
            mapped_model = model_map[requested_model]
            # If mapped to the base default, use the current dynamic default
            if mapped_model == "gemma4:31b-cloud":
                return default_model
            return mapped_model

        # 2. Check if it's already an Ollama tag (contains ':')
        if ":" in requested_model:
            return requested_model

        # 3. Fallback to current default model
        return default_model

    async def get_active_key_ids(self) -> list[str]:
        """Return IDs of keys currently handling requests."""
        async with self._lock:
            return [kid for kid, count in self._active_requests.items() if count > 0]

    async def route(self, payload: dict) -> dict:
        """
        Route a non-streaming request through the key rotation engine.
        Tries each available key up to max_retries times in a single pool cycle.
        Returns the successful Anthropic-format response dict.
        """
        request_id = str(uuid.uuid4())
        requested_model = payload.get("model", "")
        model = self._translate_model(requested_model)

        payload = {**payload, "model": model}
        if "max_tokens" in payload and payload["max_tokens"] > 32768:
            payload["max_tokens"] = 32768

        max_retries_per_key = self._config.get("rotation.max_retries", 3)
        tried_keys: list[str] = []
        total_attempts = 0
        last_error: Optional[str] = None
        last_key: Optional[any] = None

        while True:
            # --- Select next available key ---
            try:
                key = await self._rotator.get_next_key(exclude=tried_keys)
                last_key = key
            except AllKeysExhaustedException:
                # Full pool cycle complete (all keys tried max_retries_per_key times)
                await self._record_log(
                    request_id, model, None, None,
                    RequestOutcome.ALL_KEYS_EXHAUSTED, None, 0, 0, total_attempts, "All keys exhausted"
                )
                await self._update_stats(success=False)
                raise MaxRetriesExceededException(request_id, total_attempts)

            tried_keys.append(key.key_id)

            # --- Per-key patience loop ---
            for key_attempt in range(1, max_retries_per_key + 1):
                total_attempts += 1
                start = time.monotonic()

                try:
                    async with self._lock:
                        self._active_requests[key.key_id] = self._active_requests.get(key.key_id, 0) + 1

                    try:
                        status, body, headers = await self._client.call(key.api_key, payload)
                    finally:
                        async with self._lock:
                            self._active_requests[key.key_id] -= 1
                            if self._active_requests[key.key_id] <= 0:
                                del self._active_requests[key.key_id]
                except Exception as exc:
                    latency = (time.monotonic() - start) * 1000
                    error_type, _ = self._detector.classify(0, {}, {}, exception=exc)
                    await self._rotator.record_failure(key.key_id, error_type, 0)

                    if error_type in (ErrorType.KEY_INVALID, ErrorType.DAILY_LIMIT_EXCEEDED):
                        last_error = str(exc)
                        break # Skip to next key immediately

                    wait = self._rotator.calculate_backoff(total_attempts)
                    last_error = str(exc)
                    await asyncio.sleep(wait)
                    continue # Retry same key

                latency = (time.monotonic() - start) * 1000
                error_type, retry_after = self._detector.classify(status, body, headers)

                if error_type == ErrorType.SUCCESS:
                    usage = body.get("usage", {}) if isinstance(body, dict) else {}
                    input_t = usage.get("input_tokens", 0)
                    output_t = usage.get("output_tokens", 0)
                    total_t = input_t + output_t
                    await self._rotator.record_success(key.key_id, total_t, latency)
                    await self._record_log(
                        request_id, model, key.masked_key(), key.display_name(),
                        RequestOutcome.SUCCESS, latency, input_t, output_t, total_attempts
                    )
                    await self._update_stats(success=True, input_tokens=input_t, output_tokens=output_t, latency=latency)
                    return body

                elif error_type == ErrorType.BAD_REQUEST:
                    await self._record_log(
                        request_id, model, key.masked_key(), key.display_name(),
                        RequestOutcome.BAD_REQUEST, latency, 0, 0, total_attempts, str(body)
                    )
                    await self._update_stats(success=False)
                    return body

                elif error_type in (ErrorType.RATE_LIMITED, ErrorType.DAILY_LIMIT_EXCEEDED):
                    await self._rotator.record_failure(key.key_id, error_type, status, retry_after)
                    last_error = f"HTTP {status} rate limited"
                    if error_type == ErrorType.DAILY_LIMIT_EXCEEDED:
                        break # Skip to next key immediately

                    # For standard rate limit, wait and retry same key
                    wait = self._rotator.calculate_backoff(total_attempts)
                    await asyncio.sleep(wait)
                    continue

                elif error_type == ErrorType.KEY_INVALID:
                    await self._rotator.record_failure(key.key_id, error_type, status)
                    last_error = f"HTTP {status} key invalid"
                    break # Skip to next key immediately

                else:  # SERVER_ERROR / TIMEOUT / NETWORK
                    await self._rotator.record_failure(key.key_id, error_type, status)
                    last_error = f"HTTP {status} server error"
                    wait = self._rotator.calculate_backoff(total_attempts)
                    await asyncio.sleep(wait)
                    continue # Retry same key

            # If inner loop completes without return or break, it means max_retries_per_key was hit
            # the outer loop will then pick the next key.

    async def route_stream(self, payload: dict) -> AsyncGenerator[bytes, None]:
        """Stream a request through the key rotation engine with retries for connection errors."""
        request_id = str(uuid.uuid4())
        requested_model = payload.get("model", "")
        model = self._translate_model(requested_model)
        payload = {**payload, "model": model}

        if "max_tokens" in payload and payload["max_tokens"] > 32768:
            payload["max_tokens"] = 32768

        max_retries_per_key = self._config.get("rotation.max_retries", 3)
        tried_keys: list[str] = []
        total_attempts = 0
        last_error: Optional[str] = None
        last_key: Optional[any] = None

        while True:
            try:
                key = await self._rotator.get_next_key(exclude=tried_keys)
                last_key = key
            except AllKeysExhaustedException:
                await self._record_log(
                    request_id, model, None, None,
                    RequestOutcome.ALL_KEYS_EXHAUSTED, None, 0, 0, total_attempts, "All keys exhausted"
                )
                await self._update_stats(success=False)
                raise MaxRetriesExceededException(request_id, total_attempts)

            tried_keys.append(key.key_id)

            for key_attempt in range(1, max_retries_per_key + 1):
                total_attempts += 1
                start = time.monotonic()
                input_t, output_t = 0, 0

                try:
                    # Create the stream generator
                    stream = self._client.stream(key.api_key, payload)

                    def extract_usage(chunk: bytes):
                        nonlocal input_t, output_t
                        if b"usage" not in chunk:
                            return
                        try:
                            text = chunk.decode('utf-8')
                            for line in text.split('\n'):
                                if line.startswith('data: '):
                                    data_str = line[6:].strip()
                                    if not data_str: continue
                                    try:
                                        data_json = json.loads(data_str)
                                        if "usage" in data_json:
                                            u = data_json["usage"]
                                            input_t = u.get("input_tokens", u.get("prompt_tokens", 0))
                                            output_t = u.get("output_tokens", u.get("completion_tokens", 0))
                                    except json.JSONDecodeError:
                                        pass
                        except Exception:
                            pass

                    # Try to get the first chunk to verify the key/connection
                    try:
                        first_chunk = await stream.__anext__()
                        extract_usage(first_chunk)
                    except Exception as e:
                        raise e
                    except StopAsyncIteration:
                        latency = (time.monotonic() - start) * 1000
                        await self._record_log(request_id, model, key.masked_key(), key.display_name(), RequestOutcome.SUCCESS, latency, input_t, output_t, total_attempts)
                        await self._rotator.record_success(key.key_id, input_t + output_t, latency)
                        await self._update_stats(success=True, input_tokens=input_t, output_tokens=output_t, latency=latency)
                        return

                    # Success! Now yield the first chunk and the rest of the stream
                    yield first_chunk
                    try:
                        async for chunk in stream:
                            yield chunk
                            extract_usage(chunk)

                        latency = (time.monotonic() - start) * 1000
                        await self._record_log(request_id, model, key.masked_key(), key.display_name(), RequestOutcome.SUCCESS, latency, input_t, output_t, total_attempts)
                        await self._rotator.record_success(key.key_id, input_t + output_t, latency)
                        await self._update_stats(success=True, input_tokens=input_t, output_tokens=output_t, latency=latency)
                        return
                    except Exception as exc:
                        # If stream fails AFTER the first chunk, we cannot rotate keys
                        latency = (time.monotonic() - start) * 1000
                        error_type, _ = self._detector.classify(0, {}, {}, exception=exc)
                        await self._rotator.record_failure(key.key_id, error_type, 0)
                        outcome = RequestOutcome.SERVER_ERROR
                        if error_type == ErrorType.BAD_REQUEST: outcome = RequestOutcome.BAD_REQUEST
                        elif error_type == ErrorType.KEY_INVALID: outcome = RequestOutcome.KEY_INVALID
                        elif error_type in (ErrorType.RATE_LIMITED, ErrorType.DAILY_LIMIT_EXCEEDED): outcome = RequestOutcome.RATE_LIMITED

                        await self._record_log(request_id, model, key.masked_key(), key.display_name(), outcome, latency, input_t, output_t, total_attempts, str(exc))
                        raise exc

                except Exception as exc:
                    # This block handles failures that happened BEFORE the first chunk was yielded.
                    latency = (time.monotonic() - start) * 1000
                    error_type, retry_after = self._detector.classify(0, {}, {}, exception=exc)
                    await self._rotator.record_failure(key.key_id, error_type, 0, retry_after)
                    last_error = str(exc)

                    if error_type == ErrorType.BAD_REQUEST:
                        await self._record_log(request_id, model, key.masked_key(), key.display_name(), RequestOutcome.BAD_REQUEST, latency, input_t, output_t, total_attempts, last_error)
                        await self._update_stats(success=False)
                        raise

                    if error_type in (ErrorType.KEY_INVALID, ErrorType.DAILY_LIMIT_EXCEEDED):
                        # IMMEDIATE ROTATION
                        break

                    # SERVER_ERROR / TIMEOUT / NETWORK
                    wait = self._rotator.calculate_backoff(total_attempts)
                    await asyncio.sleep(wait)
                    continue # Retry same key

            # If inner loop completes without return or break, the outer loop continues to next key.

    async def get_recent_logs(self, limit: int = 100) -> list[dict]:
        """Return recent request logs as a list of dicts."""
        async with self._lock:
            logs = list(self._logs)
        recent = logs[-limit:]
        return [l.to_dict() for l in reversed(recent)]

    async def get_summary(self) -> dict:
        """Return aggregate statistics about the proxy."""
        # Use cache to reduce locking contention
        now = datetime.now(timezone.utc)
        if (self._summary_cache and self._summary_cache_time and
            (now - self._summary_cache_time) < self._summary_cache_ttl):
            return self._summary_cache

        async with self._lock:
            total = self._total_requests
            successful = self._successful_requests
            failed = self._failed_requests
            tokens = self._total_tokens
            input_t = self._total_input_tokens
            output_t = self._total_output_tokens
            samples = list(self._latency_samples)
        success_rate = round(successful / total * 100, 1) if total > 0 else 0.0
        avg_latency = round(sum(samples) / len(samples), 1) if samples else 0.0
        uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        summary = {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "total_tokens": tokens,
            "total_input_tokens": input_t,
            "total_output_tokens": output_t,
            "uptime_seconds": round(uptime, 0),
            "started_at": self._started_at.isoformat(),
        }

        # Update cache
        self._summary_cache = summary
        self._summary_cache_time = now

        return summary

    async def get_requests_per_minute(self) -> list[dict]:
        """Last 30 minutes of request counts, bucketed by minute."""
        now = datetime.now(timezone.utc)
        buckets: dict[str, dict] = {}
        for i in range(29, -1, -1):
            minute = (now - timedelta(minutes=i)).strftime("%H:%M")
            buckets[minute] = {"minute": minute, "count": 0, "errors": 0}

        # Only process recent logs to improve performance
        async with self._lock:
            # Get only the last 100 logs (most recent) instead of all 500
            recent_logs = list(self._logs)[-100:]

        for log in recent_logs:
            minute = log.timestamp.strftime("%H:%M")
            if minute in buckets:
                buckets[minute]["count"] += 1
                if log.outcome != RequestOutcome.SUCCESS:
                    buckets[minute]["errors"] += 1
        return list(buckets.values())

    async def _record_log(
        self,
        request_id: str,
        model: str,
        key_masked: Optional[str],
        key_alias: Optional[str],
        outcome: RequestOutcome,
        latency_ms: Optional[float],
        input_tokens: int,
        output_tokens: int,
        attempts: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a request log entry."""
        log = RequestLog(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
            model_requested=model,
            key_used_masked=key_masked,
            key_alias=key_alias,
            outcome=outcome,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            attempts=attempts,
            error_message=error_message,
        )
        self._logs.append(log)

    async def _update_stats(
        self, success: bool, input_tokens: int = 0, output_tokens: int = 0, latency: float = None
    ) -> None:
        """Update aggregate statistics."""
        async with self._lock:
            self._total_requests += 1
            if success:
                self._successful_requests += 1
                self._total_input_tokens += input_tokens
                self._total_output_tokens += output_tokens
                self._total_tokens += (input_tokens + output_tokens)
                if latency is not None:
                    self._latency_samples.append(latency)
            else:
                self._failed_requests += 1
        # Invalidate summary cache since stats changed
        self._summary_cache = None
        self._summary_cache_time = None