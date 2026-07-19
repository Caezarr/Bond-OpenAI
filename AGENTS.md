# AGENTS.md

Read [GOAL.md](GOAL.md), then the relevant Bond goal. This repository builds a
local, generic MCP phone action distributed by cloning the repository.

## Product boundary

- Bond/Codex provide task context and intent.
- The MCP classifies, clarifies, validates and requests confirmation.
- Fredo is the default telephony executor.
- Twilio supplies the verified caller and PSTN.
- Deepgram supplies hosted speech recognition, dialogue and TTS in the current
  profile.

Never describe hosted speech processing as local inference.

## Safety

- Require explicit consent and exact canonical E.164 destinations.
- Keep an exact allowlist and verified caller identity.
- Preserve the native preview; rejection means zero carrier call.
- Allow one active call and a 180-second hard cap.
- Disable recording and disclose synthetic voice plus no recording.
- Require idempotency for call creation.
- Validate Twilio callback and media signatures.
- Never blind-redial an uncertain carrier outcome.
- Keep credentials, raw audio, transcripts and full numbers out of logs.

## Workflow

1. Keep one local vertical path working.
2. Keep the MCP transport-neutral and provider-adapter based.
3. Add offline positive, negative, replay, policy and redaction tests.
4. Run `uv sync --frozen --extra dev`, lint, tests, build and `git diff --check`.

Separate implemented, offline-tested, live-qualified and planned behavior.
