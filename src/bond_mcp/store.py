from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from uuid import uuid4

from .models import PhoneResult, PhoneTask, TaskState


class IdempotencyConflict(RuntimeError):
    pass


class ActiveCall(RuntimeError):
    pass


class TaskStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with sqlite3.connect(self.path) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS phone_tasks (
                    call_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL,
                    result TEXT NOT NULL
                )"""
            )

    def reserve(self, task: PhoneTask) -> tuple[str, PhoneResult, bool]:
        key = task.idempotency_key or f"task:{task.task_id}"
        with self._lock, sqlite3.connect(self.path) as db:
            # Serialize the read/check/insert sequence across MCP processes as
            # well as threads. Without an immediate transaction, two local
            # clients could both observe an empty active set and dial twice.
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT call_id, payload, result FROM phone_tasks WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing:
                stored_task = json.loads(existing[1])
                if _canonical(stored_task) != _canonical(task.as_dict()):
                    raise IdempotencyConflict("Idempotency key was reused with a different task")
                return existing[0], PhoneResult(**_decode_result(existing[2])), True
            active = db.execute("SELECT result FROM phone_tasks").fetchall()
            if any(_decode_result(row[0])["status"] not in {
                TaskState.COMPLETED,
                TaskState.NO_ANSWER,
                TaskState.DECLINED,
                TaskState.FAILED,
                TaskState.CANCELLED,
            } for row in active):
                raise ActiveCall("Another phone task is already active")
            call_id = str(uuid4())
            result = PhoneResult(task_id=task.task_id, call_id=call_id, status=TaskState.CONFIRMED)
            db.execute(
                "INSERT INTO phone_tasks VALUES (?, ?, ?, ?, ?)",
                (call_id, task.task_id, key, json.dumps(task.as_dict()), json.dumps(asdict(result))),
            )
            db.commit()
            return call_id, result, False

    def get(self, call_id: str) -> PhoneResult | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT result FROM phone_tasks WHERE call_id = ?", (call_id,)).fetchone()
        return PhoneResult(**_decode_result(row[0])) if row else None

    def get_task(self, call_id: str) -> PhoneTask | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload FROM phone_tasks WHERE call_id = ?", (call_id,)).fetchone()
        if not row:
            return None
        return PhoneTask(**json.loads(row[0]))

    def update(self, result: PhoneResult) -> PhoneResult:
        with self._lock, sqlite3.connect(self.path) as db:
            db.execute("UPDATE phone_tasks SET result = ? WHERE call_id = ?", (json.dumps(asdict(result)), result.call_id))
            db.commit()
        return result


def _decode_result(raw: str) -> dict[str, object]:
    data = json.loads(raw)
    data["status"] = TaskState(data["status"])
    return data


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
