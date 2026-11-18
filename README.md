# Bond-OpenAI: a safe phone action for any agent

[![ci](https://github.com/Caezarr/Bond-OpenAI/actions/workflows/ci.yml/badge.svg)](https://github.com/Caezarr/Bond-OpenAI/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![OpenAI Codex Hackathon: finalist](https://img.shields.io/badge/OpenAI_Codex_Hackathon-finalist-412991)](README.md)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB.svg)](pyproject.toml)
[![MCP server](https://img.shields.io/badge/MCP-server-000000.svg)](https://modelcontextprotocol.io)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-2a6db2.svg)](pyproject.toml)
[![lint: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](pyproject.toml)

**Agents can read, write and click. Then the workflow needs a phone call, and they stop.**

A local MCP server that lets Codex, Bond or any MCP client place one consented, human-confirmed, time-boxed phone call and get a structured result back into the task. Finalist at the OpenAI Codex Hackathon.

*Français : [README.fr.md](README.fr.md)*

## The problem

Booking a restaurant, chasing an administration, confirming an appointment, asking a supplier for a quote: in many real workflows the blocking step is not the reasoning, it is calling a person. Agents can prepare everything up to that point and then hand the task back to you. Giving an agent a raw telephony API is not the answer: nothing stops it from dialing the wrong number, calling twice on a retry, recording without consent or talking for twenty minutes. The phone call has to be an action with the same guarantees you would expect from a careful assistant.

## How it solves it

Bond-OpenAI exposes the phone as four MCP tools with a fixed flow: **classify → clarify → preview → explicit confirmation → verified call → structured result**.

```text
Agent task ("call the restaurant and reserve a table")
        ↓  MCP over stdio
Local Bond-OpenAI MCP
  classify → clarify → preview → explicit confirmation → call
        ↓
Fredo phone runtime
  Twilio verified caller ID + Deepgram voice agent, 180 s cap
        ↓
Structured result (status, outcome, summary) returned to the task
```

Key design decisions:

- **Two-step creation.** `bond.create_phone_task` without `confirmed: true` returns a preview and stores nothing. A human approves, the agent repeats the call with `confirmed: true`. Rejecting the preview means zero carrier calls.
- **Policy outside the model.** Consent must be literal `true`; the destination must be a canonical E.164 number on an exact allowlist; the caller ID is always the operator's verified number. The task input cannot change caller ID, recording or duration.
- **Idempotent and single-flight.** An idempotency key is required; a replay returns the stored result, a changed payload is rejected, a failed attempt is never redialed. One active call at a time, enforced in SQLite across processes.
- **Provider-neutral core.** `policy`, `lifecycle` and `store` import no transport and no vendor SDK (pinned by a test). Twilio and Deepgram sit behind a `PhoneProvider` seam.

## Try it (2 minutes, no credentials)

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/) (the bootstrap script installs uv if it is missing, and `cloudflared` through Homebrew if Homebrew is present).

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git && cd Bond-OpenAI
./scripts/bootstrap.sh
```

Without provider keys, the bootstrap ends with a diagnostic, not an error you need to fix:

```text
  "mcp": "ready",
  "missing": [ "DEEPGRAM_API_KEY", "TWILIO_ACCOUNT_SID", ... ]
No demo relay profile is published. An operator must configure demo/profile.json or local provider variables.
```

Now drive the MCP by hand in **mock mode** (a deterministic fake carrier, no network). The session classifies a task, asks for a preview, confirms it, then tries a number that is not on the allowlist:

```bash
cat > /tmp/bond-session.jsonl <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"bond.classify_task","arguments":{"task_text":"Call +15555550100 and reserve a table for two at 8pm"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"bond.create_phone_task","arguments":{"idempotency_key":"demo-1","task_input":{"task_id":"demo-1","caller_identity":"Assistant for Alex","destination_phone":"+15555550100","call_goal":"Reserve a table for two tonight at 8pm","consent_confirmed":true}}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"bond.create_phone_task","arguments":{"idempotency_key":"demo-1","task_input":{"task_id":"demo-1","caller_identity":"Assistant for Alex","destination_phone":"+15555550100","call_goal":"Reserve a table for two tonight at 8pm","consent_confirmed":true,"confirmed":true}}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"bond.create_phone_task","arguments":{"idempotency_key":"demo-2","task_input":{"task_id":"demo-2","caller_identity":"x","destination_phone":"+15555550199","call_goal":"x","consent_confirmed":true,"confirmed":true}}}}
EOF
FREDO_TELEPHONY_PROVIDER=mock FREDO_ALLOWED_NUMBERS=+15555550100 FREDO_STATE_DIR="$(mktemp -d)" \
  uv run bond-mcp serve < /tmp/bond-session.jsonl
```

Expected `structuredContent` of the four responses (the process then keeps its carrier-callback server open; stop it with Ctrl-C):

```text
{"classification": "phone_call"}
{"status": "needs_confirmation", "preview": {"destination_phone": "+15555550100", "caller_identity": "Assistant for Alex", "call_goal": "Reserve a table for two tonight at 8pm", "recorded": false, "max_duration_seconds": 180}}
{"task_id": "demo-1", "call_id": "<uuid>", "status": "dialing", "outcome": null, "summary": null, "recorded": false, "error": null, "replayed": false}
{"status": "error", "code": "destination_not_allowed", "message": "Destination is not pre-enrolled"}
```

Run the offline test suite (fake carrier, no network):

```bash
uv run pytest      # 90 passed
```

### Real calls

A real PSTN call needs a Twilio account with a verified caller number (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`), a Deepgram key (`DEEPGRAM_API_KEY`), an exact allowlist of consenting numbers (`FREDO_ALLOWED_NUMBERS`), an endpoint secret (`FREDO_ENDPOINT_SECRET`) and a public HTTPS callback URL for Twilio (`FREDO_PUBLIC_URL`). See [docs/ENV.md](docs/ENV.md) and [docs/TELEPHONY.md](docs/TELEPHONY.md). `uv run bond-mcp doctor` lists what is still missing.

Alternatively, an operator can host the [demo relay](docs/DEMO-RELAY.md), which holds the provider keys; clients then only need the relay URL and a scoped token in `demo/profile.json`. No public relay is configured in this repository today.

To connect an agent, print its MCP entry with `uv run bond-mcp install --client codex|bond|generic --print` ([docs/MCP.md](docs/MCP.md)).

## How it works

| Tool | What it does |
| --- | --- |
| `bond.classify_task(task_text, context)` | `phone_call`, `needs_input` or `not_phone_call`. Never dials. |
| `bond.create_phone_task(task_input, idempotency_key)` | Preview without `confirmed: true`; with it, exactly one call per idempotency key. |
| `bond.get_phone_task_status(call_id)` | Structured result: status, outcome, summary. |
| `bond.cancel_phone_task(call_id)` | Hangs up an active call. |

`server.py` is a thin JSON-RPC adapter; `policy.py` validates and classifies; `lifecycle.py` (`PhoneTaskService`) runs preview, dial, status and cancel; `store.py` holds idempotency keys and the single-active-call guard in SQLite. `fredo/` is the carrier runtime: Twilio REST calls, a signed status callback and media WebSocket, and a bridge to one Deepgram Voice Agent session that discloses it is a synthetic voice, does not record, and hangs up on silence. Terminal states are never overwritten. Input and result shapes are in [schemas/](schemas/).

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) is a five-minute read: components, the call state machine, trust boundaries, and where each safety invariant is enforced.

## Proof in the repo

- **90 offline tests** (`tests/`), no network. Each safety invariant in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#safety-invariants) maps to the code that enforces it and is pinned by a test: consent, allowlist, preview-before-dial, idempotency and replay, no blind redial, one active call, 180 s cap, verified caller ID, no recording, signed callbacks, no secrets in results.
- **Static checks:** `ruff` (lint and format), `mypy`.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint, format, mypy, pytest and `uv build` on every push and pull request.
- Design decision record: [docs/decisions/0001-verified-caller-identity.md](docs/decisions/0001-verified-caller-identity.md).

## Limits and status

- One call at a time, 180 seconds maximum. This is a guarded action, not a dialer, and does not do unattended bulk calling.
- Speech recognition, dialogue and synthesis are hosted by Deepgram; PSTN goes through Twilio. Nothing runs inference locally, and there is no recording or voice cloning.
- Status is eventually consistent between callbacks and polling; the first terminal value wins.
- The SQLite store is local to one machine; the demo relay keeps its own store.
- Version 0.1.0. Provider versions and alternatives: [docs/PROVIDER-MATRIX.md](docs/PROVIDER-MATRIX.md).

## Development

```bash
uv sync --frozen --extra dev
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy
uv run pytest        # offline: fake carrier, no network
uv build
```

Help and how to report issues safely: [SUPPORT.md](SUPPORT.md), [SECURITY.md](SECURITY.md). Contributions: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE). Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
