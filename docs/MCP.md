# MCP client setup

Bond-OpenAI speaks standard MCP over stdin/stdout. The MCP process remains
local; its provider can be either a local Fredo runtime or the operator-hosted
zero-credential demo relay.

## Codex

From the repository root:

```bash
uv run bond-mcp install --client codex --print
```

Copy the generated `bond-openai` entry into the Codex MCP configuration. The
entry is intentionally a local command:

```json
{
  "command": "uv",
  "args": ["run", "bond-mcp", "serve"],
  "cwd": "/absolute/path/to/Bond-OpenAI"
}
```

## Bond

Run:

```bash
uv run bond-mcp install --client bond --print
```

Paste the printed command entry into Bond's MCP integrations. No Bond API key
or hosted service is needed for the local connector. A live Twilio call still
needs the public HTTPS callback URL documented in `docs/TELEPHONY.md`.

## Generic MCP clients

```bash
uv run bond-mcp install --client generic --print
```

The output is provider-neutral JSON and can be adapted to any MCP client that
supports a stdio server.

## Protocol surface

- `bond.classify_task` never dials;
- `bond.create_phone_task` validates and returns a confirmation preview before
  a confirmed request can create a call;
- `bond.get_phone_task_status` returns structured status only;
- `bond.cancel_phone_task` cancels the current call when the provider supports
  cancellation.

The MCP never returns shell instructions, credentials or raw transcripts.

## No-credential demo mode

When `demo/profile.json` contains a relay URL and scoped demo token, the first
`uv run bond-mcp serve` automatically selects the `demo` provider. Jury users
do not create a Twilio account, create a Deepgram account, or edit `.env`.
Provider keys exist only on the relay. See [DEMO-RELAY.md](DEMO-RELAY.md).
