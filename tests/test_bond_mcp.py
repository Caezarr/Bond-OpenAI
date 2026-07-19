from __future__ import annotations

import asyncio
from pathlib import Path

from bond_mcp.policy import Policy, PolicyError, build_task, classify
from bond_mcp.server import McpServer
from bond_mcp.store import TaskStore
from fredo.settings import Settings


def test_classifies_phone_tasks_without_dialing() -> None:
    assert classify("Call the restaurant and confirm the reservation") == "phone_call"
    assert classify("Update the project document") == "not_phone_call"


def test_policy_requires_consent_and_exact_allowlist() -> None:
    policy = Policy(frozenset({"+33600000000"}))
    payload = {
        "task_id": "t1",
        "caller_identity": "Gab",
        "destination_phone": "+33600000000",
        "call_goal": "Reserve a table",
    }
    try:
        build_task(payload, policy)
    except PolicyError as exc:
        assert exc.code == "consent_required"
    else:
        raise AssertionError("missing consent must be rejected")


def test_store_replays_exact_idempotency(tmp_path: Path) -> None:
    policy = Policy(frozenset({"+33600000000"}))
    task = build_task(
        {
            "task_id": "t1",
            "caller_identity": "Gab",
            "destination_phone": "+33600000000",
            "call_goal": "Reserve a table",
            "consent_confirmed": True,
            "idempotency_key": "same-key",
            "confirmed": True,
        },
        policy,
    )
    store = TaskStore(tmp_path / "tasks.sqlite3")
    first = store.reserve(task)
    second = store.reserve(task)
    assert first[0] == second[0]
    assert second[2] is True


def test_mcp_initialize_and_tools_list(tmp_path: Path) -> None:
    server = McpServer(Settings(allowed_numbers=frozenset({"+33600000000"})), store_path=tmp_path / "tasks.sqlite3")
    initialized = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
    assert initialized["result"]["serverInfo"]["name"] == "bond-openai"
    listed = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert names == {
        "bond.classify_task",
        "bond.create_phone_task",
        "bond.get_phone_task_status",
        "bond.cancel_phone_task",
    }


def test_create_returns_preview_before_confirmation(tmp_path: Path) -> None:
    settings = Settings(allowed_numbers=frozenset({"+33600000000"}))
    server = McpServer(settings, store_path=tmp_path / "tasks.sqlite3")
    response = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "preview-key",
                        "task_input": {
                            "task_id": "t1",
                            "caller_identity": "Gab",
                            "destination_phone": "+33600000000",
                            "call_goal": "Reserve a table",
                            "consent_confirmed": True,
                        },
                    },
                },
            }
        )
    )
    data = response["result"]["structuredContent"]
    assert data["status"] == "needs_confirmation"
