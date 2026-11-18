"""Twilio transport: carrier-side duration cap and TwiML escaping, with a fake client."""

from __future__ import annotations

from typing import Any

import pytest

from fredo.models import CallRequest
from fredo.settings import Settings
from fredo.telephony import TelephonyError, TwilioTelephony, build_twiml


class _FakeCalls:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        return type("Call", (), {"sid": "CA123"})()


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "twilio_account_sid": "AC-test",
        "twilio_auth_token": "test-token",
        "twilio_phone_number": "+33600000001",
        "public_url": "https://runtime.example",
        "max_duration_seconds": 180,
    }
    values.update(overrides)
    return Settings(**values)


async def test_twilio_call_carries_carrier_time_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _FakeCalls()

    class FakeClient:
        def __init__(self, sid: str, token: str) -> None:
            self.calls = calls

    monkeypatch.setattr("twilio.rest.Client", FakeClient)
    sid = await TwilioTelephony(_settings(max_duration_seconds=120)).place_call(
        CallRequest(to="+33600000000", intent="Reserve"), "call-1"
    )
    assert sid == "CA123"
    sent = calls.created[0]
    assert sent["time_limit"] == 120
    assert sent["from_"] == "+33600000001"
    assert sent["status_callback"] == "https://runtime.example/twilio/status?call_id=call-1"
    assert "record" not in sent


async def test_twilio_requires_full_configuration() -> None:
    with pytest.raises(TelephonyError):
        await TwilioTelephony(_settings(public_url=None)).place_call(
            CallRequest(to="+33600000000", intent="Reserve"), "call-1"
        )


def test_twiml_escapes_call_id_and_requires_https() -> None:
    twiml = build_twiml("https://runtime.example", 'x"/><Hangup/>')
    assert "wss://runtime.example/twilio/media" in twiml
    assert "<Hangup/>" not in twiml
    with pytest.raises(TelephonyError):
        build_twiml("http://runtime.example", "call-1")
