from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Protocol

from fredo.settings import Settings
from fredo.telephony import Telephony, telephony_from_settings

from .models import PhoneTask


class PhoneProvider(Protocol):
    async def create_call(self, task: PhoneTask, call_id: str) -> str: ...
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

    async def cancel_call(self, provider_call_id: str) -> None:
        await self.telephony.hangup(provider_call_id)
