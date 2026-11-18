"""Demo relay: bearer auth, confirmation-only creation, status refresh."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes import ALLOWED, FakeProvider, task_payload
from starlette.testclient import TestClient

from bond_mcp.demo_relay import DemoRelay, RelayRateLimiter
from bond_mcp.store import TaskStore
from fredo.settings import Settings

AUTH = {"Authorization": "Bearer public-demo"}


@pytest.fixture
def relay(tmp_path: Path, provider: FakeProvider) -> DemoRelay:
    settings = Settings(
        telephony_provider="mock",
        demo_access_token="public-demo",
        allowed_numbers=frozenset({ALLOWED}),
        state_dir=tmp_path,
    )
    return DemoRelay(settings, TaskStore(tmp_path / "relay.sqlite3"), provider)


def _body(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {"confirmed": True, "idempotency_key": "relay-key", **overrides}
    return {"task": task_payload(**values)}


def test_relay_requires_token_and_refreshes_status(relay: DemoRelay, provider: FakeProvider) -> None:
    provider.status = "completed"
    with TestClient(relay.app()) as client:
        assert client.post("/v1/calls", json=_body()).status_code == 401
        created = client.post("/v1/calls", json=_body(), headers=AUTH)
        assert created.status_code == 200
        call_id = created.json()["call_id"]
        status = client.get(f"/v1/calls/{call_id}", headers=AUTH)
        assert status.json()["status"] == "completed"
        assert client.get("/v1/calls/unknown", headers=AUTH).status_code == 404


def test_relay_refuses_unconfirmed_task(relay: DemoRelay, provider: FakeProvider) -> None:
    with TestClient(relay.app()) as client:
        response = client.post("/v1/calls", json=_body(confirmed=False), headers=AUTH)
    assert response.status_code == 409
    assert response.json()["error"] == "confirmation_required"
    assert provider.created == []


def test_relay_reapplies_allowlist(relay: DemoRelay, provider: FakeProvider) -> None:
    with TestClient(relay.app()) as client:
        response = client.post(
            "/v1/calls", json=_body(destination_phone="+33600000999"), headers=AUTH
        )
    assert response.json()["error"] == "destination_not_allowed"
    assert provider.created == []


def test_relay_maps_provider_failure_to_502(relay: DemoRelay, provider: FakeProvider) -> None:
    provider.fail_create = True
    with TestClient(relay.app()) as client:
        response = client.post("/v1/calls", json=_body(), headers=AUTH)
    assert response.status_code == 502
    assert response.json() == {"error": "provider_unavailable"}


def test_relay_rejects_malformed_body(relay: DemoRelay) -> None:
    with TestClient(relay.app()) as client:
        response = client.post("/v1/calls", json=["not", "an", "object"], headers=AUTH)
    assert response.status_code == 400


def test_relay_cancel(relay: DemoRelay, provider: FakeProvider) -> None:
    with TestClient(relay.app()) as client:
        call_id = client.post("/v1/calls", json=_body(), headers=AUTH).json()["call_id"]
        cancelled = client.post(f"/v1/calls/{call_id}/cancel", headers=AUTH)
    assert cancelled.json()["status"] == "cancelled"
    assert provider.cancelled == [f"provider-{call_id}"]


def test_rate_limiter_blocks_after_budget() -> None:
    limiter = RelayRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("k") and limiter.allow("k")
    assert limiter.allow("k") is False
    assert limiter.allow("other") is True


def test_relay_refuses_to_start_without_token() -> None:
    with pytest.raises(ValueError, match="FREDO_DEMO_ACCESS_TOKEN"):
        DemoRelay.from_settings(Settings(telephony_provider="real"))
