"""Vendor-neutral outbound action payloads.

The phone MCP never calls Google, Odoo or any calendar vendor itself. When a
call completes with structured, confirmed details, it emits a machine-readable
action (e.g. calendar.create_event) that the orchestrating agent forwards to
whatever calendar MCP exists. This keeps the phone MCP transport-neutral.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .models import PhoneResult, PhoneTask, TaskState

DEFAULT_EVENT_MINUTES = 60


def _end_iso(start_iso: str, minutes: int = DEFAULT_EVENT_MINUTES) -> str | None:
    try:
        start = datetime.fromisoformat(start_iso)
    except (TypeError, ValueError):
        return None
    return (start + timedelta(minutes=minutes)).isoformat()


def build_next_actions(
    task: PhoneTask | None, result: PhoneResult
) -> list[dict[str, Any]]:
    """Derive outbound actions from a completed call.

    Only a completed call with structured details that were not declined yields
    an action. The payload is a suggestion; the agent decides whether to run it.
    """
    if result.status != TaskState.COMPLETED:
        return []
    details = result.details or {}
    if not isinstance(details, dict):
        return []
    status = str(details.get("status", "")).strip().lower()
    if status == "declined":
        return []
    start_iso = str(details.get("datetime_iso", "")).strip()
    if not start_iso:
        return []

    name = str(details.get("name", "")).strip()
    location = str(details.get("location", "")).strip()
    goal = (task.call_goal if task else "").strip()
    title = goal[:120] or (f"Reservation for {name}" if name else "Phone task")

    event: dict[str, Any] = {"title": title, "start": start_iso}
    end = _end_iso(start_iso)
    if end:
        event["end"] = end
    if location:
        event["location"] = location
    party_size = details.get("party_size")
    if isinstance(party_size, int):
        event["party_size"] = party_size
    notes = (result.summary or result.answer or "").strip()
    if notes:
        event["notes"] = notes[:1000]

    return [{"type": "calendar.create_event", "event": event}]
