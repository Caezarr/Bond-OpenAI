"""Fredo voice runtime: agent settings, silence handling and the duration guard."""

from __future__ import annotations

import asyncio
from typing import Any

from fredo.agent_config import build_agent_settings
from fredo.models import CallRequest
from fredo.settings import Settings
from fredo.silence_monitor import SilenceMonitor
from fredo.voice_agent import VoiceAgentSession


def test_voice_agent_uses_typed_language_for_greeting() -> None:
    settings = build_agent_settings(Settings(deepgram_api_key="test"), "Réserver une table", "fr")
    assert settings.agent.greeting.startswith("Bonjour")
    assert "Speak French" in settings.agent.think.prompt


def test_greeting_discloses_synthetic_voice_and_no_recording() -> None:
    settings = build_agent_settings(Settings(deepgram_api_key="test"), "Reserve a table", "en")
    greeting = settings.agent.greeting
    assert "synthetic voice" in greeting
    assert "not recorded" in greeting


def test_flux_endpointing_is_applied_to_listen_provider() -> None:
    settings = Settings(
        deepgram_api_key="test", eot_threshold=0.85, eot_timeout_ms=9000, eager_eot_threshold=0.4
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


async def test_silence_monitor_reprompts_then_hangs_up() -> None:
    events: list[str] = []

    async def inject(message: str) -> None:
        events.append(message)

    async def hangup() -> None:
        events.append("hangup")

    monitor = SilenceMonitor(
        inject_message=inject,
        on_timeout=hangup,
        language="en",
        reprompt_seconds=0.01,  # type: ignore[arg-type]
        goodbye_seconds=0.01,  # type: ignore[arg-type]
    )
    monitor.notify_agent_audio_done()
    await asyncio.sleep(0.02)
    assert events == ["Sorry, are you still there?"]
    monitor.notify_agent_audio_done()
    await asyncio.sleep(0.02)
    monitor.stop()
    assert events[-2:] == [
        "I can't hear anyone, so I'll try again another time. Goodbye.",
        "hangup",
    ]


class _RecordingTelephony:
    def __init__(self) -> None:
        self.hangups: list[str] = []

    async def place_call(self, request: CallRequest, call_id: str) -> str:
        return call_id

    async def get_status(self, provider_call_id: str) -> str:
        return "in-progress"

    async def hangup(self, provider_call_id: str) -> None:
        self.hangups.append(provider_call_id)


async def test_duration_guard_hangs_up_at_the_cap() -> None:
    telephony = _RecordingTelephony()
    session = VoiceAgentSession(
        twilio_ws=Any,  # type: ignore[arg-type]
        stream_sid="MZ1",
        provider_call_id="CA1",
        intent="Reserve a table",
        language="en",
        # Constructed directly to bypass the 10-180 s env validation for speed.
        settings=Settings(max_duration_seconds=0),
        telephony=telephony,
        on_transcript=None,  # type: ignore[arg-type]
        on_outcome=None,  # type: ignore[arg-type]
    )
    await asyncio.wait_for(session._duration_guard(), timeout=1)
    assert telephony.hangups == ["CA1"]
