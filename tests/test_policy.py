"""Policy boundary: classification, E.164, allowlist, consent and input limits."""

from __future__ import annotations

import pytest
from fakes import ALLOWED, NOT_ALLOWED, task_payload

from bond_mcp.policy import Policy, PolicyError, build_task, classify


def test_classifies_phone_tasks_without_dialing() -> None:
    assert classify("Call the restaurant and confirm the reservation") == "needs_input"
    assert classify("Call +33600000000 and confirm the reservation") == "phone_call"
    assert classify("Update the project document") == "not_phone_call"


def test_classify_uses_context_destination() -> None:
    assert classify("Call the restaurant", {"destination_phone": ALLOWED}) == "phone_call"


def test_policy_normalizes_allowlist_and_rejects_invalid_entries() -> None:
    assert Policy(frozenset({"+33 6 00 00 00 00"})).allowed_numbers == frozenset({ALLOWED})
    with pytest.raises(PolicyError) as exc:
        Policy(frozenset({"not-a-number"}))
    assert exc.value.code == "invalid_destination"


def test_formatted_destination_matches_canonical_allowlist_entry() -> None:
    task = build_task(task_payload(destination_phone="+33 (6) 00-00-00-00"), Policy(frozenset({ALLOWED})))
    assert task.destination_phone == ALLOWED


def test_destination_outside_allowlist_is_rejected() -> None:
    with pytest.raises(PolicyError) as exc:
        build_task(task_payload(destination_phone=NOT_ALLOWED), Policy(frozenset({ALLOWED})))
    assert exc.value.code == "destination_not_allowed"


def test_empty_allowlist_rejects_every_destination() -> None:
    with pytest.raises(PolicyError) as exc:
        build_task(task_payload(), Policy(frozenset()))
    assert exc.value.code == "destination_not_allowed"


@pytest.mark.parametrize("value", ["0600000000", "+0600000000", "+336", 33600000000, None])
def test_non_e164_destination_is_rejected(value: object) -> None:
    with pytest.raises(PolicyError) as exc:
        build_task(task_payload(destination_phone=value), Policy(frozenset({ALLOWED})))
    assert exc.value.code in {"invalid_destination", "needs_input"}


@pytest.mark.parametrize("consent", [None, False, "true", "yes", 1])
def test_consent_must_be_literal_true(consent: object) -> None:
    payload = task_payload(consent_confirmed=consent)
    if consent is None:
        payload.pop("consent_confirmed")
    with pytest.raises(PolicyError) as exc:
        build_task(payload, Policy(frozenset({ALLOWED})))
    assert exc.value.code == "consent_required"


@pytest.mark.parametrize("confirmed", [None, False, "true", 1])
def test_confirmation_is_only_set_by_literal_true(confirmed: object) -> None:
    task = build_task(task_payload(confirmed=confirmed), Policy(frozenset({ALLOWED})))
    assert task.confirmed is False


def test_missing_fields_need_input() -> None:
    with pytest.raises(PolicyError) as exc:
        build_task(task_payload(call_goal="  "), Policy(frozenset({ALLOWED})))
    assert exc.value.code == "needs_input"
    assert "call_goal" in str(exc.value)


def test_rejects_unsupported_language_and_oversized_goal() -> None:
    policy = Policy(frozenset({ALLOWED}))
    with pytest.raises(PolicyError) as exc:
        build_task(task_payload(language="de"), policy)
    assert exc.value.code == "invalid_language"
    with pytest.raises(PolicyError) as exc:
        build_task(task_payload(call_goal="x" * 501), policy)
    assert exc.value.code == "invalid_goal"


def test_non_object_task_is_rejected() -> None:
    with pytest.raises(PolicyError) as exc:
        build_task(["not", "a", "dict"], Policy(frozenset({ALLOWED})))
    assert exc.value.code == "invalid_task"
