from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import PhoneTask

E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


class PolicyError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Policy:
    allowed_numbers: frozenset[str]
    max_duration_seconds: int = 180


def normalize_phone(value: Any) -> str:
    if not isinstance(value, str):
        raise PolicyError("invalid_destination", "destination_phone must be a string")
    normalized = re.sub(r"[\s().-]", "", value.strip())
    if not E164_RE.fullmatch(normalized):
        raise PolicyError("invalid_destination", "destination_phone must use E.164 format")
    return normalized


def build_task(payload: Any, policy: Policy) -> PhoneTask:
    if not isinstance(payload, dict):
        raise PolicyError("invalid_task", "task_input must be an object")
    required = ("task_id", "caller_identity", "destination_phone", "call_goal")
    missing = [name for name in required if not isinstance(payload.get(name), str) or not payload[name].strip()]
    if missing:
        raise PolicyError("needs_input", f"Missing required fields: {', '.join(missing)}")
    destination = normalize_phone(payload["destination_phone"])
    if destination not in policy.allowed_numbers:
        raise PolicyError("destination_not_allowed", "Destination is not pre-enrolled")
    if payload.get("consent_confirmed") is not True:
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
        confirmed=payload.get("confirmed") is True,
    )


def classify(text: str) -> str:
    lowered = text.lower()
    phone_words = ("call", "phone", "ring", "appelle", "téléphone", "réserve", "reservation")
    return "phone_call" if any(word in lowered for word in phone_words) else "not_phone_call"
