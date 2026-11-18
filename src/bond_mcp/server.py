"""MCP adapter: JSON-RPC over stdio, mapped onto the phone task lifecycle.

This module owns only the transport contract (MCP methods, tool schemas, result
envelopes and error codes). Every safety decision lives in ``policy``,
``store`` and ``lifecycle``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fredo.settings import Settings

from . import __version__
from .lifecycle import PhoneTaskService, ProviderFailed, error_code
from .policy import Policy, PolicyError, build_task, classify
from .providers import DemoProvider, PhoneProvider, provider_from_settings
from .runtime import RuntimeThread
from .store import ActiveCall, IdempotencyConflict, TaskStore

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "bond-openai"

_CALL_ID_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["call_id"],
    "properties": {"call_id": {"type": "string"}},
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "bond.classify_task",
        "description": "Classify whether a task needs a phone call.",
        "inputSchema": {
            "type": "object",
            "required": ["task_text"],
            "properties": {"task_text": {"type": "string"}, "context": {"type": "object"}},
        },
    },
    {
        "name": "bond.create_phone_task",
        "description": "Validate, preview and create one consented phone task.",
        "inputSchema": {
            "type": "object",
            "required": ["task_input", "idempotency_key"],
            "properties": {
                "task_input": {"type": "object"},
                "idempotency_key": {"type": "string"},
            },
        },
    },
    {
        "name": "bond.get_phone_task_status",
        "description": "Get a structured phone task result.",
        "inputSchema": _CALL_ID_SCHEMA,
    },
    {
        "name": "bond.cancel_phone_task",
        "description": "Cancel an active phone task.",
        "inputSchema": _CALL_ID_SCHEMA,
    },
]


class McpServer:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        store_path: Path | None = None,
        provider: PhoneProvider | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.policy = Policy(
            allowed_numbers=self.settings.allowed_numbers,
            max_duration_seconds=self.settings.max_duration_seconds,
        )
        self.store = TaskStore(store_path or self.settings.state_dir / "bond_tasks.sqlite3")
        self.service = PhoneTaskService(
            policy=self.policy,
            store=self.store,
            provider=provider or provider_from_settings(self.settings),
        )
        self.runtime: RuntimeThread | None = None

    @property
    def provider(self) -> PhoneProvider:
        return self.service.provider

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
            return _result(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": __version__},
                },
            )
        if method == "tools/list":
            return _result(request_id, {"tools": self.tools()})
        if method == "tools/call":
            params = message.get("params") or {}
            return await self._call_tool(
                request_id, params.get("name"), params.get("arguments") or {}
            )
        if request_id is not None:
            return _error(request_id, -32601, "Method not found")
        return None

    @staticmethod
    def tools() -> list[dict[str, Any]]:
        return TOOLS

    async def _call_tool(
        self, request_id: Any, name: str | None, args: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            if name == "bond.classify_task":
                return _tool_result(request_id, self._classify(args))
            if name == "bond.create_phone_task":
                return _tool_result(request_id, await self._create(args))
            if name == "bond.get_phone_task_status":
                result = await self.service.status(str(args.get("call_id", "")))
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                return _tool_result(request_id, result.as_dict())
            if name == "bond.cancel_phone_task":
                result = await self.service.cancel(str(args.get("call_id", "")))
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                return _tool_result(request_id, result.as_dict())
            raise PolicyError("unknown_tool", f"Unknown tool: {name}")
        except (PolicyError, IdempotencyConflict, ActiveCall) as exc:
            value = {"status": "error", "code": error_code(exc), "message": str(exc)}
            return _tool_result(request_id, value, is_error=True)

    @staticmethod
    def _classify(args: dict[str, Any]) -> dict[str, Any]:
        context = args.get("context")
        value = classify(
            str(args.get("task_text", "")),
            context if isinstance(context, dict) else None,
        )
        return {"classification": value}

    async def _create(self, args: dict[str, Any]) -> dict[str, Any]:
        payload = dict(args.get("task_input") or {})
        idempotency_key = str(args.get("idempotency_key", "")).strip()
        if not idempotency_key:
            raise PolicyError("idempotency_required", "idempotency_key is required")
        payload["idempotency_key"] = idempotency_key
        task = build_task(payload, self.policy)
        if not task.confirmed:
            return {"status": "needs_confirmation", "preview": self.service.preview(task)}
        try:
            result, replayed = await self.service.dial(task)
        except ProviderFailed as exc:
            raise PolicyError("provider_failed", str(exc)) from exc
        data = result.as_dict()
        data["replayed"] = replayed
        return data


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(request_id: Any, value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return _result(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
            "structuredContent": value,
            "isError": is_error,
        },
    )


async def run_stdio(server: McpServer) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = await server.handle(message)
        except Exception:
            response = _error(None, -32603, "Internal server error")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
