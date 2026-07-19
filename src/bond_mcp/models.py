from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class TaskState(StrEnum):
    DETECTED = "detected"
    NEEDS_INPUT = "needs_input"
    READY_FOR_REVIEW = "ready_for_review"
    CONFIRMED = "confirmed"
    DIALING = "dialing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    DECLINED = "declined"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {
        TaskState.COMPLETED,
        TaskState.NO_ANSWER,
        TaskState.DECLINED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    }
)


@dataclass(frozen=True, slots=True)
class PhoneTask:
    task_id: str
    caller_identity: str
    destination_phone: str
    call_goal: str
    consent_confirmed: bool
    language: str = "en"
    timezone: str = "Europe/Brussels"
    idempotency_key: str = ""
    confirmed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PhoneResult:
    task_id: str
    call_id: str
    status: TaskState
    outcome: str | None = None
    summary: str | None = None
    provider_call_id: str | None = None
    recorded: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        result.pop("provider_call_id", None)
        return result
