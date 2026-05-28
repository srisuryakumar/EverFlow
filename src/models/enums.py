"""Enumeration types for EverFlow."""

from enum import Enum


class KeyStatus(str, Enum):
    """Status of an API key."""

    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    COOLDOWN = "cooldown"
    INVALID = "invalid"
    DISABLED = "disabled"


class ErrorType(str, Enum):
    """Classification of an API response error."""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"
    KEY_INVALID = "key_invalid"
    SERVER_ERROR = "server_error"
    BAD_REQUEST = "bad_request"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"


class RequestOutcome(str, Enum):
    """Final outcome of a proxied request."""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    KEY_INVALID = "key_invalid"
    ALL_KEYS_EXHAUSTED = "all_keys_exhausted"
    SERVER_ERROR = "server_error"
    MAX_RETRIES = "max_retries"
    BAD_REQUEST = "bad_request"