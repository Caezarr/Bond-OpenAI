from __future__ import annotations

import asyncio
import logging
import threading
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from uvicorn import Config, Server

from fredo.telephony import telephony_from_settings
from fredo.voice_agent import VoiceAgentSession

from .models import TaskState
from .store import TaskStore

logger = logging.getLogger(__name__)


def create_runtime_app(settings, store: TaskStore) -> Starlette:
    telephony = telephony_from_settings(settings)

    async def health(request: Request) -> JSONResponse:
        del request
        return JSONResponse({"status": "ok", "service": "bond-openai-runtime"})

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
            result.status = mapped
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
            start = await websocket.receive_json()
            if start.get("event") != "start":
                await websocket.close(code=1002)
                return
            start_data = start.get("start", {})
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
            store.update(result)

            async def on_transcript(_role: str, _content: str) -> None:
                return

            async def on_outcome(outcome: dict[str, object]) -> None:
                result.status = TaskState.COMPLETED
                result.outcome = "conversation_completed"
                result.summary = str(outcome.get("summary", "")).strip()[:1000] or None
                store.update(result)

            session = VoiceAgentSession(
                twilio_ws=websocket,
                stream_sid=str(start_data.get("streamSid", "")),
                provider_call_id=provider_call_id,
                intent=task.call_goal,
                language=task.language,
                settings=settings,
                telephony=telephony,
                on_transcript=on_transcript,
                on_outcome=on_outcome,
            )
            await session.run()
        except WebSocketDisconnect:
            return
        except Exception:
            logger.exception("Phone media session failed")

    return Starlette(
        routes=[
            Route("/healthz", health, methods=["GET"]),
            Route("/twilio/status", status, methods=["POST"]),
            WebSocketRoute("/twilio/media", media),
        ]
    )


def _valid_twilio_signature(settings, websocket: WebSocket, signature: str) -> bool:
    try:
        from twilio.request_validator import RequestValidator

        public_url = settings.public_url or ""
        query = urlsplit(str(websocket.url)).query
        url = public_url.rstrip("/") + "/twilio/media"
        if query:
            url += "?" + query
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
