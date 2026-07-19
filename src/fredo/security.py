from __future__ import annotations

from collections.abc import Mapping


def validate_twilio_signature(
    auth_token: str,
    url: str,
    params: Mapping[str, str],
    signature: str,
) -> bool:
    """Validate a Twilio webhook signature without exposing request data."""
    try:
        from twilio.request_validator import RequestValidator

        return RequestValidator(auth_token).validate(url, dict(params), signature)
    except Exception:
        return False
