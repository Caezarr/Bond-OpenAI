from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.websockets import WebSocket

from .agent_config import build_agent_settings
from .settings import Settings
from .telephony import Telephony

logger = logging.getLogger(__name__)

TranscriptCallback = Callable[[str, str], Awaitable[None]]
OutcomeCallback = Callable[[dict[str, object]], Awaitable[None]]

FINISH_POST_FUNCTION_AUDIO_GRACE_SECONDS = 1.0
FINISH_AUDIO_DONE_TIMEOUT_SECONDS = 8.0
FINISH_MARK_TIMEOUT_SECONDS = 12.0


class VoiceAgentSession:
    """Bridge one Twilio media stream to one Deepgram Voice Agent session."""

    def __init__(
        self,
        *,
        twilio_ws: WebSocket,
        stream_sid: str,
        provider_call_id: str,
        intent: str,
        settings: Settings,
        telephony: Telephony,
        on_transcript: TranscriptCallback,
        on_outcome: OutcomeCallback,
    ) -> None:
        self.twilio_ws = twilio_ws
        self.stream_sid = stream_sid
        self.provider_call_id = provider_call_id
        self.intent = intent
        self.settings = settings
        self.telephony = telephony
        self.on_transcript = on_transcript
        self.on_outcome = on_outcome
        self._context_manager: Any = None
        self._connection: Any = None
        self._settings_applied = asyncio.Event()
        self._forward_twilio_audio = asyncio.Event()
        self._agent_audio_started = asyncio.Event()
        self._agent_audio_done = asyncio.Event()
        self._agent_audio_done_is_current = False
        self._finish_requested = asyncio.Event()
        self._finish_task: asyncio.Task[None] | None = None
        self._playback_mark_ack = asyncio.Event()
        self._playback_mark_name: str | None = None

    async def run(self) -> None:
        if not self.settings.deepgram_api_key:
            raise RuntimeError("Deepgram is not configured")

        listen_task: asyncio.Task[None] | None = None
        media_task = asyncio.create_task(self._listen_twilio())
        duration_task: asyncio.Task[None] | None = None

        try:
            # Drain Twilio from the start of the answered call. Until Deepgram
            # acknowledges its settings, _listen_twilio deliberately discards
            # these pre-greeting frames instead of replaying a stale "hello"
            # into the agent and triggering barge-in against its disclosure.
            from deepgram import AsyncDeepgramClient

            client = AsyncDeepgramClient(api_key=self.settings.deepgram_api_key)
            self._context_manager = client.agent.v1.connect()
            self._connection = await self._context_manager.__aenter__()
            listen_task = asyncio.create_task(self._listen_deepgram())
            await self._connection.send_settings(
                build_agent_settings(self.settings, self.intent)
            )
            await asyncio.wait_for(self._settings_applied.wait(), timeout=8)
            self._forward_twilio_audio.set()
            duration_task = asyncio.create_task(self._duration_guard())

            done, pending = await asyncio.wait(
                [listen_task, media_task, duration_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                if not task.cancelled():
                    exception = task.exception()
                    if exception:
                        raise exception
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        finally:
            tasks = tuple(
                task
                for task in (listen_task, media_task, duration_task, self._finish_task)
                if task is not None
            )
            for task in tasks:
                if task and not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if self._context_manager:
                try:
                    await self._context_manager.__aexit__(None, None, None)
                except Exception:
                    logger.debug("Deepgram cleanup failed", exc_info=True)

    async def _duration_guard(self) -> None:
        await asyncio.sleep(self.settings.max_duration_seconds)
        await self.telephony.hangup(self.provider_call_id)

    async def _listen_twilio(self) -> None:
        while True:
            message = await self.twilio_ws.receive_text()
            data = json.loads(message)
            event = data.get("event")
            if event == "media":
                if self._forward_twilio_audio.is_set():
                    audio = base64.b64decode(data["media"]["payload"], validate=True)
                    await self._connection.send_media(audio)
            elif event == "mark":
                mark_name = data.get("mark", {}).get("name")
                if mark_name and mark_name == self._playback_mark_name:
                    self._playback_mark_ack.set()
            elif event == "stop":
                return

    async def _listen_deepgram(self) -> None:
        from deepgram.agent.v1 import (
            AgentV1AgentAudioDone,
            AgentV1ConversationText,
            AgentV1Error,
            AgentV1FunctionCallRequest,
            AgentV1SettingsApplied,
            AgentV1UserStartedSpeaking,
            AgentV1Warning,
        )
        from deepgram.agent.v1.socket_client import V1SocketClientResponse
        from deepgram.core.pydantic_utilities import parse_obj_as

        async for raw_message in self._connection._websocket:
            if isinstance(raw_message, bytes):
                self._agent_audio_done_is_current = False
                self._agent_audio_done.clear()
                self._agent_audio_started.set()
                audio_b64 = base64.b64encode(raw_message).decode("ascii")
                await self.twilio_ws.send_json(
                    {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {"payload": audio_b64},
                    }
                )
                continue

            try:
                parsed = parse_obj_as(V1SocketClientResponse, json.loads(raw_message))
            except Exception:
                logger.debug("Ignoring an unsupported Deepgram event")
                continue

            if isinstance(parsed, AgentV1SettingsApplied):
                self._settings_applied.set()
            elif isinstance(parsed, AgentV1ConversationText):
                if str(parsed.role) == "user":
                    self._agent_audio_done_is_current = False
                    self._agent_audio_done.clear()
                await self.on_transcript(str(parsed.role), str(parsed.content))
            elif isinstance(parsed, AgentV1UserStartedSpeaking):
                self._agent_audio_done_is_current = False
                self._agent_audio_done.clear()
                await self.twilio_ws.send_json(
                    {"event": "clear", "streamSid": self.stream_sid}
                )
            elif isinstance(parsed, AgentV1FunctionCallRequest):
                await self._handle_function_call(parsed)
            elif isinstance(parsed, AgentV1AgentAudioDone):
                self._agent_audio_done_is_current = True
                self._agent_audio_done.set()
            elif isinstance(parsed, AgentV1Error):
                raise RuntimeError("Deepgram Voice Agent returned an error")
            elif isinstance(parsed, AgentV1Warning):
                logger.warning("Deepgram Voice Agent warning received")

    async def _handle_function_call(self, event: Any) -> None:
        from deepgram.agent.v1 import AgentV1SendFunctionCallResponse

        for function in event.functions or []:
            should_finish = False
            if function.name != "finish_demo":
                content: dict[str, object] = {"error": "unsupported_function"}
            else:
                try:
                    arguments = json.loads(function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                answer = str(arguments.get("answer", "")).strip()[:500]
                summary = str(arguments.get("summary", "")).strip()[:1000]
                content = {
                    "works": arguments.get("works") is True,
                    "answer": answer,
                    "summary": summary,
                }
                await self.on_outcome(content)
                self._finish_requested.set()
                should_finish = True

            response = AgentV1SendFunctionCallResponse(
                type="FunctionCallResponse",
                id=function.id,
                name=function.name,
                content=json.dumps(content, ensure_ascii=False),
            )
            await self._connection.send_function_call_response(response)
            if should_finish and self._finish_task is None:
                audio_was_done_before_function = self._agent_audio_done_is_current
                self._agent_audio_started.clear()
                if not audio_was_done_before_function:
                    self._agent_audio_done.clear()
                self._finish_task = asyncio.create_task(
                    self._hangup_after_playback(
                        audio_was_done_before_function=audio_was_done_before_function
                    )
                )

    async def _hangup_after_playback(
        self, *, audio_was_done_before_function: bool
    ) -> None:
        try:
            if audio_was_done_before_function:
                try:
                    await asyncio.wait_for(
                        self._agent_audio_started.wait(),
                        timeout=FINISH_POST_FUNCTION_AUDIO_GRACE_SECONDS,
                    )
                except TimeoutError:
                    pass

            if not self._agent_audio_done_is_current:
                try:
                    await asyncio.wait_for(
                        self._agent_audio_done.wait(),
                        timeout=FINISH_AUDIO_DONE_TIMEOUT_SECONDS,
                    )
                except TimeoutError:
                    logger.warning("Timed out waiting for final Deepgram audio")

            self._playback_mark_name = "fredo-finish"
            self._playback_mark_ack.clear()
            try:
                await self.twilio_ws.send_json(
                    {
                        "event": "mark",
                        "streamSid": self.stream_sid,
                        "mark": {"name": self._playback_mark_name},
                    }
                )
                await asyncio.wait_for(
                    self._playback_mark_ack.wait(),
                    timeout=FINISH_MARK_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning("Timed out waiting for Twilio playback acknowledgement")
            except Exception:
                logger.debug("Unable to confirm Twilio playback", exc_info=True)
        except asyncio.CancelledError:
            raise

        try:
            await self.telephony.hangup(self.provider_call_id)
        except Exception:
            # The independent carrier time limit and duration guard remain as
            # hard fallbacks; this task must not leak an unobserved exception.
            logger.warning("Twilio finish hangup failed; duration guard remains active")
