# MCP client setup

Bond-OpenAI speaks standard MCP over stdin/stdout. Keep the server local and
let the client launch it on demand.

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
or hosted callback is needed for the local connector.

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
