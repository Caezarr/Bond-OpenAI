"""Carrier-facing runtime: Twilio status callbacks and the media WebSocket.

Binds the provider-neutral task store to the Fredo voice agent. Every inbound
request is authenticated (Twilio signature or local endpoint secret) before it
can change a task, and terminal task states are never overwritten.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import threading
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from uvicorn import Config, Server

from fredo.security import validate_twilio_signature
from fredo.settings import Settings
from fredo.telephony import telephony_from_settings
from fredo.voice_agent import VoiceAgentSession

from .lifecycle import TWILIO_CALLBACK_STATES
from .models import TERMINAL_STATES, TaskState
from .store import TaskStore

logger = logging.getLogger(__name__)


def create_runtime_app(settings: Settings, store: TaskStore) -> Starlette:
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
        local_auth = bool(settings.endpoint_secret) and hmac.compare_digest(
            supplied, f"Bearer {settings.endpoint_secret}"
        )
        twilio_auth = _valid_twilio_http(settings, request, form, signature)
        if not (local_auth or twilio_auth):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        mapped = TWILIO_CALLBACK_STATES.get(str(form.get("CallStatus", "")))
        if mapped and result.status not in TERMINAL_STATES:
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
                # Transcripts are deliberately not retained or logged.
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


def _valid_twilio_signature(settings: Settings, websocket: WebSocket, signature: str) -> bool:
    if not settings.twilio_auth_token:
        return False
    url = (settings.public_url or "").rstrip("/") + "/twilio/media"
    query = urlsplit(str(websocket.url)).query
    if query:
        url += "?" + query
    return validate_twilio_signature(settings.twilio_auth_token, url, {}, signature)


def _valid_twilio_http(
    settings: Settings, request: Request, form: Mapping[str, Any], signature: str
) -> bool:
    if not settings.twilio_auth_token or not signature:
        return False
    if settings.public_url:
        url = settings.public_url.rstrip("/") + "/twilio/status"
    else:
        url = str(request.url)
    if request.url.query:
        url += "?" + request.url.query
    params = {key: str(value) for key, value in form.items()}
    return validate_twilio_signature(settings.twilio_auth_token, url, params, signature)


class RuntimeThread:
    """Serve the runtime app on a daemon thread beside the stdio MCP loop."""

    def __init__(self, settings: Settings, store: TaskStore):
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
