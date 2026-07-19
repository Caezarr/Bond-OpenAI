from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class CallStatus(StrEnum):
    PREPARED = "prepared"
    DIALING = "dialing"
    RINGING = "ringing"
    CONNECTED = "connected"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    CallStatus.COMPLETED,
    CallStatus.REJECTED,
    CallStatus.FAILED,
    CallStatus.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class CallRequest:
    to: str
    intent: str
    consent: bool
    confirmed: bool
    profile: str
    demo_session_id: str
    expires_at: str


@dataclass(slots=True)
class CallRecord:
    call_id: str
    destination_hint: str
    intent: str
    status: CallStatus = CallStatus.PREPARED
    twilio_sid: str | None = None
    outcome: dict[str, Any] | None = None
    transcript: list[dict[str, str]] = field(default_factory=list)
    error_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        result.pop("twilio_sid", None)
        return result
