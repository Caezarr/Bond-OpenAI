# ADR 0002: Verified caller identity only

Status: accepted on 2026-07-18 for verified caller identity. The server-side
SIP gateway custody described below is superseded for the active
`hosted-voice-mvp` by [ADR 0005](0005-hosted-voice-mvp.md), which temporarily
uses the team's verified Twilio identity from the team-controlled runtime.

## Context

Some desktop calling services market arbitrary caller-ID presentation as “spoofing”. This does not remove the need for carrier infrastructure and creates fraud, blocking, and legal risk.

## Decision

The stack supports only caller identities owned by the operator's SIM or verified by the operator's SIP carrier. For the judged milestone, the team is the telecom operator: its verified identity and carrier credential remain at the server-side SIP policy gateway.

## Consequences

- caller-ID spoofing is not implemented;
- transport configuration must prove identity ownership or carrier verification;
- judges receive no credential capable of changing or bypassing the verified caller identity;
- destination policy blocks emergency, premium-rate, short-code, and prohibited numbers;
- public documentation must not imply anonymous or bulk calling capability.
