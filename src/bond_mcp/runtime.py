from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from uvicorn import Config, Server

from fredo.audio import (
    audio_encoding_available,
    encode_pcm_stream,
    get_audio_hub,
    get_audio_tokens,
)
from fredo.telephony import telephony_from_settings
from fredo.voice_agent import VoiceAgentSession

from .models import TaskState
from .store import TaskStore
from .summary import fallback_summary

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_runtime_app(settings, store: TaskStore) -> Starlette:
    telephony = telephony_from_settings(settings)

    async def health(request: Request) -> JSONResponse:
        del request
        return JSONResponse({"status": "ok", "service": "bond-openai-runtime"})

    async def ready(request: Request) -> JSONResponse:
        del request
        missing = settings.missing_for_real_call()
        encoder_available = audio_encoding_available()
        audio_error = bool(settings.audio_stream_origin) and not encoder_available
        payload = {
            "status": "ready" if not missing and not audio_error else "not_ready",
            "missing": missing,
            "audio": {
                "enabled": bool(settings.audio_stream_origin),
                "encoder_available": encoder_available,
            },
        }
        return JSONResponse(payload, status_code=200 if payload["status"] == "ready" else 503)

    async def status(request: Request) -> JSONResponse:
        call_id = request.query_params.get("call_id", "")
        result = store.get(call_id)
        if result is None:
            return JSONResponse({"error": "unknown_call"}, status_code=404)
        form = await request.form()
        supplied = request.headers.get("authorization", "")
        signature = request.headers.get("x-twilio-signature", "")
        local_auth = settings.endpoint_secret and supplied == f"Bearer {settings.endpoint_secret}"
        twilio_auth = _valid_twilio_http(settings, request, form, signature)
        if not (local_auth or twilio_auth):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        call_status = str(form.get("CallStatus", ""))
        mapped = {
            "queued": TaskState.DIALING,
            "initiated": TaskState.DIALING,
            "ringing": TaskState.DIALING,
            "in-progress": TaskState.IN_PROGRESS,
            "completed": TaskState.COMPLETED,
            "busy": TaskState.DECLINED,
            "no-answer": TaskState.NO_ANSWER,
            "canceled": TaskState.CANCELLED,
            "failed": TaskState.FAILED,
        }.get(call_status)
        if mapped and result.status not in {TaskState.COMPLETED, TaskState.NO_ANSWER, TaskState.DECLINED, TaskState.FAILED, TaskState.CANCELLED}:
            # A carrier-level "completed" only means that the phone leg ended.
            # It is not evidence that the voice agent connected or spoke.
            if mapped == TaskState.COMPLETED and result.outcome is None:
                result.status = TaskState.FAILED
                result.error = "voice session ended without a verified result"
            else:
                result.status = mapped
            if mapped == TaskState.IN_PROGRESS and not result.connected_at:
                result.connected_at = _now_iso()
            if mapped in {TaskState.COMPLETED, TaskState.NO_ANSWER, TaskState.DECLINED, TaskState.FAILED, TaskState.CANCELLED} and not result.ended_at:
                result.ended_at = _now_iso()
            store.update(result)
        return JSONResponse({"ok": True})

    async def media(websocket: WebSocket) -> None:
        if settings.twilio_auth_token:
            signature = websocket.headers.get("x-twilio-signature", "")
            if not _valid_twilio_signature(settings, websocket, signature):
                await websocket.close(code=1008)
                return
        await websocket.accept()
        try:
            # Twilio Media Streams sends a "connected" control frame before the
            # "start" frame. Skip pre-start control frames instead of rejecting
            # the socket on the first non-start frame (which drops the call).
            start_data: dict = {}
            while True:
                message = await websocket.receive_json()
                event = message.get("event")
                if event == "start":
                    start_data = message.get("start", {})
                    break
                if event == "stop":
                    await websocket.close(code=1000)
                    return
            params = start_data.get("customParameters", {})
            call_id = str(params.get("fredoCallId", ""))
            provider_call_id = str(start_data.get("callSid", ""))
            task = store.get_task(call_id)
            result = store.get(call_id)
            if not task or not result:
                await websocket.close(code=1008)
                return
            result.status = TaskState.IN_PROGRESS
            result.provider_call_id = provider_call_id or result.provider_call_id
            if not result.connected_at:
                result.connected_at = _now_iso()
            store.update(result)

            async def on_transcript(_role: str, _content: str) -> None:
                return

            async def on_outcome(outcome: dict[str, object]) -> None:
                result.status = TaskState.COMPLETED
                result.ended_at = result.ended_at or _now_iso()
                works = outcome.get("works") is True
                result.works = works
                result.outcome = "objective_confirmed" if works else "objective_unconfirmed"
                result.answer = str(outcome.get("answer", "")).strip()[:500] or None
                result.summary = str(outcome.get("summary", "")).strip()[:1000] or None
                raw_details = outcome.get("details")
                result.details = raw_details if isinstance(raw_details, dict) else None
                store.update(result)

            hub = get_audio_hub()
            session = VoiceAgentSession(
                twilio_ws=websocket,
                stream_sid=str(start_data.get("streamSid", "")),
                provider_call_id=provider_call_id,
                intent=task.call_goal,
                language=task.language,
                timezone=task.timezone,
                settings=settings,
                telephony=telephony,
                on_transcript=on_transcript,
                on_outcome=on_outcome,
                audio_publish=(
                    (lambda leg, data: hub.publish(call_id, leg, data))
                    if settings.audio_stream_origin
                    else None
                ),
            )
            try:
                await session.run()
            finally:
                hub.close(call_id)
            # Guarantee a clear summary even when the agent never called
            # finish_demo (early hangup, silence, carrier drop).
            if not session.outcome_captured and result.outcome is None:
                result.outcome = "ended_without_confirmation"
                result.ended_at = result.ended_at or _now_iso()
                result.summary = fallback_summary(
                    language=task.language,
                    disclosure_delivered=session.disclosure_delivered,
                    user_turns=session.user_turn_count,
                )
                store.update(result)
        except WebSocketDisconnect:
            return
        except Exception:
            logger.exception("Phone media session failed")
            if "result" in locals() and result.status not in {
                TaskState.COMPLETED,
                TaskState.NO_ANSWER,
                TaskState.DECLINED,
                TaskState.CANCELLED,
            }:
                result.status = TaskState.FAILED
                result.outcome = "voice_session_failed"
                result.error = "voice session failed before completing the call"
                result.ended_at = result.ended_at or _now_iso()
                store.update(result)

    async def live(request: Request) -> StreamingResponse | JSONResponse:
        token = request.path_params["token"]
        call_id = get_audio_tokens().consume(token)
        if not call_id:
            return JSONResponse({"error": "invalid_token"}, status_code=404)
        if not audio_encoding_available():
            return JSONResponse({"error": "audio_unavailable"}, status_code=503)
        hub = get_audio_hub()
        if not hub.is_live(call_id):
            return JSONResponse({"error": "call_not_live"}, status_code=404)
        frames = hub.listen(call_id)
        return StreamingResponse(
            encode_pcm_stream(frames),
            media_type="audio/mpeg",
            headers={"cache-control": "no-store"},
        )

    return Starlette(
        routes=[
            Route("/healthz", health, methods=["GET"]),
            Route("/readyz", ready, methods=["GET"]),
            Route("/twilio/status", status, methods=["POST"]),
            WebSocketRoute("/twilio/media", media),
            Route("/live/{token}", live, methods=["GET"]),
        ]
    )


def _valid_twilio_signature(settings, websocket: WebSocket, signature: str) -> bool:
    try:
        from twilio.request_validator import RequestValidator

        public_url = settings.public_url or ""
        query = urlsplit(str(websocket.url)).query
        parsed = urlsplit(public_url)
        # Twilio signs the exact WebSocket URL from the <Stream> TwiML.  The
        # public service URL is configured as HTTPS, but using that scheme here
        # changes the HMAC input and rejects every legitimate WSS connection.
        path = parsed.path.rstrip("/") + "/twilio/media"
        url = urlunsplit(("wss", parsed.netloc, path, query, ""))
        return RequestValidator(settings.twilio_auth_token).validate(url, {}, signature)
    except Exception:
        return False


def _valid_twilio_http(settings, request: Request, form, signature: str) -> bool:
    if not settings.twilio_auth_token or not signature:
        return False
    try:
        from twilio.request_validator import RequestValidator

        url = settings.public_url.rstrip("/") + "/twilio/status" if settings.public_url else str(request.url)
        if request.url.query:
            url += "?" + request.url.query
        return RequestValidator(settings.twilio_auth_token).validate(url, dict(form), signature)
    except Exception:
        return False


class RuntimeThread:
    def __init__(self, settings, store: TaskStore):
        self.settings = settings
        self.store = store
        self.thread: threading.Thread | None = None
        self.server: Server | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        def run() -> None:
            config = Config(
                create_runtime_app(self.settings, self.store),
                host=self.settings.host,
                port=self.settings.port,
                log_level="warning",
            )
            self.server = Server(config)
            asyncio.run(self.server.serve())

        self.thread = threading.Thread(target=run, name="bond-openai-runtime", daemon=True)
        self.thread.start()
