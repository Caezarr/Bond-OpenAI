# Smoke testing checklist

Local MCP + telephony smoke validation before merge. Run this checklist after
dependency updates, telephony provider changes, or MCP contract modifications.

## Prerequisites

- [ ] Repository cloned and current working directory is project root
- [ ] No uncommitted changes that could interfere with testing
- [ ] Test phone number consented and available for outbound test

## Environment setup

```bash
./scripts/bootstrap.sh
```

- [ ] `uv` installed successfully (via Homebrew or fallback installer)
- [ ] `uv sync --frozen --extra dev` completed without errors
- [ ] No missing pinned dependencies in frozen lockfile

## MCP server validation

```bash
uv run bond-mcp doctor
```

- [ ] Doctor check passes with valid configuration
- [ ] If demo relay configured: `demo/profile.json` contains valid endpoint + token
- [ ] If local provider: `.env` contains required Twilio + Deepgram credentials
- [ ] No secrets printed to stdout during doctor check

```bash
uv run bond-mcp serve
```

- [ ] Server starts without errors
- [ ] Stdio transport ready (observe startup log)
- [ ] Stop with `Ctrl+C` after validation

## Provider configuration

### Demo relay mode

- [ ] `demo/profile.json` contains operator relay endpoint
- [ ] Demo access token is scoped (not a Twilio/Deepgram credential)
- [ ] No `.env` required for jury machine flow

### Local provider mode

From `.env.example`, verify `.env` contains:

- [ ] `DEEPGRAM_API_KEY` (for voice agent)
- [ ] `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- [ ] `FREDO_ALLOWED_NUMBERS` (exact E.164, comma-separated, consenting only)
- [ ] `FREDO_ENDPOINT_SECRET` (generated via `openssl rand -hex 24`)
- [ ] `FREDO_PUBLIC_URL` if testing live Twilio callbacks
- [ ] Safety bounds: `FREDO_MAX_DURATION_SECONDS=180`, `FREDO_MAX_CONCURRENT_CALLS=1`

## MCP client connection

Choose one client for smoke testing:

### Codex

```bash
uv run bond-mcp install --client codex --print
```

- [ ] Generated MCP entry is valid JSON
- [ ] `cwd` path is absolute and points to this repository
- [ ] Entry added to Codex MCP configuration
- [ ] Codex recognizes `bond.*` tools after MCP restart

### Bond

```bash
uv run bond-mcp install --client bond --print
```

- [ ] Command entry printed for Bond integrations
- [ ] Entry pasted into Bond MCP configuration
- [ ] Bond shows 4 available `bond.*` tools

### Generic client

```bash
uv run bond-mcp install --client generic --print
```

- [ ] Provider-neutral JSON output
- [ ] Stdio command and args present
- [ ] Adaptable to any MCP client

## MCP tool contract

From the connected MCP client, validate each tool:

### 1. Classify task (never dials)

```text
bond.classify_task(
  task_text="Call the restaurant and reserve a table",
  context={}
)
```

- [ ] Returns classification (e.g., `phone_call`)
- [ ] Returns confidence score
- [ ] No dial attempt occurs
- [ ] No secrets in response

### 2. Create phone task (preview required)

```text
bond.create_phone_task(
  task_input={
    "destination": "+33600000000",
    "intent": "reserve a table for four at 9 PM",
    "context": {"recipient_name": "Restaurant Example"}
  },
  idempotency_key="smoke-test-001"
)
```

- [ ] Returns confirmation preview (not a live call)
- [ ] Shows masked destination hint (not full number)
- [ ] Requires explicit confirmation before dialing
- [ ] Rejects if destination not in allowlist
- [ ] Rejects duplicate idempotency key with identical result

### 3. Confirmed call (local provider only)

**Skip this step in demo relay mode unless operator permits test calls.**

With confirmed task:

- [ ] Call initiates only after explicit user confirmation
- [ ] Twilio status callback received (if `FREDO_PUBLIC_URL` configured)
- [ ] Media WebSocket establishes after carrier answer
- [ ] Deepgram voice agent greeting plays
- [ ] Bidirectional audio verified (speak + agent response)
- [ ] Barge-in works (interrupt agent mid-sentence)
- [ ] Hard hangup terminates call cleanly
- [ ] 180-second timeout enforced for long calls
- [ ] No recording created (verify in Twilio console)

### 4. Get task status

```text
bond.get_phone_task_status(call_id="<call-id-from-create>")
```

- [ ] Returns structured status (e.g., `completed`, `failed`, `in_progress`)
- [ ] Includes outcome summary when available
- [ ] Does not leak raw Twilio SID or full phone numbers
- [ ] Does not return raw transcripts or audio

### 5. Cancel task

```text
bond.cancel_phone_task(call_id="<call-id-from-active-call>")
```

- [ ] Cancels active call if provider supports it
- [ ] Returns error gracefully if call already completed
- [ ] Does not allow canceling another user's call

## Safety boundaries

- [ ] Only verified caller identity used (from `TWILIO_PHONE_NUMBER`)
- [ ] Allowlist enforced: unauthorized destinations rejected before dial
- [ ] One concurrent call: second create fails while first is active
- [ ] Duration cap: calls terminate at 180 seconds maximum
- [ ] Recording disabled: no Twilio recording resource created
- [ ] Agent disclosure: synthetic voice announced, no recording disclosed
- [ ] Idempotency: duplicate key returns cached result without redialing
- [ ] Preview preservation: rejecting confirmation creates zero carrier call
- [ ] Credentials masked: no secrets in logs, MCP responses, or agent output
- [ ] No blind redial: uncertain carrier outcome requires manual reconciliation

## Telephony-specific validation (local provider)

### Twilio callbacks

If `FREDO_PUBLIC_URL` is configured:

- [ ] Public HTTPS URL reachable (use `cloudflared tunnel` for local dev)
- [ ] Status callbacks validate `X-Twilio-Signature`
- [ ] Forged callbacks rejected
- [ ] Media WebSocket handshake validates signature
- [ ] Opaque Fredo call ID matches Twilio SID before media starts

### Provider failure handling

- [ ] Twilio API errors normalized (see `docs/PROVIDER-FAILURE.md`)
- [ ] Deepgram connection failure reported gracefully
- [ ] Timeout during carrier answer does not leave zombie call
- [ ] Process crash after Twilio accept: no automatic retry (manual reconciliation)

## Cleanup

- [ ] Stop any running `uv run bond-mcp serve` processes
- [ ] Remove test `.env` if created for smoke testing
- [ ] Verify no test call IDs left in local SQLite store (optional)
- [ ] No credentials committed to version control

## Success criteria

All checkboxes pass before merging dependency bumps or telephony changes.

For demo relay smoke tests, skip the "Confirmed call" step unless the operator
explicitly permits test calls during the smoke run.

For local provider smoke tests, complete the full call lifecycle including
bidirectional audio, barge-in, timeout enforcement, and recording absence
verification.

## Related documentation

- **[MCP.md](MCP.md)** — MCP client setup for Bond, Codex, generic clients
- **[DEMO-RELAY.md](DEMO-RELAY.md)** — Zero-credential jury mode
- **[TELEPHONY.md](TELEPHONY.md)** — Twilio callbacks and media bridge details
- **[PROVIDER-FAILURE.md](PROVIDER-FAILURE.md)** — Provider error handling
- **[ENV.md](ENV.md)** — Complete environment variable matrix and usage modes
- **[../.env.example](../.env.example)** — Example configuration template
