"""Custom exceptions for EverFlow."""

from typing import Optional


class AllKeysExhaustedException(Exception):
    """Raised when all available API keys are exhausted or invalid."""

    def __init__(self, total_keys: int):
        self.total_keys = total_keys
        super().__init__(f"All {total_keys} Ollama keys are exhausted or invalid.")


class KeyInvalidException(Exception):
    """Raised when an API key is permanently invalid."""

    def __init__(self, key_id: str, http_status: int):
        self.key_id = key_id
        self.http_status = http_status
        super().__init__(f"Key '{key_id}' is permanently invalid (HTTP {http_status}).")


class MaxRetriesExceededException(Exception):
    """Raised when a request exceeds the maximum retry attempts."""

    def __init__(self, request_id: str, attempts: int):
        self.request_id = request_id
        self.attempts = attempts
        super().__init__(f"Request '{request_id}' failed after {attempts} attempts.")


class RateLimitException(Exception):
    """Raised when an API key hits a rate limit."""

    def __init__(self, key_id: str, retry_after: Optional[int]):
        self.key_id = key_id
        self.retry_after = retry_after
        super().__init__(f"Key '{key_id}' hit rate limit. Retry after: {retry_after}s")


class ConfigNotFoundException(Exception):
    """Raised when the configuration file cannot be found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Config file not found: {path}")