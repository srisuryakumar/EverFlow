"""APIKey data model for EverFlow."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models.enums import KeyStatus


@dataclass
class APIKey:
    """Represents an Ollama cloud API key with metadata and status."""

    key_id: str
    api_key: str
    alias: str = ""
    enabled: bool = True
    status: KeyStatus = KeyStatus.ACTIVE
    weight: float = 1.0
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    exhaustion_count: int = 0
    total_requests: int = 0
    total_tokens: int = 0
    last_error_code: Optional[int] = None
    sequence_number: int = 0

    def is_available(self) -> bool:
        """Return True if this key is available for use."""
        if not self.enabled:
            return False
        if self.status == KeyStatus.ACTIVE:
            return True
        if self.status in (KeyStatus.EXHAUSTED, KeyStatus.COOLDOWN):
            if self.cooldown_until is not None:
                return datetime.now(timezone.utc) >= self.cooldown_until
        return False

    def masked_key(self) -> str:
        """Return a masked version of the API key for display."""
        k = self.api_key
        if len(k) <= 8:
            return "****"
        return f"{k[:4]}...{k[-4:]}"

    def display_name(self) -> str:
        """Return the display name for this key (alias or masked key)."""
        if self.alias:
            return self.alias
        return self.masked_key()

    def to_dict(self) -> dict:
        """Serialize this APIKey to a dictionary for JSON storage."""
        return {
            "key_id": self.key_id,
            "api_key": self.api_key,
            "alias": self.alias,
            "enabled": self.enabled,
            "status": self.status.value,
            "weight": self.weight,
            "added_at": self.added_at.isoformat() + "Z" if self.added_at else None,
            "last_used_at": self.last_used_at.isoformat() + "Z" if self.last_used_at else None,
            "last_success_at": self.last_success_at.isoformat() + "Z" if self.last_success_at else None,
            "last_error_at": self.last_error_at.isoformat() + "Z" if self.last_error_at else None,
            "cooldown_until": self.cooldown_until.isoformat() + "Z" if self.cooldown_until else None,
            "exhaustion_count": self.exhaustion_count,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "last_error_code": self.last_error_code,
            "sequence_number": self.sequence_number,
        }

    def to_dashboard_dict(self) -> dict:
        """Serialize for dashboard API with computed fields and masked key."""
        d = self.to_dict()
        d["api_key"] = self.masked_key()
        d["display_name"] = self.display_name()
        d["is_available"] = self.is_available()
        if self.cooldown_until is None:
            d["seconds_until_recovery"] = None
        else:
            d["seconds_until_recovery"] = max(
                0.0, (self.cooldown_until - datetime.now(timezone.utc)).total_seconds()
            )
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "APIKey":
        """Deserialize an APIKey from a dictionary (loaded from keys.json)."""
        def parse_datetime(s: Optional[str]) -> Optional[datetime]:
            if s is None:
                return None
            dt = datetime.fromisoformat(s.rstrip("Z"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        return cls(
            key_id=d.get("key_id", ""),
            api_key=d.get("api_key", ""),
            alias=d.get("alias", ""),
            enabled=d.get("enabled", True),
            status=KeyStatus(d.get("status", "active")),
            weight=d.get("weight", 1.0),
            added_at=parse_datetime(d.get("added_at")) or datetime.now(timezone.utc),
            last_used_at=parse_datetime(d.get("last_used_at")),
            last_success_at=parse_datetime(d.get("last_success_at")),
            last_error_at=parse_datetime(d.get("last_error_at")),
            cooldown_until=parse_datetime(d.get("cooldown_until")),
            exhaustion_count=d.get("exhaustion_count", 0),
            total_requests=d.get("total_requests", 0),
            total_tokens=d.get("total_tokens", 0),
            last_error_code=d.get("last_error_code"),
            sequence_number=d.get("sequence_number", 0),
        )