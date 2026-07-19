---
name: fredo-call
description: Use the local Bond-OpenAI MCP to place one safe, consented phone call.
---

# Fredo phone action

Use the local MCP for a task that genuinely requires speaking to a person.

## One-time setup

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
uv run bond-mcp doctor
uv run bond-mcp serve
```

The first run installs pinned dependencies. Never ask the user to paste a
secret into a prompt or task. Credentials stay in the local ignored `.env` or
configured secret store.

## Invocation contract

Use the MCP tools in this order:

1. `bond.classify_task` with the user's task and available context.
2. Ask only for missing destination, purpose, caller identity, language,
   timing or consent.
3. `bond.create_phone_task` with normalized E.164 data and an idempotency key.
4. Wait for the user to confirm the Fredo preview.
5. After confirmation, let the Fredo phone surface display and control the live
   call. Poll `bond.get_phone_task_status` until terminal only when the client
   cannot render the phone surface.
6. If live listening is available, it is opt-in and listen-only. The user must
   start it from the phone surface; never request microphone access.

The call must identify itself as an automated synthetic voice and state that it
is not recorded. Return the carrier-backed answer and a concise factual summary.

## Hard rules

- Never dial without explicit consent and preview confirmation.
- Never spoof caller ID or call emergency, premium or bulk destinations.
- Never record audio. Never put raw audio, stream credentials, or transcripts
  in model-visible content, logs, or persistent storage. A user-initiated live
  stream may reach only the phone widget through short-lived hidden metadata.
- Never retry an uncertain carrier outcome blindly.
- A carrier request accepted is not a completed task; require a terminal result.
- Never claim that a visible phone surface means the carrier answered. Treat the
  structured terminal state as authoritative.
