"""Safety contract of the provider-neutral lifecycle, exercised with a fake carrier."""

from __future__ import annotations

import pytest
from fakes import FakeProvider, task_payload

from bond_mcp.lifecycle import PROVIDER_STATES, PhoneTaskService, ProviderFailed
from bond_mcp.models import TERMINAL_STATES, PhoneTask, TaskState
from bond_mcp.policy import Policy, PolicyError, build_task
from bond_mcp.store import ActiveCall, IdempotencyConflict


def _confirmed(policy: Policy, key: str = "k1", **overrides: object) -> PhoneTask:
    return build_task(task_payload(confirmed=True, idempotency_key=key, **overrides), policy)


def test_preview_describes_call_without_touching_provider(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    preview = service.preview(build_task(task_payload(), policy))
    assert preview["recorded"] is False
    assert preview["max_duration_seconds"] == 180
    assert provider.created == []


async def test_dial_refuses_unconfirmed_task(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    with pytest.raises(PolicyError) as exc:
        await service.dial(build_task(task_payload(idempotency_key="k1"), policy))
    assert exc.value.code == "confirmation_required"
    assert provider.created == []


async def test_dial_places_one_call_and_replays(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    task = _confirmed(policy)
    first, replayed_first = await service.dial(task)
    second, replayed_second = await service.dial(task)
    assert (replayed_first, replayed_second) == (False, True)
    assert first.call_id == second.call_id
    assert first.status is TaskState.DIALING
    assert len(provider.created) == 1


async def test_idempotency_conflict_never_reaches_provider(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    await service.dial(_confirmed(policy))
    with pytest.raises(IdempotencyConflict):
        await service.dial(_confirmed(policy, call_goal="Something else"))
    assert len(provider.created) == 1


async def test_second_active_call_is_refused_before_provider(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    await service.dial(_confirmed(policy))
    with pytest.raises(ActiveCall):
        await service.dial(_confirmed(policy, key="k2"))
    assert len(provider.created) == 1


async def test_provider_failure_is_recorded_and_never_redialed(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    provider.fail_create = True
    task = _confirmed(policy)
    with pytest.raises(ProviderFailed):
        await service.dial(task)
    replay, replayed = await service.dial(task)
    assert replayed is True
    assert replay.status is TaskState.FAILED
    assert replay.error == "phone provider rejected the call"
    assert len(provider.created) == 1


async def test_status_maps_provider_state(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    result, _ = await service.dial(_confirmed(policy))
    provider.status = "in-progress"
    refreshed = await service.status(result.call_id)
    assert refreshed is not None and refreshed.status is TaskState.IN_PROGRESS
    assert await service.status("unknown") is None


async def test_terminal_status_is_not_refreshed(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    result, _ = await service.dial(_confirmed(policy))
    provider.status = "completed"
    await service.status(result.call_id)
    provider.status = "in-progress"
    final = await service.status(result.call_id)
    assert final is not None and final.status is TaskState.COMPLETED


async def test_cancel_hangs_up_active_call_once(
    service: PhoneTaskService, policy: Policy, provider: FakeProvider
) -> None:
    result, _ = await service.dial(_confirmed(policy))
    cancelled = await service.cancel(result.call_id)
    again = await service.cancel(result.call_id)
    assert cancelled is not None and cancelled.status is TaskState.CANCELLED
    assert again is not None and again.status is TaskState.CANCELLED
    assert provider.cancelled == [f"provider-{result.call_id}"]
    assert await service.cancel("unknown") is None


def test_every_mapped_provider_state_is_a_task_state() -> None:
    assert set(PROVIDER_STATES.values()) <= set(TaskState)
    assert TERMINAL_STATES <= set(TaskState)
