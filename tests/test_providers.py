"""Provider adapters: the demo client never carries provider credentials."""

from __future__ import annotations

import httpx
import pytest
from fakes import ALLOWED, task_payload

from bond_mcp.policy import Policy, build_task
from bond_mcp.providers import DemoProvider, FredoProvider, provider_from_settings
from fredo.models import CallRequest
from fredo.settings import Settings


async def test_demo_provider_keeps_provider_keys_out_of_client_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/calls":
            return httpx.Response(200, json={"call_id": "remote-1"})
        if request.method == "GET":
            return httpx.Response(200, json={"status": "completed"})
        return httpx.Response(200, json={"status": "cancelled"})

    provider = DemoProvider(
        "https://relay.example", "public-demo", transport=httpx.MockTransport(handler)
    )
    task = build_task(
        task_payload(confirmed=True, idempotency_key="demo-key"), Policy(frozenset({ALLOWED}))
    )
    assert await provider.create_call(task, "local-1") == "remote-1"
    assert await provider.get_status("remote-1") == "completed"
    await provider.cancel_call("remote-1")
    assert all(request.headers["authorization"] == "Bearer public-demo" for request in requests)
    assert all("DEEPGRAM" not in str(request.content) for request in requests)


async def test_demo_provider_rejects_invalid_receipt() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={})

    provider = DemoProvider("https://relay.example", transport=httpx.MockTransport(handler))
    task = build_task(task_payload(confirmed=True), Policy(frozenset({ALLOWED})))
    with pytest.raises(RuntimeError, match="invalid call receipt"):
        await provider.create_call(task, "local-1")


async def test_fredo_provider_passes_only_destination_and_goal() -> None:
    seen: list[tuple[CallRequest, str]] = []

    class RecordingTelephony:
        async def place_call(self, request: CallRequest, call_id: str) -> str:
            seen.append((request, call_id))
            return "CA1"

        async def get_status(self, provider_call_id: str) -> str:
            return "ringing"

        async def hangup(self, provider_call_id: str) -> None:
            return None

    provider = FredoProvider(Settings(), RecordingTelephony())
    task = build_task(task_payload(confirmed=True), Policy(frozenset({ALLOWED})))
    assert await provider.create_call(task, "local-1") == "CA1"
    assert seen == [(CallRequest(to=ALLOWED, intent="Reserve a table"), "local-1")]


def test_provider_selection() -> None:
    demo = provider_from_settings(
        Settings(telephony_provider="demo", demo_endpoint="https://relay.example")
    )
    assert isinstance(demo, DemoProvider)
    assert isinstance(provider_from_settings(Settings(telephony_provider="mock")), FredoProvider)
    with pytest.raises(ValueError, match="FREDO_DEMO_ENDPOINT"):
        provider_from_settings(Settings(telephony_provider="demo"))
