from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Protocol

import httpx

from fredo.settings import Settings
from fredo.telephony import Telephony, telephony_from_settings

from .models import PhoneTask


class PhoneProvider(Protocol):
    async def create_call(self, task: PhoneTask, call_id: str) -> str: ...

    async def get_status(self, provider_call_id: str) -> str: ...

    async def cancel_call(self, provider_call_id: str) -> None: ...


@dataclass(slots=True)
class FredoProvider:
    settings: Settings
    telephony: Telephony

    @classmethod
    def from_settings(cls, settings: Settings) -> "FredoProvider":
        return cls(settings=settings, telephony=telephony_from_settings(settings))

    async def create_call(self, task: PhoneTask, call_id: str) -> str:
        # The existing media bridge reads only `to` and `intent`; the MCP keeps
        # its own provider-neutral task contract at this boundary.
        request = SimpleNamespace(to=task.destination_phone, intent=task.call_goal)
        return await self.telephony.place_call(request, call_id)

    async def get_status(self, provider_call_id: str) -> str:
        return await self.telephony.get_status(provider_call_id)

    async def cancel_call(self, provider_call_id: str) -> None:
        await self.telephony.hangup(provider_call_id)


@dataclass(slots=True)
class DemoProvider:
    """Client for the operator-hosted, zero-credential demo relay.

    The access token is a deliberately scoped demo credential, never a Twilio
    or Deepgram secret. The relay still enforces its own allowlist and limits.
    """

    endpoint: str
    access_token: str | None = None
    timeout_seconds: float = 15.0
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json", "user-agent": "bond-openai-mcp/0.1"}
        if self.access_token:
            headers["authorization"] = f"Bearer {self.access_token}"
        return headers

    async def create_call(self, task: PhoneTask, call_id: str) -> str:
        body = {"task": task.as_dict(), "client_call_id": call_id}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.post(
                    f"{self.endpoint.rstrip('/')}/v1/calls",
                    headers=self._headers(),
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("Demo relay is unavailable") from exc
        provider_call_id = payload.get("call_id") or payload.get("provider_call_id")
        if not isinstance(provider_call_id, str) or not provider_call_id:
            raise RuntimeError("Demo relay returned an invalid call receipt")
        return provider_call_id

    async def get_status(self, provider_call_id: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.get(
                    f"{self.endpoint.rstrip('/')}/v1/calls/{provider_call_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("Demo relay status is unavailable") from exc
        status = payload.get("status")
        if not isinstance(status, str):
            raise RuntimeError("Demo relay returned an invalid status")
        return status

    async def cancel_call(self, provider_call_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.post(
                    f"{self.endpoint.rstrip('/')}/v1/calls/{provider_call_id}/cancel",
                    headers=self._headers(),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Demo relay cancellation failed") from exc


def provider_from_settings(settings: Settings) -> PhoneProvider:
    if settings.telephony_provider == "demo":
        if not settings.demo_endpoint:
            raise ValueError("FREDO_DEMO_ENDPOINT is required for demo mode")
        return DemoProvider(settings.demo_endpoint, settings.demo_access_token)
    return FredoProvider.from_settings(settings)
