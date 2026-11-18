"""Offline test doubles and payload builders. Nothing here touches a network."""

from __future__ import annotations

from typing import Any

from bond_mcp.models import PhoneTask

# Obvious placeholders, never real subscribers.
ALLOWED = "+33600000000"
OTHER_ALLOWED = "+33600000001"
NOT_ALLOWED = "+33600000999"


def task_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": "t1",
        "caller_identity": "Gab",
        "destination_phone": ALLOWED,
        "call_goal": "Reserve a table",
        "consent_confirmed": True,
    }
    payload.update(overrides)
    return payload


class FakeProvider:
    """Records every carrier interaction so tests can assert on zero-call paths."""

    def __init__(self, *, status: str = "queued", fail_create: bool = False) -> None:
        self.status = status
        self.fail_create = fail_create
        self.created: list[tuple[PhoneTask, str]] = []
        self.cancelled: list[str] = []

    async def create_call(self, task: PhoneTask, call_id: str) -> str:
        self.created.append((task, call_id))
        if self.fail_create:
            raise RuntimeError("carrier rejected")
        return f"provider-{call_id}"

    async def get_status(self, provider_call_id: str) -> str:
        del provider_call_id
        return self.status

    async def cancel_call(self, provider_call_id: str) -> None:
        self.cancelled.append(provider_call_id)


def tool_call(name: str, arguments: dict[str, Any], request_id: int = 1) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def create_call(task_input: dict[str, Any], key: str = "key-1") -> dict[str, Any]:
    return tool_call(
        "bond.create_phone_task", {"idempotency_key": key, "task_input": task_input}
    )
