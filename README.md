# Bond-OpenAI — voice actions for every software agent

**Agents can read, write and click. Then the workflow needs a phone call, and they stop.**

Booking a restaurant, chasing an administration, confirming an appointment,
asking a supplier for a quote: in a huge number of real workflows the blocking
step is not the reasoning, it is calling a person. Bond-OpenAI removes that
blocker. It gives Bond, Codex and any MCP-compatible agent a safe telephone
action, so the agent can finish the task instead of handing it back to you.

**One local MCP server. Any compatible agent. One phone task completed.**

Clone the repository, bootstrap once, connect the MCP, and
let the agent turn a task such as “call the restaurant and reserve a table”
into a real consented conversation.

## The product

```text
Bond task / Codex prompt
        ↓
Local Bond-OpenAI MCP
  classify → clarify → preview → explicit confirmation → call
        ↓
Fredo phone runtime
  Twilio verified caller + Deepgram voice agent
        ↓
Structured result returned to the originating task
```

Bond finds the work. Codex understands the intent. Fredo makes the call.

## Quick start

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
uv run bond-mcp doctor
uv run bond-mcp serve
```

The first run installs pinned dependencies and local tools. The user never
copies shell commands from an agent response and never puts a secret in a task.
For the public demo, provider credentials stay in the operator relay and the
user only needs the public `demo/profile.json` configuration. A local `.env`
is required only when running the provider directly.

## MCP tools

| Tool | What it does |
| --- | --- |
| `bond.classify_task(task_text, context)` | Says whether a task needs a call (`phone_call`, `needs_input`, `not_phone_call`). Never dials. |
| `bond.create_phone_task(task_input, idempotency_key)` | Without `confirmed: true`, returns a preview and dials nothing. With it, places exactly one call per idempotency key. |
| `bond.get_phone_task_status(call_id)` | Returns the structured result: status, outcome, summary. |
| `bond.cancel_phone_task(call_id)` | Hangs up an active call. |

The same contract works from Bond, Codex, an IDE agent, or any MCP client.
Input and result shapes are in [schemas/](schemas/); client setup is in
[docs/MCP.md](docs/MCP.md), the no-credential jury flow in
[docs/DEMO-RELAY.md](docs/DEMO-RELAY.md), and every environment variable in
[docs/ENV.md](docs/ENV.md).

## Safety by default

- explicit recipient consent is required;
- destinations must be canonical E.164 numbers on an exact allowlist;
- only the operator's verified caller ID is used;
- a human confirms the preview before dialing; rejecting it means zero carrier calls;
- one active call at a time, hard-capped at 180 seconds by both Twilio and the runtime;
- recording is disabled, and the agent discloses that it is a synthetic voice and not recording;
- creation requires an idempotency key; a failed attempt is never redialed automatically;
- Twilio callbacks are signature-checked;
- raw audio, secrets and full phone numbers stay out of logs and results.

Where each rule is enforced in code, and the offline tests that pin them, are listed in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#safety-invariants).

## Architecture

```text
src/bond_mcp/server.py      MCP adapter (JSON-RPC over stdio)
src/bond_mcp/lifecycle.py   provider-neutral core: preview, dial, status, cancel
src/bond_mcp/policy.py      consent, E.164, allowlist, classification
src/bond_mcp/store.py       SQLite idempotency + one-active-call guard
src/bond_mcp/providers.py   Fredo (local Twilio + Deepgram) or demo relay
src/fredo/                  carrier runtime: telephony, voice agent, silence handling
```

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) is a five-minute read covering
components, the call state machine, trust boundaries and safety invariants.

## Development

```bash
uv sync --frozen --extra dev
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy
uv run pytest        # offline: fake carrier, no network
uv build
```

## Support

Need help with setup, configuration or MCP connections? See
[SUPPORT.md](SUPPORT.md) for documentation links and how to ask questions
safely.

Bond-OpenAI is free software. Consider [sponsoring development on GitHub](https://github.com/sponsors/Caezarr).

## Project goals

- [GOAL-BOND-MCP.md](docs/goals/GOAL-BOND-MCP.md) — software and MCP contract.
- [GOAL-BOND-DESIGN.md](docs/goals/GOAL-BOND-DESIGN.md) — website, deck and visual system.
- [GOAL-BOND-VOICE.md](docs/goals/GOAL-BOND-VOICE.md) — goal index.

## Current runtime boundary

The current phone engine uses Twilio for PSTN access and Deepgram for hosted
speech recognition, dialogue and text-to-speech. The MCP itself runs locally.
This repository does not claim local inference, recording, voice cloning or
unattended bulk calling.

See [docs/PROVIDER-MATRIX.md](docs/PROVIDER-MATRIX.md) for the complete
provider matrix and current pinned dependency versions.
