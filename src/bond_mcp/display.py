"""Safe display projection for the Codex phone widget.

The widget (`codex-plugin/fredo/ui/phone-call.html`) renders from a `display`
object. This projection is deliberately free of full phone numbers, provider
IDs, raw audio and transcripts: only what the surface needs to show a call.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import TERMINAL_STATES, PhoneResult, PhoneTask, TaskState


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_destination(e164: str | None) -> str:
    digits = "".join(ch for ch in (e164 or "") if ch.isdigit())
    if len(digits) < 4:
        return ""
    cc = digits[:2] if (e164 or "").startswith("+") else ""
    prefix = f"+{cc} " if cc else ""
    return f"{prefix}•••• ••{digits[-2:]}"


def _phase(status: TaskState) -> str | None:
    if status == TaskState.DIALING:
        return "ringing"
    if status == TaskState.IN_PROGRESS:
        return "listening"
    return None


def _iso_to_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _elapsed_seconds(result: PhoneResult) -> int:
    start = _iso_to_epoch(result.connected_at)
    end = _iso_to_epoch(result.ended_at)
    if start and end:
        return max(0, int(end - start))
    if start and result.status == TaskState.IN_PROGRESS:
        return max(0, int(datetime.now(timezone.utc).timestamp() - start))
    return 0


def build_display(
    task: PhoneTask | None,
    result: PhoneResult,
    *,
    max_duration_seconds: int,
    live_listen_available: bool = False,
) -> dict[str, object]:
    terminal = result.status in TERMINAL_STATES
    return {
        "recipient_label": (task.recipient_label if task else None),
        "destination_masked": mask_destination(task.destination_phone if task else None),
        "call_goal": (task.call_goal if task else None),
        "language": (task.language if task else "en"),
        "max_duration_seconds": max_duration_seconds,
        "elapsed_seconds": _elapsed_seconds(result),
        "connected_at": result.connected_at,
        "ended_at": result.ended_at,
        "server_now": _now_iso(),
        "phase": _phase(result.status),
        "recorded": False,
        # Listen-only live audio requires the audio relay (Bloc B). Until it is
        # configured the widget hides the Listen control.
        "live_listen_available": bool(live_listen_available) and not terminal,
    }
