# Environment variables reference

Complete matrix of every variable from `.env.example`. Derived from existing
documentation only: [TELEPHONY.md](TELEPHONY.md),
[DEMO-RELAY.md](DEMO-RELAY.md), [SMOKE.md](SMOKE.md).

## Variable matrix

| Variable | Mock | Demo | Real PSTN | Secret? | Purpose |
|----------|------|------|-----------|---------|---------|
| `DEEPGRAM_API_KEY` | Optional | No | Yes | **Yes** | Hosted speech recognition, dialogue and TTS credential |
| `TWILIO_ACCOUNT_SID` | No | No | Yes | **Yes** | PSTN carrier authentication (Twilio account identifier) |
| `TWILIO_AUTH_TOKEN` | No | No | Yes | **Yes** | PSTN carrier authentication (Twilio account secret) |
| `TWILIO_PHONE_NUMBER` | No | No | Yes | Sensitive | Verified caller identity (E.164 format) |
| `FREDO_ALLOWED_NUMBERS` | No | Optional | Yes | Sensitive | Exact consenting destinations allowlist (comma-separated E.164) |
| `FREDO_ENDPOINT_SECRET` | No | Relay only | Yes | **Yes** | Twilio callback signature validation (generate via `openssl rand -hex 24`) |
| `FREDO_PUBLIC_URL` | No | Relay only | Yes | No | Public HTTPS callback and media WebSocket URL |
| `FREDO_DEMO_ENDPOINT` | No | Yes | No | No | Public demo relay endpoint URL (from `demo/profile.json`) |
| `FREDO_DEMO_ACCESS_TOKEN` | No | Yes | No | Scoped | Demo relay authentication token (not provider credential) |
| `FREDO_HOST` | Yes | Yes | Yes | No | Local server bind address (default: `127.0.0.1`) |
| `FREDO_PORT` | Yes | Yes | Yes | No | Local server bind port (default: `8080`) |
| `FREDO_MAX_DURATION_SECONDS` | Yes | Yes | Yes | No | Hard safety cap on call duration (max 180 seconds) |
| `FREDO_MAX_CONCURRENT_CALLS` | Yes | Yes | Yes | No | Maximum concurrent active calls (default: `1`) |
| `FREDO_LISTEN_MODEL` | Optional | Optional | Optional | No | Deepgram speech recognition model (default: `flux-general-multi`) |
| `FREDO_LISTEN_LANGUAGE` | Optional | Optional | Optional | No | Speech recognition language code (default: `en`) |
| `FREDO_EOT_THRESHOLD` | Optional | Optional | Optional | No | End-of-turn detection confidence threshold (default: `0.7`) |
| `FREDO_EOT_TIMEOUT_MS` | Optional | Optional | Optional | No | End-of-turn timeout in milliseconds (default: `7000`) |
| `FREDO_EAGER_EOT_THRESHOLD` | Optional | Optional | Optional | No | Optional eager end-of-turn threshold (leave blank unless Flux profile requires) |
| `FREDO_PROTECT_DISCLOSURE` | Yes | Yes | Yes | No | Enforce synthetic voice and no-recording disclosure (default: `1`) |
| `FREDO_SILENCE_REPROMPT_SECONDS` | Optional | Optional | Optional | No | Silence duration before agent reprompts (default: `12`) |
| `FREDO_SILENCE_GOODBYE_SECONDS` | Optional | Optional | Optional | No | Silence duration before goodbye and hangup (default: `10`) |
| `FREDO_LLM_PROVIDER` | Optional | Optional | Optional | No | LLM provider selection (default: `open_ai`) |
| `FREDO_LLM_MODEL` | Optional | Optional | Optional | No | LLM model selection (default: `gpt-4o-mini`) |
| `FREDO_VOICE_MODEL` | Optional | Optional | Optional | No | Deepgram TTS voice model (default: `aura-2-thalia-en`) |
| `FREDO_TELEPHONY_PROVIDER` | Yes | Auto | Yes | No | Provider mode: `mock` for tests, blank for auto-select demo, `real` for local |

## Usage modes

### Mock mode

For offline tests without provider credentials. Set `FREDO_TELEPHONY_PROVIDER=mock`.

**Required:** None of the provider credential variables.
**Optional:** Safety bounds, voice agent defaults, host/port configuration.

### Demo relay mode

Zero-credential jury flow via operator-published `demo/profile.json`.

**Required:**
- `FREDO_DEMO_ENDPOINT` (from profile)
- `FREDO_DEMO_ACCESS_TOKEN` (from profile)

**Not required:** Twilio or Deepgram credentials stay on the relay.

**Optional:** Safety bounds are enforced relay-side; local overrides ignored.

See [DEMO-RELAY.md](DEMO-RELAY.md) for relay operator setup.

### Real PSTN mode

Fully local operator runtime with direct provider credentials.

**Required:**
- `DEEPGRAM_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `FREDO_ALLOWED_NUMBERS`
- `FREDO_ENDPOINT_SECRET`
- `FREDO_PUBLIC_URL` (for live Twilio callbacks; use `cloudflared tunnel` for local dev)

**Optional:** Voice agent defaults, silence thresholds, LLM/TTS model overrides.

See [TELEPHONY.md](TELEPHONY.md) for media bridge and callback details.
See [SMOKE.md](SMOKE.md) for validation checklist.

## Security notes

- Never commit `.env` or any file containing real credentials
- Rotate `FREDO_DEMO_ACCESS_TOKEN` after public demos
- Generate `FREDO_ENDPOINT_SECRET` via `openssl rand -hex 24`
- Keep full phone numbers out of logs (allowed numbers are masked in output)
- Demo access tokens are scoped relay tokens, not Twilio/Deepgram credentials
- See [AGENTS.md](../AGENTS.md) safety section for complete credential policy
