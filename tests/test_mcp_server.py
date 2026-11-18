"""MCP adapter: JSON-RPC envelope, tool surface and error codes."""

from __future__ import annotations

from typing import Any

from fakes import NOT_ALLOWED, FakeProvider, create_call, task_payload, tool_call

from bond_mcp.server import McpServer


def _content(response: dict[str, Any] | None) -> dict[str, Any]:
    assert response is not None
    return response["result"]["structuredContent"]


async def test_initialize_and_tools_list(server: McpServer) -> None:
    initialized = await server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert initialized is not None
    assert initialized["result"]["serverInfo"]["name"] == "bond-openai"
    listed = await server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    assert {tool["name"] for tool in listed["result"]["tools"]} == {
        "bond.classify_task",
        "bond.create_phone_task",
        "bond.get_phone_task_status",
        "bond.cancel_phone_task",
    }


async def test_notifications_and_unknown_methods(server: McpServer) -> None:
    assert await server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    response = await server.handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})
    assert response is not None and response["error"]["code"] == -32601


async def test_classify_tool_never_dials(server: McpServer, provider: FakeProvider) -> None:
    response = await server.handle(
        tool_call("bond.classify_task", {"task_text": "Call +33600000000"})
    )
    assert _content(response) == {"classification": "phone_call"}
    assert provider.created == []


async def test_create_returns_preview_before_confirmation(
    server: McpServer, provider: FakeProvider
) -> None:
    data = _content(await server.handle(create_call(task_payload())))
    assert data["status"] == "needs_confirmation"
    assert data["preview"]["recorded"] is False
    assert provider.created == []


async def test_confirmed_task_calls_provider_once_and_replays(
    server: McpServer, provider: FakeProvider
) -> None:
    message = create_call(task_payload(confirmed=True), key="confirmed-once")
    first = _content(await server.handle(message))
    second = _content(await server.handle(message))
    assert first["status"] == "dialing"
    assert second["replayed"] is True
    assert len(provider.created) == 1


async def test_missing_idempotency_key_is_rejected(
    server: McpServer, provider: FakeProvider
) -> None:
    response = await server.handle(create_call(task_payload(confirmed=True), key="  "))
    assert response is not None and response["result"]["isError"] is True
    assert _content(response)["code"] == "idempotency_required"
    assert provider.created == []


async def test_non_allowlisted_destination_returns_error_code(
    server: McpServer, provider: FakeProvider
) -> None:
    payload = task_payload(destination_phone=NOT_ALLOWED, confirmed=True)
    data = _content(await server.handle(create_call(payload)))
    assert data["code"] == "destination_not_allowed"
    assert provider.created == []


async def test_conflict_busy_and_provider_failure_codes(
    server: McpServer, provider: FakeProvider
) -> None:
    await server.handle(create_call(task_payload(confirmed=True), key="k1"))
    changed = task_payload(confirmed=True, call_goal="Different goal")
    assert _content(await server.handle(create_call(changed, key="k1")))["code"] == (
        "idempotency_conflict"
    )
    assert _content(await server.handle(create_call(changed, key="k2")))["code"] == "call_busy"


async def test_provider_failure_surfaces_as_tool_error(
    server: McpServer, provider: FakeProvider
) -> None:
    provider.fail_create = True
    data = _content(await server.handle(create_call(task_payload(confirmed=True))))
    assert data["code"] == "provider_failed"


async def test_status_and_cancel_tools(server: McpServer, provider: FakeProvider) -> None:
    created = _content(await server.handle(create_call(task_payload(confirmed=True))))
    call_id = created["call_id"]
    status = _content(
        await server.handle(tool_call("bond.get_phone_task_status", {"call_id": call_id}))
    )
    assert status["status"] == "dialing"
    assert "provider_call_id" not in status
    cancelled = _content(
        await server.handle(tool_call("bond.cancel_phone_task", {"call_id": call_id}))
    )
    assert cancelled["status"] == "cancelled"
    missing = _content(
        await server.handle(tool_call("bond.cancel_phone_task", {"call_id": "nope"}))
    )
    assert missing["code"] == "not_found"
    unknown = _content(await server.handle(tool_call("bond.unknown", {})))
    assert unknown["code"] == "unknown_tool"
