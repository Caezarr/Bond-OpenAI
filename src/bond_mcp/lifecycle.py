"""Provider-neutral phone task lifecycle.

This is the single place where a validated :class:`PhoneTask` becomes a carrier
call. Both transports (the local stdio MCP adapter and the operator-hosted demo
relay) delegate here, so the safety ordering below holds for every entry point:

1. the caller builds the task through ``policy.build_task`` (allowlist, consent,
   E.164, language, goal length);
2. an unconfirmed task only ever yields a preview;
3. ``TaskStore.reserve`` enforces idempotency and the one-active-call limit
   before the provider is touched;
4. the provider is called at most once per reservation; a provider failure is
   persisted as ``failed`` and never retried automatically.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .models import TERMINAL_STATES, PhoneResult, PhoneTask, TaskState
from .policy import Policy, PolicyError
from .store import ActiveCall, IdempotencyConflict, TaskStore

# Status values sent by Twilio status callbacks.
TWILIO_CALLBACK_STATES: Mapping[str, TaskState] = {
    "queued": TaskState.DIALING,
    "initiated": TaskState.DIALING,
    "ringing": TaskState.DIALING,
    "in-progress": TaskState.IN_PROGRESS,
    "completed": TaskState.COMPLETED,
    "busy": TaskState.DECLINED,
    "no-answer": TaskState.NO_ANSWER,
    "canceled": TaskState.CANCELLED,
    "failed": TaskState.FAILED,
}

# Status values returned by any PhoneProvider.get_status: Twilio values plus the
# snake_case TaskState values the demo relay echoes back.
PROVIDER_STATES: Mapping[str, TaskState] = {
    **TWILIO_CALLBACK_STATES,
    "dialing": TaskState.DIALING,
    "in_progress": TaskState.IN_PROGRESS,
    "no_answer": TaskState.NO_ANSWER,
    "cancelled": TaskState.CANCELLED,
}


class PhoneProvider(Protocol):
    """Port implemented by every carrier adapter (see ``providers.py``)."""

    async def create_call(self, task: PhoneTask, call_id: str) -> str: ...

    async def get_status(self, provider_call_id: str) -> str: ...

    async def cancel_call(self, provider_call_id: str) -> None: ...


class ProviderFailed(RuntimeError):
    """The provider rejected a reserved call. The task is already marked failed."""


def error_code(exc: PolicyError | IdempotencyConflict | ActiveCall) -> str:
    """Stable machine-readable code for a rejected request."""
    if isinstance(exc, PolicyError):
        return exc.code
    if isinstance(exc, IdempotencyConflict):
        return "idempotency_conflict"
    return "call_busy"


@dataclass(slots=True)
class PhoneTaskService:
    policy: Policy
    store: TaskStore
    provider: PhoneProvider

    def preview(self, task: PhoneTask) -> dict[str, Any]:
        """Describe exactly what would be dialed. Never touches the provider."""
        return {
            "destination_phone": task.destination_phone,
            "caller_identity": task.caller_identity,
            "call_goal": task.call_goal,
            "recorded": False,
            "max_duration_seconds": self.policy.max_duration_seconds,
        }

    async def dial(self, task: PhoneTask) -> tuple[PhoneResult, bool]:
        """Place a confirmed task. Returns ``(result, replayed)``.

        Raises ``PolicyError`` for an unconfirmed task and ``IdempotencyConflict``
        or ``ActiveCall`` from the store, all before any provider call, and
        ``ProviderFailed`` after recording the failure.
        """
        if not task.confirmed:
            raise PolicyError("confirmation_required", "A confirmed preview is required")
        call_id, result, replayed = self.store.reserve(task)
        if replayed:
            # Exact replay: return the stored outcome, never redial.
            return result, True
        try:
            result.provider_call_id = await self.provider.create_call(task, call_id)
        except Exception as exc:
            result.status = TaskState.FAILED
            result.error = "phone provider rejected the call"
            self.store.update(result)
            raise ProviderFailed(str(exc)) from exc
        result.status = TaskState.DIALING
        self.store.update(result)
        return result, False

    async def status(self, call_id: str) -> PhoneResult | None:
        """Return the stored result, refreshed from the provider when still active."""
        result = self.store.get(call_id)
        if result is None:
            return None
        if not result.provider_call_id or result.status in TERMINAL_STATES:
            return result
        try:
            provider_status = await self.provider.get_status(result.provider_call_id)
        except Exception:
            # A status lookup failure is not a call outcome; keep the last known state.
            return result
        mapped = PROVIDER_STATES.get(provider_status)
        if mapped and mapped != result.status:
            result.status = mapped
            self.store.update(result)
        return result

    async def cancel(self, call_id: str) -> PhoneResult | None:
        """Cancel an active task. Terminal tasks are returned unchanged."""
        result = self.store.get(call_id)
        if result is None:
            return None
        if result.status not in TERMINAL_STATES:
            if result.provider_call_id:
                await self.provider.cancel_call(result.provider_call_id)
            result.status = TaskState.CANCELLED
            self.store.update(result)
        return result
