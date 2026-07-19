# GOAL — Build Bond-OpenAI end to end

Version: `1.0-execution`
Status: implementation contract

## Slash goal

```text
/gsd-autonomous Build the complete Bond-OpenAI local MCP repository from GOAL-BOND-MCP.md. Implement the generic phone-task layer, the Fredo provider adapter, the Bond/Codex MCP tools, one-command bootstrap and client installation, policy and consent gates, call lifecycle/status persistence, the zero-credential operator demo relay, documentation, tests, and a live-test checklist. Work feature-by-feature on focused branches and open one PR per feature; if GitHub access is unavailable, leave each branch and commit PR-ready and report the exact blocker. Do not add a marketplace or Bond-specific hosted dependency. Keep Twilio and Deepgram credentials relay-only, and make a configured public demo profile require no end-user API key. Do not claim completion until the repository is clean, the offline test/build/audit gates pass, and only one-time operator relay configuration plus controlled live-provider verification remain.
```

## End state

A developer can clone the repository and connect a phone action to Bond, Codex,
or any MCP-compatible client without learning the internal implementation:

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
uv run bond-mcp install --client codex
uv run bond-mcp doctor
uv run bond-mcp serve
```

Then an agent can handle:

> Call the consenting restaurant at +33600000000, reserve a table for four at
> 9 PM tonight under Gab, and tell me what they answer.

The agent extracts the task, asks only for missing fields, shows a confirmation
preview, starts one safe call, and returns a factual structured result.

At the end of implementation, the only remaining operator work is:

1. add local provider environment variables;
2. run `bond-mcp doctor`;
3. run the offline test suite;
4. perform a controlled live call to a consenting fixture.

## Product boundary

Bond-OpenAI is a local generic MCP layer. It is not a hosted marketplace, a
hosted service, a GitHub Action, or a replacement for Bond/Codex.

```text
Bond / Codex / MCP client
          ↓ standard MCP over stdio
Bond-OpenAI task layer
  classify → clarify → policy → preview → lifecycle
          ↓ provider interface
Fredo phone provider (local or operator relay)
  Twilio verified caller + Deepgram voice agent
          ↓
Structured terminal result
```

GitHub is only the distribution channel. The MCP runtime works from a local
clone; the optional zero-credential demo relay is an operator-controlled
provider boundary, not a marketplace or a Bond dependency.

## Requirements

### R1 — Generic MCP server

Implement a standard MCP server over stdio with stable, typed schemas. The
server must not require Bond-specific APIs and must be usable by Codex, Bond,
Claude Desktop or another compatible MCP client.

Required tools:

```text
bond.classify_task(task_text, context)
bond.create_phone_task(task_input, idempotency_key)
bond.get_phone_task_status(call_id)
bond.cancel_phone_task(call_id)
```

Tools return structured JSON, never shell commands or opaque instructions.

### R2 — Task understanding

Classify `phone_call`, `not_phone_call`, or `needs_input`.

Extract and validate:

- task ID;
- caller identity;
- destination in canonical E.164 format;
- concrete call goal;
- language;
- date, time, timezone and other goal-specific details;
- explicit consent.

Ask a concise clarification question when a required field is absent or
ambiguous. Never infer a phone number, consent or reservation detail.

### R3 — Provider abstraction

Create a small `PhoneProvider` interface with:

```text
create_call(request) -> provider_call_id
get_status(provider_call_id) -> provider_status
cancel_call(provider_call_id) -> provider_status
```

Keep Twilio/Deepgram code behind the Fredo adapter. Keep a deterministic fake
provider for offline tests only. The MCP contract must not expose Twilio or
Deepgram-specific fields.

### R4 — Call safety

- explicit consent required;
- canonical E.164 validation;
- exact allowlist, default deny;
- verified caller identity only;
- native/user-visible preview before dialing;
- rejected preview means zero carrier attempt;
- one active call;
- 180-second hard cap;
- recording disabled;
- synthetic-voice and no-recording disclosure at call start;
- no emergency, premium, short-code, anonymous, scraped or bulk calls;
- remote speech can only affect the current result and hangup;
- no secrets, raw audio, full transcripts or full numbers in logs.

### R5 — Lifecycle and idempotency

Persist a local correlation between `task_id`, `call_id` and provider ID.

States:

```text
detected → needs_input → ready_for_review → confirmed → dialing → in_progress
→ completed | no_answer | declined | failed | cancelled
```

Require an idempotency key. Exact replays return the original receipt and never
create a second carrier attempt. Uncertain carrier outcomes must be reconciled,
never blindly redialed.

### R6 — One-command setup

Implement:

```text
./scripts/bootstrap.sh
bond-mcp install --client codex
bond-mcp install --client bond
bond-mcp install --client generic --print
bond-mcp doctor --json
bond-mcp serve
```

`install` must be explicit about files it writes, support a print-only mode,
and never overwrite an existing client configuration without confirmation.

When the public `demo/profile.json` is configured, the same commands must
select the demo relay automatically. End users must not need provider
credentials or a local `.env` for the jury flow.

The first run installs pinned dependencies and verifies required local tools.
Local provider credentials are read only from an ignored `.env` or local secret
store. In demo mode they exist only on the operator relay; end-user machines
use the public profile and never receive them.

### R7 — Configuration

Document only the variables actually needed by the selected provider:

```text
DEEPGRAM_API_KEY
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER
FREDO_ALLOWED_NUMBERS
FREDO_ENDPOINT_SECRET
```

No credential is committed, printed, placed in a task payload or embedded in a
client configuration generated for Bond/Codex.

The demo relay may expose a narrowly scoped public demo token in
`demo/profile.json`; it is not a provider credential and is protected by relay
allowlist, consent, rate and duration gates. Twilio and Deepgram credentials
remain relay-only.

### R8 — Documentation

Provide:

- English README and short French README;
- quick start from a clean macOS clone;
- MCP configuration examples for Codex, Bond and generic clients;
- task schema and result schema;
- provider setup and environment-variable guide;
- troubleshooting and doctor output guide;
- consent/privacy and live-call checklist;
- clear distinction between mocked, offline-tested and live-qualified behavior.

Remove obsolete marketplace/provider/deployment documentation. The public repo
must describe one local MCP product, not an earlier provider experiment.

## Implementation phases

### P0 — Foundation

- create `bond_mcp` package and CLI;
- define typed input/output schemas;
- add stdio MCP transport;
- add configuration and redacted doctor;
- add bootstrap and client installer;
- make the clean clone path work.

### P1 — Task and policy layer

- implement task classifier and clarification model;
- implement E.164, consent, allowlist, language and timing validation;
- implement preview/confirmation token;
- implement idempotency and lifecycle store;
- add redaction and abuse-case tests.

### P2 — Fredo adapter

- extract the existing phone logic behind `PhoneProvider`;
- connect Twilio and Deepgram without leaking vendor fields into MCP;
- support English and French disclosure;
- implement status callbacks, cancellation and 180-second timeout;
- ensure preview rejection performs zero dial attempts.

### P3 — Client integrations

- generate Codex MCP configuration;
- generate Bond MCP configuration;
- provide generic JSON config via `--print`;
- test repeated installation and existing-config protection;
- add an end-to-end local fake-provider flow.

### P4 — Release readiness

- update all public docs and examples;
- run lint, unit tests, integration tests and package build;
- run `bond-mcp doctor --json` on a clean machine;
- execute one controlled consenting live call;
- record evidence without committing secrets, full numbers, audio or transcripts.

## Acceptance gates

### A0 — Clean repository

- no obsolete marketplace/deployment/provider references in public docs;
- no secret, `.env`, local database, transcript, recording or old Git history;
- local mode has no runtime dependency on a hosted endpoint; demo mode uses
  only the operator-controlled relay documented in `docs/DEMO-RELAY.md`;
- `git clone` followed by bootstrap reaches the CLI.

### A1 — MCP contract

- all four tools expose typed schemas;
- malformed requests return structured errors;
- the same task works from a fixture Bond client, Codex configuration and
  generic MCP configuration;
- tool output contains no shell instruction or secret.

### A2 — Policy

- missing consent, invalid number, non-allowlisted number and ambiguous intent
  create zero provider calls;
- rejecting the preview creates zero provider calls;
- 20 exact idempotency replays create exactly one provider attempt;
- one concurrent call blocks a second call;
- cancellation and timeout reach terminal states.

### A3 — Live provider

- three controlled calls to consenting fixtures ring from the verified caller;
- disclosure is audible within five seconds;
- recording remains disabled;
- English and French flows return truthful terminal summaries;
- no-answer, decline and failure remain distinct from success.

### A4 — Installation

- a fresh macOS clone starts with the documented commands;
- a configured public demo profile requires no end-user API key;
- Codex connects after one generated configuration step;
- Bond connects after one generated configuration step;
- a generic MCP client can use `--print` output;
- existing client config is never overwritten silently.

### A5 — Handoff

- README, goals, schemas and CLI agree;
- only environment variables, live provider verification and final tests remain;
- the final report lists exactly what was tested offline and live.

## Definition of done

The goal is complete when A0–A5 pass on the clean Bond-OpenAI repository and a
developer can connect an MCP-compatible client and complete one real consenting
phone task without understanding Fredo internals. Until the live gate passes,
the product must be described as implemented/offline-tested, not live-qualified.
