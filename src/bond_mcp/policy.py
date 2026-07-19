from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import PhoneTask

E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")

# Emergency short numbers (digits only). E.164 already excludes most of these by
# length, but this is an explicit second gate that must hold even in full-auto.
EMERGENCY_NUMBERS = frozenset(
    {"112", "911", "999", "000", "110", "111", "113", "114", "115", "119", "15", "17", "18"}
)

# Baseline premium / surtaxe / international-premium E.164 prefixes. Not
# exhaustive; extensible via `Policy.extra_forbidden_prefixes`. Kept even when
# unlisted destinations are allowed, because auto-dialing these enables fraud.
DENY_PREFIXES = (
    "+1900",   # US/CA premium
    "+449",    # UK 09 premium
    "+4487",   # UK personal/premium
    "+33899",  # FR service surtaxe
    "+33897",
    "+33898",
    "+33890",  # FR audiotel
    "+33891",
    "+33892",
    "+979",    # International Premium Rate Service
)


class PolicyError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Policy:
    allowed_numbers: frozenset[str]
    max_duration_seconds: int = 180
    # Full-auto knobs. When `allow_unlisted` is set, the static allowlist is not
    # required, but E.164 validation and the forbidden blocklist ALWAYS run.
    allow_unlisted: bool = False
    autoconfirm: bool = False
    extra_forbidden_prefixes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        # Normalize the operator-supplied allowlist once at the policy boundary.
        # Invalid entries fail closed instead of becoming unreachable targets.
        normalized = frozenset(normalize_phone(value) for value in self.allowed_numbers)
        object.__setattr__(self, "allowed_numbers", normalized)


def normalize_phone(value: Any) -> str:
    if not isinstance(value, str):
        raise PolicyError("invalid_destination", "destination_phone must be a string")
    normalized = re.sub(r"[\s().-]", "", value.strip())
    if not E164_RE.fullmatch(normalized):
        raise PolicyError("invalid_destination", "destination_phone must use E.164 format")
    return normalized


def is_forbidden_destination(
    e164: str, extra_prefixes: frozenset[str] = frozenset()
) -> bool:
    """Block emergency, premium and short-code destinations.

    This gate is non-negotiable: it runs on every call, including full-auto,
    because dialing these numbers with an automated agent is abusive or illegal.
    """
    digits = e164.lstrip("+")
    if digits in EMERGENCY_NUMBERS:
        return True
    for prefix in (*DENY_PREFIXES, *extra_prefixes):
        if e164.startswith(prefix):
            return True
    return False


def build_task(payload: Any, policy: Policy) -> PhoneTask:
    if not isinstance(payload, dict):
        raise PolicyError("invalid_task", "task_input must be an object")
    required = ("task_id", "caller_identity", "destination_phone", "call_goal")
    missing = [name for name in required if not isinstance(payload.get(name), str) or not payload[name].strip()]
    if missing:
        raise PolicyError("needs_input", f"Missing required fields: {', '.join(missing)}")
    destination = normalize_phone(payload["destination_phone"])
    # Non-negotiable gate: emergency/premium/short-code numbers are rejected even
    # in full-auto mode with the allowlist disabled.
    if is_forbidden_destination(destination, policy.extra_forbidden_prefixes):
        raise PolicyError(
            "destination_forbidden",
            "Destination is a forbidden (emergency/premium/short-code) number",
        )
    if not policy.allow_unlisted and destination not in policy.allowed_numbers:
        raise PolicyError("destination_not_allowed", "Destination is not pre-enrolled")
    if payload.get("consent_confirmed") is not True and not policy.autoconfirm:
        raise PolicyError("consent_required", "Explicit recipient consent is required")
    language = payload.get("language", "en")
    if language not in {"en", "fr"}:
        raise PolicyError("invalid_language", "language must be en or fr")
    goal = " ".join(payload["call_goal"].split())
    if len(goal) > 500:
        raise PolicyError("invalid_goal", "call_goal must be at most 500 characters")
    return PhoneTask(
        task_id=payload["task_id"].strip(),
        caller_identity=payload["caller_identity"].strip(),
        destination_phone=destination,
        call_goal=goal,
        consent_confirmed=True,
        language=language,
        timezone=payload.get("timezone", "Europe/Brussels"),
        idempotency_key=str(payload.get("idempotency_key", "")),
        confirmed=(payload.get("confirmed") is True) or policy.autoconfirm,
        destination_source=_clean_source(payload.get("destination_source")),
        recipient_label=_clean_label(payload.get("recipient_label")),
    )


def _clean_label(value: Any) -> str | None:
    """A human display name for the widget; never used for routing."""
    if not isinstance(value, str):
        return None
    label = " ".join(value.split())[:80]
    return label or None


def _clean_source(value: Any) -> dict[str, str] | None:
    """Keep provenance for audit only; it is never trusted for safety."""
    if not isinstance(value, dict):
        return None
    allowed = ("method", "url", "query", "confidence")
    cleaned = {k: str(value[k])[:300] for k in allowed if value.get(k) is not None}
    return cleaned or None


def classify(text: str, context: dict[str, Any] | None = None) -> str:
    """Classify a request without making a carrier call."""
    text = text.strip()
    lowered = text.lower()
    phone_words = (
        "call", "phone", "ring", "telephone", "appelle", "appeler",
        "téléphone", "réserve", "reservation", "réservation",
    )
    if not any(word in lowered for word in phone_words):
        return "not_phone_call"
    context = context or {}
    combined = f"{text} {context.get('destination_phone', '')}"
    has_destination = bool(re.search(r"\+[1-9][0-9\s().-]{7,18}", combined))
    return "phone_call" if has_destination else "needs_input"
