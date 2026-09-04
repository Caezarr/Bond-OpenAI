# Quick Start

Get Bond-OpenAI running in minutes and make your first phone call from any MCP-compatible agent.

## Prerequisites

- Python 3.12 or 3.13
- Git
- An MCP-compatible client (Bond, Codex, Claude Desktop, or compatible)

## Installation

Clone and bootstrap the repository:

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
```

The bootstrap script installs all pinned dependencies and sets up local tools.

## Verify Installation

Check that everything is configured correctly:

```bash
uv run bond-mcp doctor
```

## Start the MCP Server

Launch the local MCP server:

```bash
uv run bond-mcp serve
```

The server runs locally and provides four MCP tools to any connected client.

## Connect Your MCP Client

Configure your MCP client to connect to Bond-OpenAI. See [MCP.md](MCP.md) for detailed client setup instructions.

## Demo Mode (No Credentials Required)

For testing without provider credentials, use the public demo relay:

1. Copy the demo profile:
   ```bash
   cp demo/profile.example.json demo/profile.json
   ```

2. Start the server (it will use the demo relay automatically)

3. Create a phone task from your agent

See [DEMO-RELAY.md](DEMO-RELAY.md) for the complete no-credential jury flow.

## Production Setup

For direct provider access (required for production use):

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Add your provider credentials to `.env`:
   - Twilio account SID and auth token
   - Twilio verified phone number
   - Deepgram API key

3. Never commit `.env` to version control

## Available MCP Tools

Once connected, your agent can use these tools:

- `bond.classify_task(task_text, context)` - Classify and validate phone task intent
- `bond.create_phone_task(task_input, idempotency_key)` - Create a consented phone call with preview
- `bond.get_phone_task_status(call_id)` - Query call status
- `bond.cancel_phone_task(call_id)` - Cancel a pending or active call

## Safety Features

Every phone call includes:

- ✓ Explicit user consent required
- ✓ E.164 validation and allowlist enforcement
- ✓ Human confirmation before dialing
- ✓ Single active call limit (180-second cap)
- ✓ No recording by default
- ✓ Credential and PII redaction from logs

**Rejecting the preview means zero carrier call.**

## Next Steps

- Read [MCP.md](MCP.md) for MCP client configuration
- Review [TELEPHONY.md](TELEPHONY.md) for telephony architecture
- Check [SECURITY.md](../SECURITY.md) for security policies
- Explore [AGENTS.md](../AGENTS.md) for development workflow

## Troubleshooting

If you encounter issues:

1. Run `uv run bond-mcp doctor` to validate configuration
2. Check that Python 3.12+ is installed: `python --version`
3. Verify uv is available: `uv --version`
4. Ensure the MCP server is running before connecting clients
5. Review logs for credential or network errors

For demo mode issues, verify that `demo/profile.json` exists and contains valid relay configuration.
