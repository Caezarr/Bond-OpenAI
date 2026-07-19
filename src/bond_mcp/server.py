from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fredo.audio import audio_encoding_available, get_audio_hub, get_audio_tokens
from fredo.settings import Settings

from .actions import build_next_actions
from .display import build_display
from .models import PhoneResult, PhoneTask, TaskState
from .policy import Policy, PolicyError, build_task, classify
from .providers import DemoProvider, PhoneProvider, provider_from_settings
from .runtime import RuntimeThread
from .store import ActiveCall, IdempotencyConflict, TaskStore

WIDGET_URI = "ui://fredo/phone-call-v2.html"
_WIDGET_PATH = (
    Path(__file__).resolve().parents[2]
    / "codex-plugin"
    / "fredo"
    / "ui"
    / "phone-call.html"
)


class McpServer:
    def __init__(self, settings: Settings | None = None, *, store_path: Path | None = None):
        self.settings = settings or Settings.from_env()
        self.policy = Policy(
            allowed_numbers=self.settings.allowed_numbers,
            max_duration_seconds=self.settings.max_duration_seconds,
            allow_unlisted=self.settings.allow_unlisted_destinations,
            autoconfirm=self.settings.autoconfirm,
        )
        self.store = TaskStore(store_path or self.settings.state_dir / "bond_tasks.sqlite3")
        self.provider: PhoneProvider = provider_from_settings(self.settings)
        self.runtime: RuntimeThread | None = None

    def start_runtime(self) -> None:
        """Start the local Twilio/Deepgram callback runtime beside stdio MCP."""
        if self.runtime is None and not isinstance(self.provider, DemoProvider):
            self.runtime = RuntimeThread(self.settings, self.store)
            self.runtime.start()

    async def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return self._result(request_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "bond-openai", "version": "0.1.0"},
            })
        if method == "tools/list":
            return self._result(request_id, {"tools": self.tools()})
        if method == "resources/list":
            return self._result(request_id, {"resources": self._resources()})
        if method == "resources/read":
            params = message.get("params") or {}
            return self._read_resource(request_id, params.get("uri"))
        if method == "tools/call":
            params = message.get("params") or {}
            return await self._call_tool(request_id, params.get("name"), params.get("arguments") or {})
        if request_id is not None:
            return self._error(request_id, -32601, "Method not found")
        return None

    @staticmethod
    def tools() -> list[dict[str, Any]]:
        return [
            {"name": "bond.classify_task", "description": "Classify whether a task needs a phone call.", "inputSchema": {"type": "object", "required": ["task_text"], "properties": {"task_text": {"type": "string"}, "context": {"type": "object"}}}},
            {
                "name": "bond.create_phone_task",
                "description": "Validate, preview and create one consented phone task. Provide every task_input field in a single call; do not call with partial input.",
                "inputSchema": {
                    "type": "object",
                    "required": ["task_input", "idempotency_key"],
                    "properties": {
                        "task_input": {
                            "type": "object",
                            "required": ["task_id", "caller_identity", "destination_phone", "call_goal", "language"],
                            "properties": {
                                "task_id": {"type": "string", "description": "Stable unique id for this task."},
                                "caller_identity": {"type": "string", "description": "Who the call is from (e.g. Gabriel)."},
                                "destination_phone": {"type": "string", "description": "Recipient number in E.164, e.g. +33695340008."},
                                "call_goal": {"type": "string", "description": "What to accomplish on the call (max 500 chars)."},
                                "language": {"type": "string", "enum": ["en", "fr"], "description": "Spoken language for the call."},
                                "recipient_label": {"type": "string", "description": "Human display name for the recipient (widget only)."},
                                "consent_confirmed": {"type": "boolean", "description": "True when the recipient consents to the call."},
                                "confirmed": {"type": "boolean", "description": "True to dial now; omit/false to only preview."},
                                "timezone": {"type": "string", "description": "IANA timezone for relative dates, e.g. Europe/Brussels."},
                            },
                        },
                        "idempotency_key": {"type": "string"},
                    },
                },
                "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True, "idempotentHint": True},
                "_meta": {
                    "ui": {"resourceUri": WIDGET_URI, "visibility": ["model", "app"]},
                    "openai/outputTemplate": WIDGET_URI,
                    "openai/toolInvocation/invoking": "Preparing the call…",
                    "openai/toolInvocation/invoked": "Phone ready",
                },
            },
            {"name": "bond.get_phone_task_status", "description": "Get a structured phone task result, including any proposed next_actions.", "inputSchema": {"type": "object", "required": ["call_id"], "properties": {"call_id": {"type": "string"}}}},
            {"name": "bond.get_task_actions", "description": "Get proposed outbound actions (e.g. calendar.create_event) derived from a completed call.", "inputSchema": {"type": "object", "required": ["call_id"], "properties": {"call_id": {"type": "string"}}}},
            {"name": "bond.open_phone_audio_stream", "description": "Open a short-lived, listen-only live audio stream for an in-progress call (app-only; user-initiated).", "inputSchema": {"type": "object", "required": ["call_id"], "properties": {"call_id": {"type": "string"}}}},
            {"name": "bond.cancel_phone_task", "description": "Cancel an active phone task.", "inputSchema": {"type": "object", "required": ["call_id"], "properties": {"call_id": {"type": "string"}}}},
        ]

    @staticmethod
    def _resources() -> list[dict[str, Any]]:
        return [{"uri": WIDGET_URI, "name": "Fredo phone", "description": "Live phone call surface.", "mimeType": "text/html;profile=mcp-app"}]

    def _read_resource(self, request_id: Any, uri: Any) -> dict[str, Any]:
        if uri != WIDGET_URI:
            return self._error(request_id, -32602, "Unknown resource")
        try:
            html = _WIDGET_PATH.read_text(encoding="utf-8")
        except OSError:
            return self._error(request_id, -32603, "Widget resource unavailable")
        origin = self._audio_origin()
        csp = {"connectDomains": [origin] if origin else [], "resourceDomains": [origin] if origin else []}
        content = {"uri": WIDGET_URI, "mimeType": "text/html;profile=mcp-app", "text": html, "_meta": {"ui": {"csp": csp}}}
        return self._result(request_id, {"contents": [content]})

    def _display(self, task: PhoneTask | None, result: PhoneResult) -> dict[str, Any]:
        return build_display(
            task,
            result,
            max_duration_seconds=self.policy.max_duration_seconds,
            live_listen_available=bool(self._audio_origin()),
        )

    def _audio_origin(self) -> str | None:
        """Return the origin that serves live audio for the selected provider."""
        if self.settings.audio_stream_origin:
            return self.settings.audio_stream_origin
        if getattr(self.provider, "open_audio_stream", None) is not None:
            return self.settings.demo_endpoint
        return None

    async def _open_audio_stream(self, call_id: str, result: PhoneResult) -> dict[str, Any] | None:
        """Return a one-time listen-only stream descriptor, or None if unavailable."""
        if result.status != TaskState.IN_PROGRESS:
            return None
        opener = getattr(self.provider, "open_audio_stream", None)
        if opener is not None and result.provider_call_id:
            # Demo mode: the relay owns the audio and mints the token.
            try:
                payload = await opener(result.provider_call_id)
            except Exception:
                return None
            if not isinstance(payload, dict) or payload.get("status") != "ready" or not payload.get("url"):
                return None
            return {
                "url": payload["url"],
                "mime_type": payload.get("mime_type", "audio/mpeg"),
                "expires_at": payload.get("expires_at"),
            }
        # Local/real mode: this process runs the audio hub, so mint locally.
        if not self.settings.audio_stream_origin:
            return None
        origin = self.settings.audio_stream_origin.rstrip("/")
        if not audio_encoding_available() or not get_audio_hub().is_live(call_id):
            return None
        token, expires_at = get_audio_tokens().mint(call_id)
        return {
            "url": f"{origin}/live/{token}",
            "mime_type": "audio/mpeg",
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        }

    async def _call_tool(self, request_id: Any, name: str | None, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "bond.classify_task":
                context = args.get("context")
                value = classify(
                    str(args.get("task_text", "")),
                    context if isinstance(context, dict) else None,
                )
                return self._tool_result(request_id, {"classification": value})
            if name == "bond.create_phone_task":
                payload = dict(args.get("task_input") or {})
                idempotency_key = str(args.get("idempotency_key", "")).strip()
                if not idempotency_key:
                    raise PolicyError("idempotency_required", "idempotency_key is required")
                payload["idempotency_key"] = idempotency_key
                task = build_task(payload, self.policy)
                if not task.confirmed:
                    preview = PhoneResult(task_id=task.task_id, call_id="", status=TaskState.READY_FOR_REVIEW)
                    return self._tool_result(request_id, {"status": "needs_confirmation", "preview": {"destination_phone": task.destination_phone, "caller_identity": task.caller_identity, "call_goal": task.call_goal, "recorded": False, "max_duration_seconds": self.policy.max_duration_seconds}, "display": self._display(task, preview)})
                call_id, result, replayed = self.store.reserve(task)
                if not replayed:
                    try:
                        provider_id = await self.provider.create_call(task, call_id)
                        result.provider_call_id = provider_id
                        result.status = TaskState.DIALING
                        self.store.update(result)
                    except Exception as exc:
                        result.status = TaskState.FAILED
                        result.error = "phone provider rejected the call"
                        self.store.update(result)
                        raise PolicyError("provider_failed", str(exc)) from exc
                data = result.as_dict()
                data["replayed"] = replayed
                data["display"] = self._display(task, result)
                return self._tool_result(request_id, data)
            if name == "bond.get_phone_task_status":
                call_id = str(args.get("call_id", ""))
                result = self.store.get(call_id)
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                await self._refresh_provider_status(result)
                task = self.store.get_task(call_id)
                data = result.as_dict()
                data["next_actions"] = build_next_actions(task, result)
                data["display"] = self._display(task, result)
                return self._tool_result(request_id, data)
            if name == "bond.open_phone_audio_stream":
                call_id = str(args.get("call_id", ""))
                result = self.store.get(call_id)
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                descriptor = await self._open_audio_stream(call_id, result)
                if not descriptor:
                    return self._tool_result(request_id, {"call_id": call_id, "status": "unavailable"})
                # The stream descriptor lives in _meta only: it is widget-only and
                # must never leak into structuredContent, logs or summaries.
                return self._tool_result(
                    request_id,
                    {"call_id": call_id, "status": "ready"},
                    meta={"audio_stream": descriptor},
                )
            if name == "bond.get_task_actions":
                call_id = str(args.get("call_id", ""))
                result = self.store.get(call_id)
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                actions = build_next_actions(self.store.get_task(call_id), result)
                return self._tool_result(request_id, {"call_id": call_id, "next_actions": actions})
            if name == "bond.cancel_phone_task":
                call_id = str(args.get("call_id", ""))
                result = self.store.get(call_id)
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                if result.status not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.NO_ANSWER, TaskState.DECLINED}:
                    if result.provider_call_id:
                        await self.provider.cancel_call(result.provider_call_id)
                    result.status = TaskState.CANCELLED
                    self.store.update(result)
                data = result.as_dict()
                data["display"] = self._display(self.store.get_task(call_id), result)
                return self._tool_result(request_id, data)
            raise PolicyError("unknown_tool", f"Unknown tool: {name}")
        except (PolicyError, IdempotencyConflict, ActiveCall) as exc:
            code = getattr(exc, "code", "idempotency_conflict" if isinstance(exc, IdempotencyConflict) else "call_busy")
            # The phone widget is bound to bond.create_phone_task, so every result
            # of that tool renders a card, including validation errors (missing
            # fields, consent). Tell the host to hide the widget for those error
            # results so only the real dialing card remains.
            meta = {"openai/closeWidget": True} if name == "bond.create_phone_task" else None
            return self._tool_result(
                request_id,
                {"status": "error", "code": code, "message": str(exc)},
                is_error=True,
                meta=meta,
            )

    async def _refresh_provider_status(self, result) -> None:
        if not result.provider_call_id or result.status in {
            TaskState.COMPLETED,
            TaskState.NO_ANSWER,
            TaskState.DECLINED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }:
            return
        remote: dict[str, Any] | None = None
        get_result = getattr(self.provider, "get_result", None)
        try:
            if get_result is not None:
                remote = await get_result(result.provider_call_id)
                provider_status = str(remote.get("status", ""))
            else:
                provider_status = await self.provider.get_status(result.provider_call_id)
        except Exception:
            return
        if remote:
            # Carry the relay's authoritative display fields back to the local
            # store so the widget shows a real timer, summary and outcome.
            for field_name in ("connected_at", "ended_at", "summary", "answer", "outcome"):
                value = remote.get(field_name)
                if value is not None and getattr(result, field_name, None) is None:
                    setattr(result, field_name, value)
            if isinstance(remote.get("details"), dict) and result.details is None:
                result.details = remote["details"]
            if remote.get("works") is not None and result.works is None:
                result.works = remote["works"]
        mapped = {
            "queued": TaskState.DIALING,
            "initiated": TaskState.DIALING,
            "ringing": TaskState.DIALING,
            "dialing": TaskState.DIALING,
            "in-progress": TaskState.IN_PROGRESS,
            "in_progress": TaskState.IN_PROGRESS,
            "completed": TaskState.COMPLETED,
            "busy": TaskState.DECLINED,
            "no-answer": TaskState.NO_ANSWER,
            "no_answer": TaskState.NO_ANSWER,
            "canceled": TaskState.CANCELLED,
            "cancelled": TaskState.CANCELLED,
            "failed": TaskState.FAILED,
        }.get(provider_status)
        if mapped and mapped != result.status:
            result.status = mapped
            self.store.update(result)
        elif remote:
            # Persist merged display fields even when the status is unchanged.
            self.store.update(result)

    @staticmethod
    def _result(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_result(request_id: Any, value: Any, *, is_error: bool = False, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "structuredContent": value, "isError": is_error}
        if meta:
            payload["_meta"] = meta
        return McpServer._result(request_id, payload)


async def run_stdio(server: McpServer) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = await server.handle(message)
        except Exception:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Internal server error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
