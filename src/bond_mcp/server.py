from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fredo.settings import Settings

from .models import TaskState
from .policy import Policy, PolicyError, build_task, classify
from .providers import FredoProvider
from .runtime import RuntimeThread
from .store import ActiveCall, IdempotencyConflict, TaskStore


class McpServer:
    def __init__(self, settings: Settings | None = None, *, store_path: Path | None = None):
        self.settings = settings or Settings.from_env()
        self.policy = Policy(
            allowed_numbers=self.settings.allowed_numbers,
            max_duration_seconds=self.settings.max_duration_seconds,
        )
        self.store = TaskStore(store_path or self.settings.state_dir / "bond_tasks.sqlite3")
        self.provider = FredoProvider.from_settings(self.settings)
        self.runtime: RuntimeThread | None = None

    def start_runtime(self) -> None:
        """Start the local Twilio/Deepgram callback runtime beside stdio MCP."""
        if self.runtime is None:
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
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bond-openai", "version": "0.1.0"},
            })
        if method == "tools/list":
            return self._result(request_id, {"tools": self.tools()})
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
            {"name": "bond.create_phone_task", "description": "Validate, preview and create one consented phone task.", "inputSchema": {"type": "object", "required": ["task_input", "idempotency_key"], "properties": {"task_input": {"type": "object"}, "idempotency_key": {"type": "string"}}}},
            {"name": "bond.get_phone_task_status", "description": "Get a structured phone task result.", "inputSchema": {"type": "object", "required": ["call_id"], "properties": {"call_id": {"type": "string"}}}},
            {"name": "bond.cancel_phone_task", "description": "Cancel an active phone task.", "inputSchema": {"type": "object", "required": ["call_id"], "properties": {"call_id": {"type": "string"}}}},
        ]

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
                    return self._tool_result(request_id, {"status": "needs_confirmation", "preview": {"destination_phone": task.destination_phone, "caller_identity": task.caller_identity, "call_goal": task.call_goal, "recorded": False, "max_duration_seconds": self.policy.max_duration_seconds}})
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
                return self._tool_result(request_id, data)
            if name == "bond.get_phone_task_status":
                result = self.store.get(str(args.get("call_id", "")))
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                return self._tool_result(request_id, result.as_dict())
            if name == "bond.cancel_phone_task":
                result = self.store.get(str(args.get("call_id", "")))
                if result is None:
                    raise PolicyError("not_found", "Unknown call_id")
                if result.status not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.NO_ANSWER, TaskState.DECLINED}:
                    if result.provider_call_id:
                        await self.provider.cancel_call(result.provider_call_id)
                    result.status = TaskState.CANCELLED
                    self.store.update(result)
                return self._tool_result(request_id, result.as_dict())
            raise PolicyError("unknown_tool", f"Unknown tool: {name}")
        except (PolicyError, IdempotencyConflict, ActiveCall) as exc:
            code = getattr(exc, "code", "idempotency_conflict" if isinstance(exc, IdempotencyConflict) else "call_busy")
            return self._tool_result(request_id, {"status": "error", "code": code, "message": str(exc)}, is_error=True)

    @staticmethod
    def _result(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_result(request_id: Any, value: Any, *, is_error: bool = False) -> dict[str, Any]:
        return McpServer._result(request_id, {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "structuredContent": value, "isError": is_error})


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
