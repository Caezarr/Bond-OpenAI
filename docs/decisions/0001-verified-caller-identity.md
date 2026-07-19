# ADR 0001: verified caller identity only

Status: accepted

## Context

Desktop caller-ID spoofing does not remove the need for carrier infrastructure
and creates fraud, blocking and legal risk. Bond-OpenAI must make one explicit,
operator-owned call identity available to the phone provider without exposing
carrier credentials to the MCP client or remote callee.

## Decision

The Fredo adapter uses only the configured Twilio number, which must be owned or
verified by the operator. The task schema never accepts a caller-ID override.
The provider chooses the caller identity from local configuration and the MCP
exposes only a redacted confirmation preview.

## Consequences

- caller-ID spoofing is not implemented;
- the carrier account must verify the configured caller number;
- judges and agents cannot change or bypass caller identity;
- public documentation does not imply anonymous, scraped or bulk calling;
- a live qualification must verify the number and carrier geographic permissions.
