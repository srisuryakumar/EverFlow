"""ResponseDetector: classifies API responses into ErrorType."""

import re
from typing import Optional

from src.models.enums import ErrorType


class ResponseDetector:
    """Classifies every API response into an ErrorType."""

    def classify(
        self,
        status_code: int,
        body: dict,
        headers: dict,
        exception: Exception = None,
    ) -> tuple[ErrorType, Optional[int]]:
        """
        Classify an API response.
        Returns: (ErrorType, retry_after_seconds_or_None)
        """
        # Handle network-level exceptions (no HTTP response)
        if exception is not None:
            exc_type = type(exception).__name__.lower()
            if "timeout" in exc_type:
                return (ErrorType.TIMEOUT, None)
            return (ErrorType.NETWORK_ERROR, None)

        # HTTP 200
        if status_code == 200:
            return (ErrorType.SUCCESS, None)

        # HTTP 429 — rate limit
        if status_code == 429:
            retry_after = self.extract_retry_after(headers, body)

            # Priority 1: Specific headers
            limit_type = str(headers.get("X-RateLimit-Type", "")).lower()
            if any(w in limit_type for w in ("daily", "quota")):
                return (ErrorType.DAILY_LIMIT_EXCEEDED, retry_after)

            # Priority 2: Long retry window (e.g., > 3600s) often indicates daily/quota limits
            if retry_after and retry_after > 3600:
                return (ErrorType.DAILY_LIMIT_EXCEEDED, retry_after)

            # Priority 3: Body heuristics (fallback)
            error_body = body.get("error", {}) if isinstance(body, dict) else {}
            msg = str(error_body.get("message", "")).lower()
            etype = str(error_body.get("type", "")).lower()
            ecode = str(error_body.get("code", "")).lower()
            combined = msg + etype + ecode
            if any(w in combined for w in ("quota", "exceeded", "daily", "billing", "limit", "capacity", "budget", "account", "exhausted", "too many requests", "throttled")):
                return (ErrorType.DAILY_LIMIT_EXCEEDED, retry_after)

            return (ErrorType.RATE_LIMITED, retry_after)

        # HTTP 401 / 403 — bad key
        if status_code in (401, 403):
            return (ErrorType.KEY_INVALID, None)

        # HTTP 400 — bad request
        if status_code == 400:
            return (ErrorType.BAD_REQUEST, None)

        # HTTP 5xx
        if status_code in (500, 502, 503, 529):
            return (ErrorType.SERVER_ERROR, None)

        # Unknown
        return (ErrorType.SERVER_ERROR, None)

    def extract_retry_after(self, headers: dict, body: dict) -> Optional[int]:
        """Extract retry delay in seconds from headers or body."""
        # Check headers (case-insensitive)
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in ("retry-after", "x-ratelimit-reset-requests"):
                try:
                    return int(float(str(value)))
                except (ValueError, TypeError):
                    pass

        # Parse body error message: "try again in 45.3s"
        if isinstance(body, dict):
            message = str(body.get("error", {}).get("message", ""))
            match = re.search(r"try again in (\d+(?:\.\d+)?)s", message, re.IGNORECASE)
            if match:
                return int(float(match.group(1))) + 1

        return None