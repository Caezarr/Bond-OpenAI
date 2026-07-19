from __future__ import annotations

import asyncio
import html
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urlsplit

from .models import CallRequest
from .settings import Settings


class TelephonyError(RuntimeError):
    pass


class Telephony(Protocol):
    async def place_call(self, request: CallRequest, call_id: str) -> str: ...

    async def hangup(self, provider_call_id: str) -> None: ...


def _public_endpoint(public_url: str, path: str) -> str:
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise TelephonyError("FREDO_PUBLIC_URL must be a public HTTPS URL")
    prefix = parsed.path.rstrip("/")
    return f"https://{parsed.netloc}{prefix}{path}"


def build_twiml(public_url: str, call_id: str) -> str:
    media_https = _public_endpoint(public_url, "/twilio/media")
    media_wss = "wss://" + media_https.removeprefix("https://")
    stream_url = html.escape(media_wss, quote=True)
    safe_call_id = html.escape(call_id, quote=True)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect><Stream url=\""
        f"{stream_url}\"><Parameter name=\"fredoCallId\" value=\"{safe_call_id}\" />"
        "</Stream></Connect></Response>"
    )


@dataclass(slots=True)
class TwilioTelephony:
    settings: Settings

    async def place_call(self, request: CallRequest, call_id: str) -> str:
        settings = self.settings
        required = (
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_phone_number,
            settings.public_url,
        )
        if not all(required):
            raise TelephonyError("Twilio transport is not configured")

        def _create() -> str:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            callback = _public_endpoint(
                settings.public_url or "", f"/twilio/status?call_id={quote(call_id)}"
            )
            call = client.calls.create(
                to=request.to,
                from_=settings.twilio_phone_number,
                twiml=build_twiml(settings.public_url or "", call_id),
                status_callback=callback,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
                time_limit=settings.max_duration_seconds,
            )
            return str(call.sid)

        try:
            return await asyncio.to_thread(_create)
        except Exception as exc:
            raise TelephonyError("Carrier rejected the outbound call") from exc

    async def hangup(self, provider_call_id: str) -> None:
        settings = self.settings

        def _hangup() -> None:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            client.calls(provider_call_id).update(status="completed")

        try:
            await asyncio.to_thread(_hangup)
        except Exception as exc:
            raise TelephonyError("Carrier hangup failed") from exc


class MockTelephony:
    """Deterministic test double. It is intentionally rejected by the jury CLI."""

    async def place_call(self, request: CallRequest, call_id: str) -> str:
        del request
        return f"MOCK-{call_id}"

    async def hangup(self, provider_call_id: str) -> None:
        del provider_call_id


def telephony_from_settings(settings: Settings) -> Telephony:
    if settings.telephony_provider == "mock":
        return MockTelephony()
    return TwilioTelephony(settings)
