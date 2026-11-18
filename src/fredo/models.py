from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CallRequest:
    """The only call data the carrier transport needs: who to dial and why.

    Consent, confirmation, allowlist and idempotency are enforced upstream by
    ``bond_mcp`` before a CallRequest is ever built.
    """

    to: str
    intent: str
