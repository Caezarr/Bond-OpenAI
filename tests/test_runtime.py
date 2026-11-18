"""Carrier callback runtime: authentication and terminal-state protection."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes import ALLOWED, task_payload
from starlette.testclient import TestClient

from bond_mcp.models import TaskState
from bond_mcp.policy import Policy, build_task
from bond_mcp.runtime import create_runtime_app
from bond_mcp.store import TaskStore
from fredo.settings import Settings

SECRET = "local-endpoint-secret"


@pytest.fixture
def reserved(tmp_path: Path) -> tuple[TaskStore, str]:
    store = TaskStore(tmp_path / "runtime.sqlite3")
    task = build_task(task_payload(confirmed=True), Policy(frozenset({ALLOWED})))
    call_id, _, _ = store.reserve(task)
    return store, call_id


def _client(store: TaskStore, **settings: object) -> TestClient:
    app = create_runtime_app(
        Settings(telephony_provider="mock", endpoint_secret=SECRET, **settings),  # type: ignore[arg-type]
        store,
    )
    return TestClient(app)


def test_health(reserved: tuple[TaskStore, str]) -> None:
    store, _ = reserved
    assert _client(store).get("/healthz").json()["status"] == "ok"


def test_status_callback_requires_authentication(reserved: tuple[TaskStore, str]) -> None:
    store, call_id = reserved
    client = _client(store)
    url = f"/twilio/status?call_id={call_id}"
    assert client.post(url, data={"CallStatus": "completed"}).status_code == 401
    wrong = {"Authorization": "Bearer wrong"}
    assert client.post(url, data={"CallStatus": "completed"}, headers=wrong).status_code == 401
    forged = {"X-Twilio-Signature": "forged"}
    assert client.post(url, data={"CallStatus": "completed"}, headers=forged).status_code == 401
    assert store.get(call_id).status is TaskState.CONFIRMED  # type: ignore[union-attr]


def test_status_callback_updates_and_never_leaves_terminal(
    reserved: tuple[TaskStore, str],
) -> None:
    store, call_id = reserved
    client = _client(store)
    url = f"/twilio/status?call_id={call_id}"
    headers = {"Authorization": f"Bearer {SECRET}"}
    client.post(url, data={"CallStatus": "in-progress"}, headers=headers)
    assert store.get(call_id).status is TaskState.IN_PROGRESS  # type: ignore[union-attr]
    client.post(url, data={"CallStatus": "no-answer"}, headers=headers)
    client.post(url, data={"CallStatus": "in-progress"}, headers=headers)
    assert store.get(call_id).status is TaskState.NO_ANSWER  # type: ignore[union-attr]


def test_status_callback_unknown_call(reserved: tuple[TaskStore, str]) -> None:
    store, _ = reserved
    response = _client(store).post("/twilio/status?call_id=nope", data={"CallStatus": "completed"})
    assert response.status_code == 404


def test_media_stream_rejects_unsigned_connection(reserved: tuple[TaskStore, str]) -> None:
    from starlette.websockets import WebSocketDisconnect

    store, _ = reserved
    client = _client(store, twilio_auth_token="token", public_url="https://runtime.example")
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/twilio/media"):
        pass
    assert exc.value.code == 1008
