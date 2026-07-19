# Bond-OpenAI — voice actions for every software agent

**One local MCP server. Any compatible agent. One phone task completed.**

Bond-OpenAI gives Bond, Codex and other MCP-compatible software a safe
telephone action. Clone the repository, bootstrap once, connect the MCP, and
let the agent turn a task such as “call the restaurant and reserve a table”
into a real consented conversation.

## The product

```text
Bond task / Codex prompt
        ↓
Local Bond-OpenAI MCP
  classify → clarify → preview → call
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
Credentials are read from an ignored local `.env` or a configured secret
store.

## MCP tools

```text
bond.classify_task(task_text, context)
bond.create_phone_task(task_input, idempotency_key)
bond.get_phone_task_status(call_id)
bond.cancel_phone_task(call_id)
```

The same contract works from Bond, Codex, an IDE agent, or any MCP client. The
adapter is local and provider-neutral; Fredo is the default phone executor.

See [docs/MCP.md](docs/MCP.md) for the two-click client setup.

## Safety by default

- explicit consent is required;
- E.164 destinations and Fredo's exact allowlist are enforced;
- only a verified caller identity is used;
- a human confirmation happens before dialing;
- one active call and a 180-second cap;
- recording is disabled;
- the agent discloses its synthetic voice and no recording;
- duplicate requests are idempotent;
- raw audio, secrets and full phone numbers stay out of logs.

Rejecting the preview means zero carrier call.

## Project goals

- [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) — software and MCP contract.
- [GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) — website, deck and visual system.
- [GOAL-BOND-VOICE.md](GOAL-BOND-VOICE.md) — goal index.

## Current runtime boundary

The current phone engine uses Twilio for PSTN access and Deepgram for hosted
speech recognition, dialogue and text-to-speech. The MCP itself runs locally.
This repository does not claim local inference, recording, voice cloning or
unattended bulk calling.
