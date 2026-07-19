from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from starlette.testclient import TestClient

from bond_mcp.cli import main
from bond_mcp.demo_relay import DemoRelay
from bond_mcp.policy import Policy, PolicyError, build_task, classify
from bond_mcp.providers import DemoProvider
from bond_mcp.runtime import _valid_twilio_signature
from bond_mcp.server import McpServer
from bond_mcp.store import IdempotencyConflict, TaskStore
from fredo.agent_config import build_agent_settings
from fredo.settings import Settings
from fredo.silence_monitor import SilenceMonitor


def test_twilio_websocket_signature_uses_exact_wss_url() -> None:
    from twilio.request_validator import RequestValidator

    token = "twilio-auth-token"
    signed_url = "wss://voice.example.test/fredo/twilio/media?region=ie1"
    signature = RequestValidator(token).compute_signature(signed_url, {})
    websocket = SimpleNamespace(url="wss://internal:8080/twilio/media?region=ie1")
    settings = Settings(
        twilio_auth_token=token,
        public_url="https://voice.example.test/fredo",
    )

    assert _valid_twilio_signature(settings, websocket, signature) is True


def test_classifies_phone_tasks_without_dialing() -> None:
    assert classify("Call the restaurant and confirm the reservation") == "needs_input"
    assert classify("Call +33600000000 and confirm the reservation") == "phone_call"
    assert classify("Update the project document") == "not_phone_call"


def test_policy_normalizes_allowlist_and_rejects_invalid_entries() -> None:
    assert Policy(frozenset({"+33 6 00 00 00 00"})).allowed_numbers == frozenset({"+33600000000"})
    try:
        Policy(frozenset({"not-a-number"}))
    except PolicyError as exc:
        assert exc.code == "invalid_destination"
    else:
        raise AssertionError("invalid allowlist entries must fail closed")


def test_voice_agent_uses_typed_language_for_greeting() -> None:
    settings = build_agent_settings(Settings(deepgram_api_key="test"), "Réserver une table", "fr")
    assert settings.agent.greeting.startswith("Bonjour")
    assert "Speak French" in settings.agent.think.prompt


def test_flux_endpointing_is_applied_to_listen_provider() -> None:
    settings = Settings(
        deepgram_api_key="test",
        eot_threshold=0.85,
        eot_timeout_ms=9000,
        eager_eot_threshold=0.4,
    )
    provider = build_agent_settings(settings, "Reserve a table", "en").agent.listen.provider
    dumped = provider.model_dump()
    assert dumped["eot_threshold"] == 0.85
    assert dumped["eot_timeout_ms"] == 9000
    assert dumped["eager_eot_threshold"] == 0.4


def test_flux_endpointing_omits_eager_when_unset() -> None:
    provider = build_agent_settings(
        Settings(deepgram_api_key="test"), "Reserve a table", "en"
    ).agent.listen.provider
    assert provider.model_dump().get("eager_eot_threshold") is None


def test_settings_reject_out_of_range_endpointing() -> None:
    try:
        Settings.from_env({"FREDO_EOT_THRESHOLD": "0.2", "FREDO_MAX_CONCURRENT_CALLS": "1"})
    except ValueError as exc:
        assert "FREDO_EOT_THRESHOLD" in str(exc)
    else:
        raise AssertionError("out-of-range EOT threshold must fail closed")


def test_fallback_summary_is_clear_and_transcript_free() -> None:
    from bond_mcp.summary import fallback_summary

    silent = fallback_summary(language="en", disclosure_delivered=True, user_turns=0)
    assert "connected" in silent.lower()
    assert "no audible response" in silent.lower()

    spoke_en = fallback_summary(language="en", disclosure_delivered=True, user_turns=3)
    assert "disclosure" in spoke_en.lower()
    assert "3 turn" in spoke_en

    spoke_fr = fallback_summary(language="fr", disclosure_delivered=False, user_turns=2)
    assert "parole" in spoke_fr.lower()
    assert "2 prise" in spoke_fr


def test_phone_result_carries_answer_and_works(tmp_path: Path) -> None:
    from bond_mcp.models import TaskState
    from bond_mcp.store import TaskStore

    policy = Policy(frozenset({"+33600000000"}))
    task = build_task(
        {
            "task_id": "t1",
            "caller_identity": "Gab",
            "destination_phone": "+33600000000",
            "call_goal": "Reserve a table",
            "consent_confirmed": True,
            "idempotency_key": "answer-key",
            "confirmed": True,
        },
        policy,
    )
    store = TaskStore(tmp_path / "tasks.sqlite3")
    call_id, result, _ = store.reserve(task)
    result.status = TaskState.COMPLETED
    result.works = True
    result.answer = "Table booked for four at nine"
    result.summary = "Reserved a table for four at 9 PM under Gab."
    store.update(result)
    reloaded = store.get(call_id)
    assert reloaded is not None
    assert reloaded.works is True
    assert reloaded.answer == "Table booked for four at nine"
    assert reloaded.as_dict()["summary"].startswith("Reserved")


def test_extended_calls_require_explicit_optin() -> None:
    try:
        Settings.from_env(
            {"FREDO_MAX_DURATION_SECONDS": "600", "FREDO_MAX_CONCURRENT_CALLS": "1"}
        )
    except ValueError as exc:
        assert "FREDO_ALLOW_EXTENDED_CALLS" in str(exc)
    else:
        raise AssertionError("durations above 180 must fail closed without opt-in")


def test_extended_calls_allowed_with_optin_and_hard_capped() -> None:
    settings = Settings.from_env(
        {
            "FREDO_MAX_DURATION_SECONDS": "600",
            "FREDO_ALLOW_EXTENDED_CALLS": "1",
            "FREDO_MAX_CONCURRENT_CALLS": "1",
        }
    )
    assert settings.max_duration_seconds == 600
    try:
        Settings.from_env(
            {
                "FREDO_MAX_DURATION_SECONDS": "99999",
                "FREDO_ALLOW_EXTENDED_CALLS": "1",
                "FREDO_MAX_CONCURRENT_CALLS": "1",
            }
        )
    except ValueError as exc:
        assert "3600" in str(exc)
    else:
        raise AssertionError("extended durations must remain hard-capped")


def test_forbidden_destinations_blocked_even_when_unlisted() -> None:
    from bond_mcp.policy import is_forbidden_destination

    assert is_forbidden_destination("+19005550000") is True
    assert is_forbidden_destination("+33899000000") is True
    assert is_forbidden_destination("+33612345678") is False

    policy = Policy(frozenset(), allow_unlisted=True, autoconfirm=True)
    try:
        build_task(
            {
                "task_id": "t",
                "caller_identity": "Gab",
                "destination_phone": "+1 900 555 0000",
                "call_goal": "x",
            },
            policy,
        )
    except PolicyError as exc:
        assert exc.code == "destination_forbidden"
    else:
        raise AssertionError("premium/emergency numbers must always be blocked")


def test_allow_unlisted_and_autoconfirm_build_task() -> None:
    policy = Policy(frozenset(), allow_unlisted=True, autoconfirm=True)
    task = build_task(
        {
            "task_id": "t",
            "caller_identity": "Gab",
            "destination_phone": "+33612345678",
            "call_goal": "Reserve a table",
            "destination_source": {
                "method": "browse",
                "url": "https://maps.example/x",
                "confidence": "high",
            },
        },
        policy,
    )
    assert task.confirmed is True
    assert task.consent_confirmed is True
    assert task.destination_source is not None
    assert task.destination_source["method"] == "browse"


def test_unlisted_off_still_requires_allowlist() -> None:
    policy = Policy(frozenset({"+33600000000"}))
    try:
        build_task(
            {
                "task_id": "t",
                "caller_identity": "Gab",
                "destination_phone": "+33612345678",
                "call_goal": "Reserve a table",
                "consent_confirmed": True,
            },
            policy,
        )
    except PolicyError as exc:
        assert exc.code == "destination_not_allowed"
    else:
        raise AssertionError("allowlist must still be enforced when unlisted is off")


def test_details_round_trip_through_store(tmp_path: Path) -> None:
    from bond_mcp.models import TaskState
    from bond_mcp.store import TaskStore

    policy = Policy(frozenset(), allow_unlisted=True, autoconfirm=True)
    task = build_task(
        {
            "task_id": "t",
            "caller_identity": "Gab",
            "destination_phone": "+33612345678",
            "call_goal": "Reserve a table",
            "idempotency_key": "details-key",
        },
        policy,
    )
    store = TaskStore(tmp_path / "tasks.sqlite3")
    call_id, result, _ = store.reserve(task)
    result.status = TaskState.COMPLETED
    result.details = {
        "datetime_iso": "2026-07-19T21:00:00+02:00",
        "party_size": 4,
        "status": "confirmed",
    }
    store.update(result)
    reloaded = store.get(call_id)
    assert reloaded is not None
    assert reloaded.details is not None
    assert reloaded.details["party_size"] == 4


def test_build_next_actions_calendar_event() -> None:
    from bond_mcp.actions import build_next_actions
    from bond_mcp.models import PhoneResult, TaskState

    policy = Policy(frozenset(), allow_unlisted=True, autoconfirm=True)
    task = build_task(
        {
            "task_id": "t",
            "caller_identity": "Gab",
            "destination_phone": "+33612345678",
            "call_goal": "Reserve a table for four at 9 PM",
        },
        policy,
    )
    result = PhoneResult(
        task_id="t",
        call_id="c1",
        status=TaskState.COMPLETED,
        summary="Reserved a table for four at nine.",
        details={
            "datetime_iso": "2026-07-19T21:00:00+02:00",
            "party_size": 4,
            "location": "Chez X",
            "status": "confirmed",
        },
    )
    actions = build_next_actions(task, result)
    assert actions[0]["type"] == "calendar.create_event"
    event = actions[0]["event"]
    assert event["start"] == "2026-07-19T21:00:00+02:00"
    assert event["end"] == "2026-07-19T22:00:00+02:00"
    assert event["party_size"] == 4
    assert event["location"] == "Chez X"
    assert "Reserved" in event["notes"]


def test_build_next_actions_skips_declined_and_missing() -> None:
    from bond_mcp.actions import build_next_actions
    from bond_mcp.models import PhoneResult, TaskState

    declined = PhoneResult(
        task_id="t",
        call_id="c1",
        status=TaskState.COMPLETED,
        details={"status": "declined", "datetime_iso": "2026-07-19T21:00:00+02:00"},
    )
    assert build_next_actions(None, declined) == []

    no_details = PhoneResult(task_id="t", call_id="c2", status=TaskState.COMPLETED, details=None)
    assert build_next_actions(None, no_details) == []

    not_terminal = PhoneResult(
        task_id="t",
        call_id="c3",
        status=TaskState.IN_PROGRESS,
        details={"datetime_iso": "2026-07-19T21:00:00+02:00"},
    )
    assert build_next_actions(None, not_terminal) == []


def test_auto_orchestration_dry_run(tmp_path: Path) -> None:
    from bond_mcp.models import TaskState

    settings = Settings(allow_unlisted_destinations=True, autoconfirm=True)
    server = McpServer(settings, store_path=tmp_path / "tasks.sqlite3")

    class FakeProvider:
        async def create_call(self, task, call_id):
            del task
            return f"prov-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "in-progress"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    server.provider = FakeProvider()

    created = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "auto-key",
                        "task_input": {
                            "task_id": "t1",
                            "caller_identity": "Gab",
                            "destination_phone": "+33612345678",
                            "call_goal": "Reserve a table for four at 9 PM",
                            "language": "fr",
                            "destination_source": {"method": "browse", "url": "https://maps.example/x"},
                        },
                    },
                },
            }
        )
    )
    data = created["result"]["structuredContent"]
    assert data["status"] == "dialing"
    call_id = data["call_id"]

    result = server.store.get(call_id)
    assert result is not None
    result.status = TaskState.COMPLETED
    result.summary = "Reserved a table for four at nine."
    result.details = {
        "datetime_iso": "2026-07-19T21:00:00+02:00",
        "party_size": 4,
        "status": "confirmed",
    }
    server.store.update(result)

    status = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bond.get_phone_task_status", "arguments": {"call_id": call_id}},
            }
        )
    )
    sdata = status["result"]["structuredContent"]
    assert sdata["next_actions"][0]["type"] == "calendar.create_event"

    actions = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "bond.get_task_actions", "arguments": {"call_id": call_id}},
            }
        )
    )
    adata = actions["result"]["structuredContent"]
    assert adata["next_actions"][0]["event"]["party_size"] == 4


def test_relay_full_auto_and_next_actions(tmp_path: Path) -> None:
    from starlette.testclient import TestClient

    from bond_mcp.demo_relay import DemoRelay
    from bond_mcp.models import TaskState

    settings = Settings(
        telephony_provider="mock",
        demo_access_token="token-token-token",
        allow_unlisted_destinations=True,
        autoconfirm=True,
        state_dir=tmp_path,
    )
    relay = DemoRelay.from_settings(settings)
    client = TestClient(relay.app())
    headers = {"authorization": "Bearer token-token-token"}
    body = {
        "task": {
            "task_id": "t1",
            "caller_identity": "Gab",
            "destination_phone": "+33612345678",
            "call_goal": "Reserve a table for four at 9 PM",
            "idempotency_key": "relay-key",
        }
    }
    created = client.post("/v1/calls", json=body, headers=headers)
    assert created.status_code == 200
    call_id = created.json()["call_id"]

    result = relay.store.get(call_id)
    assert result is not None
    result.status = TaskState.COMPLETED
    result.summary = "Reserved a table for four at nine."
    result.details = {
        "datetime_iso": "2026-07-19T21:00:00+02:00",
        "party_size": 4,
        "status": "confirmed",
    }
    relay.store.update(result)

    fetched = client.get(f"/v1/calls/{call_id}", headers=headers)
    assert fetched.status_code == 200
    actions = fetched.json()["next_actions"]
    assert actions[0]["type"] == "calendar.create_event"
    assert actions[0]["event"]["party_size"] == 4


def test_mask_destination() -> None:
    from bond_mcp.display import mask_destination

    assert mask_destination("+33612345678") == "+33 •••• ••78"
    assert mask_destination("") == ""
    assert mask_destination(None) == ""


def test_widget_resource_served(tmp_path: Path) -> None:
    server = McpServer(Settings(allowed_numbers=frozenset({"+33600000000"})), store_path=tmp_path / "t.sqlite3")
    init = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
    assert "resources" in init["result"]["capabilities"]

    listed = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/list"}))
    uris = {r["uri"] for r in listed["result"]["resources"]}
    assert "ui://fredo/phone-call-v2.html" in uris

    read = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": "ui://fredo/phone-call-v2.html"},
            }
        )
    )
    content = read["result"]["contents"][0]
    assert content["mimeType"] == "text/html;profile=mcp-app"
    assert "<!doctype html>" in content["text"].lower()

    unknown = asyncio.run(
        server.handle(
            {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "ui://nope"}}
        )
    )
    assert "error" in unknown


def test_create_phone_task_has_output_template(tmp_path: Path) -> None:
    server = McpServer(Settings(allowed_numbers=frozenset({"+33600000000"})), store_path=tmp_path / "t.sqlite3")
    tools = {tool["name"]: tool for tool in server.tools()}
    create = tools["bond.create_phone_task"]
    assert create["_meta"]["openai/outputTemplate"] == "ui://fredo/phone-call-v2.html"
    # The template must be attached only to create, never to status/cancel.
    assert "_meta" not in tools["bond.get_phone_task_status"]


def test_status_result_includes_display(tmp_path: Path) -> None:
    from bond_mcp.models import TaskState

    settings = Settings(allow_unlisted_destinations=True, autoconfirm=True, telephony_provider="mock")
    server = McpServer(settings, store_path=tmp_path / "t.sqlite3")

    class FakeProvider:
        async def create_call(self, task, call_id):
            del task
            return f"prov-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "in-progress"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    server.provider = FakeProvider()
    created = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "disp-key",
                        "task_input": {
                            "task_id": "t1",
                            "caller_identity": "Gab",
                            "destination_phone": "+33612345678",
                            "call_goal": "Reserve a table",
                            "recipient_label": "Chez X",
                        },
                    },
                },
            }
        )
    )
    display = created["result"]["structuredContent"]["display"]
    assert display["destination_masked"] == "+33 •••• ••78"
    assert display["recipient_label"] == "Chez X"
    assert display["recorded"] is False
    assert display["live_listen_available"] is False

    call_id = created["result"]["structuredContent"]["call_id"]
    result = server.store.get(call_id)
    result.status = TaskState.IN_PROGRESS
    result.connected_at = "2026-07-19T21:00:00+00:00"
    server.store.update(result)
    status = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bond.get_phone_task_status", "arguments": {"call_id": call_id}},
            }
        )
    )
    sdisplay = status["result"]["structuredContent"]["display"]
    assert sdisplay["connected_at"] == "2026-07-19T21:00:00+00:00"
    assert sdisplay["phase"] == "listening"


def test_open_phone_audio_stream_unavailable(tmp_path: Path) -> None:
    settings = Settings(allow_unlisted_destinations=True, autoconfirm=True, telephony_provider="mock")
    server = McpServer(settings, store_path=tmp_path / "t.sqlite3")

    class FakeProvider:
        async def create_call(self, task, call_id):
            del task
            return f"prov-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "in-progress"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    server.provider = FakeProvider()
    created = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "audio-key",
                        "task_input": {
                            "task_id": "t1",
                            "caller_identity": "Gab",
                            "destination_phone": "+33612345678",
                            "call_goal": "Reserve a table",
                        },
                    },
                },
            }
        )
    )
    call_id = created["result"]["structuredContent"]["call_id"]
    audio = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bond.open_phone_audio_stream", "arguments": {"call_id": call_id}},
            }
        )
    )
    content = audio["result"]["structuredContent"]
    assert content["status"] == "unavailable"
    assert "audio_stream" not in json.dumps(audio)


def test_mulaw_decode_and_mix() -> None:
    from fredo.audio import _mix, mulaw_to_pcm16

    pcm = mulaw_to_pcm16(bytes([0x00]))
    assert pcm[0] < -30000  # 0x00 decodes to a large negative magnitude
    mixed = _mix(mulaw_to_pcm16(bytes([0x00])), mulaw_to_pcm16(bytes([0x00])))
    assert mixed[0] == -32768  # summed and hard-clipped


def test_audio_tokens_single_use_and_expiry() -> None:
    from fredo.audio import AudioTokenManager

    manager = AudioTokenManager(ttl_seconds=60)
    token, _ = manager.mint("c1")
    assert manager.consume(token) == "c1"
    assert manager.consume(token) is None  # single use

    expired = AudioTokenManager(ttl_seconds=-1)
    stale, _ = expired.mint("c2")
    assert expired.consume(stale) is None


def test_audio_tokens_prune_expired_entries() -> None:
    from fredo.audio import AudioTokenManager

    manager = AudioTokenManager(ttl_seconds=-1)
    manager.mint("expired")
    manager._ttl = 60
    manager.mint("live")
    assert len(manager._tokens) == 1


def test_audio_hub_mixes_and_streams() -> None:
    from fredo.audio import FRAME_BYTES, AudioHub

    async def scenario() -> bytes:
        hub = AudioHub()
        hub.publish("c1", "caller", bytes([0x00]) * 160)
        hub.publish("c1", "agent", bytes([0x00]) * 160)
        stream = hub.listen("c1")
        try:
            return await asyncio.wait_for(stream.__anext__(), timeout=1.0)
        finally:
            hub.close("c1")

    frame = asyncio.run(scenario())
    assert len(frame) == FRAME_BYTES


def test_audio_hub_absent_call_ends_stream() -> None:
    from fredo.audio import AudioHub

    async def scenario() -> list[bytes]:
        return [frame async for frame in AudioHub().listen("missing")]

    assert asyncio.run(scenario()) == []


def test_runtime_readiness_endpoint(tmp_path: Path, monkeypatch) -> None:
    import bond_mcp.runtime as runtime_mod
    from bond_mcp.runtime import create_runtime_app

    ready_settings = Settings(telephony_provider="mock")
    app = create_runtime_app(ready_settings, TaskStore(tmp_path / "ready.sqlite3"))
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

    monkeypatch.setattr(runtime_mod, "audio_encoding_available", lambda: False)
    not_ready = create_runtime_app(
        Settings(telephony_provider="mock", audio_stream_origin="https://audio.example.com"),
        TaskStore(tmp_path / "audio.sqlite3"),
    )
    response = TestClient(not_ready).get("/readyz")
    assert response.status_code == 503
    assert response.json()["audio"]["encoder_available"] is False


def test_doctor_flags_enabled_audio_without_encoder(monkeypatch) -> None:
    import bond_mcp.cli as cli_mod

    monkeypatch.setattr(cli_mod, "audio_encoding_available", lambda: False)
    summary = cli_mod._doctor_summary(
        Settings(telephony_provider="mock", audio_stream_origin="https://audio.example.com")
    )
    assert summary["audio_ready"] is False
    assert "lameenc (run: uv sync --frozen --extra audio)" in summary["missing"]


def test_doctor_demo_client_does_not_require_relay_encoder(monkeypatch) -> None:
    import bond_mcp.cli as cli_mod

    monkeypatch.setattr(cli_mod, "audio_encoding_available", lambda: False)
    summary = cli_mod._doctor_summary(
        Settings(
            telephony_provider="demo",
            demo_endpoint="https://relay.example.com",
            demo_access_token="demo-token",
            audio_stream_origin="https://relay.example.com",
        )
    )
    assert summary["audio_encoder_required"] is False
    assert summary["audio_ready"] is True
    assert not summary["missing"]


def test_settings_reject_non_https_audio_origin() -> None:
    try:
        Settings.from_env(
            {
                "FREDO_MAX_CONCURRENT_CALLS": "1",
                "FREDO_AUDIO_STREAM_ORIGIN": "http://audio.example.com",
            }
        )
    except ValueError as exc:
        assert "FREDO_AUDIO_STREAM_ORIGIN" in str(exc)
    else:
        raise AssertionError("audio origin must require HTTPS")


def test_open_phone_audio_stream_ready(tmp_path: Path, monkeypatch) -> None:
    import bond_mcp.server as server_mod
    from bond_mcp.models import TaskState
    from fredo.audio import get_audio_hub

    settings = Settings(
        allow_unlisted_destinations=True,
        autoconfirm=True,
        telephony_provider="mock",
        audio_stream_origin="https://relay.example.com",
    )
    server = McpServer(settings, store_path=tmp_path / "t.sqlite3")

    class FakeProvider:
        async def create_call(self, task, call_id):
            del task
            return f"prov-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "in-progress"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    server.provider = FakeProvider()
    created = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "audio-ready",
                        "task_input": {
                            "task_id": "t1",
                            "caller_identity": "Gab",
                            "destination_phone": "+33612345678",
                            "call_goal": "Reserve a table",
                        },
                    },
                },
            }
        )
    )
    call_id = created["result"]["structuredContent"]["call_id"]
    result = server.store.get(call_id)
    result.status = TaskState.IN_PROGRESS
    server.store.update(result)
    get_audio_hub().publish(call_id, "caller", bytes([0x00]) * 160)
    monkeypatch.setattr(server_mod, "audio_encoding_available", lambda: True)

    audio = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bond.open_phone_audio_stream", "arguments": {"call_id": call_id}},
            }
        )
    )
    get_audio_hub().close(call_id)
    stream = audio["result"]["_meta"]["audio_stream"]
    assert audio["result"]["structuredContent"]["status"] == "ready"
    assert stream["url"].startswith("https://relay.example.com/live/")
    assert stream["mime_type"] == "audio/mpeg"


def test_demo_audio_stream_uses_relay_without_local_audio_origin(tmp_path: Path) -> None:
    from bond_mcp.models import TaskState

    settings = Settings(
        allow_unlisted_destinations=True,
        autoconfirm=True,
        telephony_provider="demo",
        demo_endpoint="https://relay.example.com",
    )
    server = McpServer(settings, store_path=tmp_path / "demo-audio.sqlite3")

    class RelayProvider:
        async def create_call(self, task, call_id):
            del task, call_id
            return "remote-1"

        async def get_result(self, provider_call_id):
            del provider_call_id
            return {"status": "in_progress"}

        async def cancel_call(self, provider_call_id):
            del provider_call_id

        async def open_audio_stream(self, provider_call_id):
            assert provider_call_id == "remote-1"
            return {
                "status": "ready",
                "url": "https://relay.example.com/live/token",
                "mime_type": "audio/mpeg",
            }

    server.provider = RelayProvider()
    created = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "demo-audio",
                        "task_input": {
                            "task_id": "demo-audio",
                            "caller_identity": "Gab",
                            "destination_phone": "+33612345678",
                            "call_goal": "Test audio",
                        },
                    },
                },
            }
        )
    )
    call_id = created["result"]["structuredContent"]["call_id"]
    result = server.store.get(call_id)
    result.status = TaskState.IN_PROGRESS
    server.store.update(result)

    status = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "bond.get_phone_task_status",
                    "arguments": {"call_id": call_id},
                },
            }
        )
    )
    assert status["result"]["structuredContent"]["display"]["live_listen_available"] is True

    audio = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "bond.open_phone_audio_stream",
                    "arguments": {"call_id": call_id},
                },
            }
        )
    )
    assert audio["result"]["structuredContent"]["status"] == "ready"
    assert audio["result"]["_meta"]["audio_stream"]["url"].endswith("/live/token")


def test_settings_render_port_and_host() -> None:
    settings = Settings.from_env({"PORT": "10000"})
    assert settings.port == 10000
    assert settings.host == "0.0.0.0"
    override = Settings.from_env({"PORT": "10000", "FREDO_HOST": "127.0.0.1", "FREDO_PORT": "9999"})
    assert override.port == 9999
    assert override.host == "127.0.0.1"


def test_settings_reject_eager_above_eot() -> None:
    try:
        Settings.from_env(
            {
                "FREDO_EOT_THRESHOLD": "0.6",
                "FREDO_EAGER_EOT_THRESHOLD": "0.8",
                "FREDO_MAX_CONCURRENT_CALLS": "1",
            }
        )
    except ValueError as exc:
        assert "FREDO_EAGER_EOT_THRESHOLD" in str(exc)
    else:
        raise AssertionError("eager threshold above eot must fail closed")


def test_settings_auto_select_demo_without_provider_keys() -> None:
    settings = Settings.from_env(
        {
            "FREDO_DEMO_ENDPOINT": "https://relay.example",
            "FREDO_DEMO_ACCESS_TOKEN": "public-demo",
        }
    )
    assert settings.telephony_provider == "demo"
    assert settings.missing_for_real_call() == []
    assert settings.public_summary()["demo_configured"] is True


def test_settings_public_demo_mode_needs_no_client_token() -> None:
    settings = Settings.from_env(
        {
            "FREDO_DEMO_ENDPOINT": "https://relay.example",
            "FREDO_DEMO_PUBLIC": "1",
        }
    )
    assert settings.telephony_provider == "demo"
    assert settings.demo_public is True
    assert settings.missing_for_real_call() == []
    assert settings.public_summary()["demo_configured"] is True


def test_demo_provider_keeps_provider_keys_out_of_client_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/calls":
            return httpx.Response(200, json={"call_id": "remote-1"})
        if request.method == "GET":
            return httpx.Response(200, json={"status": "completed"})
        return httpx.Response(200, json={"status": "cancelled"})

    provider = DemoProvider(
        "https://relay.example",
        "public-demo",
        transport=httpx.MockTransport(handler),
    )
    task = build_task(
        {
            "task_id": "demo-task",
            "caller_identity": "Gab",
            "destination_phone": "+33600000000",
            "call_goal": "Reserve a table",
            "consent_confirmed": True,
            "confirmed": True,
            "idempotency_key": "demo-key",
        },
        Policy(frozenset({"+33600000000"})),
    )
    assert asyncio.run(provider.create_call(task, "local-1")) == "remote-1"
    assert asyncio.run(provider.get_status("remote-1")) == "completed"
    asyncio.run(provider.cancel_call("remote-1"))
    assert all(request.headers["authorization"] == "Bearer public-demo" for request in requests)
    assert all("DEEPGRAM" not in str(request.content) for request in requests)


def test_demo_relay_requires_token_and_refreshes_status(tmp_path: Path) -> None:
    class FakeProvider:
        async def create_call(self, task, call_id):
            del task, call_id
            return "remote-1"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "completed"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    settings = Settings(
        telephony_provider="mock",
        demo_access_token="public-demo",
        allowed_numbers=frozenset({"+33600000000"}),
        state_dir=tmp_path,
    )
    relay = DemoRelay(settings, TaskStore(tmp_path / "relay.sqlite3"), FakeProvider())
    with TestClient(relay.app()) as client:
        body = {
            "task": {
                "task_id": "relay-task",
                "caller_identity": "Gab",
                "destination_phone": "+33600000000",
                "call_goal": "Reserve a table",
                "consent_confirmed": True,
                "confirmed": True,
                "idempotency_key": "relay-key",
            }
        }
        assert client.post("/v1/calls", json=body).status_code == 401
        headers = {"Authorization": "Bearer public-demo"}
        created = client.post("/v1/calls", json=body, headers=headers)
        assert created.status_code == 200
        call_id = created.json()["call_id"]
        status = client.get(f"/v1/calls/{call_id}", headers=headers)
        assert status.json()["status"] == "completed"


def test_demo_relay_public_mode_is_allowlist_only(tmp_path: Path) -> None:
    class FakeProvider:
        async def create_call(self, task, call_id):
            del task
            return f"remote-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "completed"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    settings = Settings(
        telephony_provider="mock",
        demo_public=True,
        allowed_numbers=frozenset({"+33600000000"}),
        state_dir=tmp_path,
    )
    relay = DemoRelay(settings, TaskStore(tmp_path / "relay.sqlite3"), FakeProvider())
    body = {
        "task": {
            "task_id": "public-relay-task",
            "caller_identity": "Gab",
            "destination_phone": "+33600000000",
            "call_goal": "Reserve a table",
            "consent_confirmed": True,
            "confirmed": True,
            "idempotency_key": "public-relay-key",
        }
    }
    with TestClient(relay.app()) as client:
        created = client.post("/v1/calls", json=body)
        assert created.status_code == 200


def test_demo_relay_public_dynamic_consent_can_skip_static_list(tmp_path: Path) -> None:
    class FakeProvider:
        async def create_call(self, task, call_id):
            del task
            return f"remote-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "completed"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    settings = Settings(
        telephony_provider="mock",
        demo_public=True,
        allow_unlisted_destinations=True,
        state_dir=tmp_path,
    )
    relay = DemoRelay(settings, TaskStore(tmp_path / "relay.sqlite3"), FakeProvider())
    body = {
        "task": {
            "task_id": "dynamic-consent-task",
            "caller_identity": "Gab",
            "destination_phone": "+31636409680",
            "call_goal": "Ask whether the recipient can speak about Bond",
            "consent_confirmed": True,
            "confirmed": True,
            "idempotency_key": "dynamic-consent-key",
        }
    }
    with TestClient(relay.app()) as client:
        created = client.post("/v1/calls", json=body)
        assert created.status_code == 200


def test_silence_monitor_reprompts_then_hangs_up() -> None:
    events: list[str] = []

    async def inject(message: str) -> None:
        events.append(message)

    async def hangup() -> None:
        events.append("hangup")

    async def run() -> None:
        monitor = SilenceMonitor(
            inject_message=inject,
            on_timeout=hangup,
            language="en",
            reprompt_seconds=0.01,
            goodbye_seconds=0.01,
        )
        monitor.notify_agent_audio_done()
        await asyncio.sleep(0.02)
        assert events == ["Sorry, are you still there?"]
        monitor.notify_agent_audio_done()
        await asyncio.sleep(0.02)
        monitor.stop()

    asyncio.run(run())
    assert events[-2:] == ["I can't hear anyone, so I'll try again another time. Goodbye.", "hangup"]


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


def test_store_rejects_idempotency_key_reuse_with_changed_task(tmp_path: Path) -> None:
    policy = Policy(frozenset({"+33600000000", "+33600000001"}))
    first = build_task(
        {
            "task_id": "t1", "caller_identity": "Gab", "destination_phone": "+33600000000",
            "call_goal": "Reserve a table", "consent_confirmed": True,
            "idempotency_key": "same-key", "confirmed": True,
        }, policy,
    )
    second = build_task(
        {
            "task_id": "t2", "caller_identity": "Gab", "destination_phone": "+33600000001",
            "call_goal": "Cancel a table", "consent_confirmed": True,
            "idempotency_key": "same-key", "confirmed": True,
        }, policy,
    )
    store = TaskStore(tmp_path / "tasks.sqlite3")
    store.reserve(first)
    try:
        store.reserve(second)
    except IdempotencyConflict:
        pass
    else:
        raise AssertionError("changed task must conflict")


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
        "bond.get_task_actions",
        "bond.open_phone_audio_stream",
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


def test_rejected_preview_never_calls_provider(tmp_path: Path) -> None:
    class CountingProvider:
        calls = 0

        async def create_call(self, task, call_id):
            del task
            self.calls += 1
            return f"provider-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "queued"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    settings = Settings(allowed_numbers=frozenset({"+33600000000"}))
    server = McpServer(settings, store_path=tmp_path / "tasks.sqlite3")
    provider = CountingProvider()
    server.provider = provider
    response = asyncio.run(
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "bond.create_phone_task",
                    "arguments": {
                        "idempotency_key": "preview-only",
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
    assert response["result"]["structuredContent"]["status"] == "needs_confirmation"
    assert provider.calls == 0


def test_confirmed_task_calls_provider_once_and_replays(tmp_path: Path) -> None:
    class CountingProvider:
        calls = 0

        async def create_call(self, task, call_id):
            del task
            self.calls += 1
            return f"provider-{call_id}"

        async def get_status(self, provider_call_id):
            del provider_call_id
            return "queued"

        async def cancel_call(self, provider_call_id):
            del provider_call_id

    settings = Settings(allowed_numbers=frozenset({"+33600000000"}))
    server = McpServer(settings, store_path=tmp_path / "tasks.sqlite3")
    provider = CountingProvider()
    server.provider = provider
    arguments = {
        "name": "bond.create_phone_task",
        "arguments": {
            "idempotency_key": "confirmed-once",
            "task_input": {
                "task_id": "t1",
                "caller_identity": "Gab",
                "destination_phone": "+33600000000",
                "call_goal": "Reserve a table",
                "consent_confirmed": True,
                "confirmed": True,
            },
        },
    }
    first = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": arguments}))
    second = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": arguments}))
    assert first["result"]["structuredContent"]["status"] == "dialing"
    assert second["result"]["structuredContent"]["replayed"] is True
    assert provider.calls == 1


def test_install_writes_only_an_explicit_new_path(tmp_path: Path) -> None:
    target = tmp_path / "codex-mcp.json"
    assert main(["install", "--client", "codex", "--write", str(target)]) == 0
    assert '"bond-openai"' in target.read_text(encoding="utf-8")
    assert main(["install", "--client", "codex", "--write", str(target)]) == 2


def test_demo_configure_writes_public_profile_without_overwriting(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(
        [
            "demo",
            "configure",
            "--endpoint",
            "https://relay.example",
            "--token",
            "public-demo-token-1234",
        ]
    ) == 0
    profile = (tmp_path / "demo" / "profile.json").read_text(encoding="utf-8")
    assert "relay.example" in profile
    assert main(
        [
            "demo",
            "configure",
            "--endpoint",
            "https://other.example",
            "--token",
            "public-demo-token-1234",
        ]
    ) == 2


def test_demo_configure_writes_public_profile_without_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(
        [
            "demo",
            "configure",
            "--endpoint",
            "https://relay.example",
            "--public",
        ]
    ) == 0
    profile = json.loads((tmp_path / "demo" / "profile.json").read_text(encoding="utf-8"))
    assert profile == {
        "endpoint": "https://relay.example",
        "public": True,
        "profile": "public-demo",
    }
