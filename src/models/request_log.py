"""RequestLog data model for EverFlow."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.models.enums import RequestOutcome


@dataclass
class RequestLog:
    """Represents a log entry for a proxied API request."""

    request_id: str
    timestamp: datetime
    model_requested: str
    key_used_masked: Optional[str]
    key_alias: Optional[str]
    outcome: RequestOutcome
    latency_ms: Optional[float]
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    attempts: int = 1
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize this RequestLog to a dictionary for JSON response."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "model_requested": self.model_requested,
            "key_used_masked": self.key_used_masked,
            "key_alias": self.key_alias,
            "outcome": self.outcome.value,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "attempts": self.attempts,
            "error_message": self.error_message,
        }