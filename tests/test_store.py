"""Task store: idempotency replay/conflict and the single-active-call guard."""

from __future__ import annotations

import pytest
from fakes import OTHER_ALLOWED, task_payload

from bond_mcp.models import PhoneTask, TaskState
from bond_mcp.policy import Policy, build_task
from bond_mcp.store import ActiveCall, IdempotencyConflict, TaskStore


def _task(policy: Policy, **overrides: object) -> PhoneTask:
    values: dict[str, object] = {"confirmed": True, "idempotency_key": "same-key", **overrides}
    return build_task(task_payload(**values), policy)


def test_store_replays_exact_idempotency(store: TaskStore, policy: Policy) -> None:
    task = _task(policy)
    first = store.reserve(task)
    second = store.reserve(task)
    assert first[0] == second[0]
    assert first[2] is False
    assert second[2] is True


def test_store_rejects_idempotency_key_reuse_with_changed_task(
    store: TaskStore, policy: Policy
) -> None:
    store.reserve(_task(policy))
    changed = _task(policy, task_id="t2", destination_phone=OTHER_ALLOWED, call_goal="Cancel")
    with pytest.raises(IdempotencyConflict):
        store.reserve(changed)


def test_store_allows_one_active_call_only(store: TaskStore, policy: Policy) -> None:
    store.reserve(_task(policy))
    with pytest.raises(ActiveCall):
        store.reserve(_task(policy, idempotency_key="other-key"))


def test_store_allows_new_call_after_terminal_state(store: TaskStore, policy: Policy) -> None:
    _, result, _ = store.reserve(_task(policy))
    result.status = TaskState.COMPLETED
    store.update(result)
    _, second, replayed = store.reserve(_task(policy, idempotency_key="other-key"))
    assert replayed is False
    assert second.status is TaskState.CONFIRMED


def test_store_round_trips_task_and_result(store: TaskStore, policy: Policy) -> None:
    task = _task(policy)
    call_id, _, _ = store.reserve(task)
    assert store.get_task(call_id) == task
    stored = store.get(call_id)
    assert stored is not None and stored.status is TaskState.CONFIRMED
    assert store.get("unknown") is None
    assert store.get_task("unknown") is None


def test_public_result_hides_provider_call_id(store: TaskStore, policy: Policy) -> None:
    _, result, _ = store.reserve(_task(policy))
    result.provider_call_id = "CA-secret"
    public = result.as_dict()
    assert "provider_call_id" not in public
    assert public["recorded"] is False
