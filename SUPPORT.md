# Support

Bond-OpenAI is a local MCP server that connects software agents to real
telephone calls. If you need help setting up the MCP, configuring providers, or
running your first phone task, you're in the right place.

## Getting help with setup

### Setup questions and troubleshooting

For questions about:

- Installing dependencies and bootstrapping the environment
- Connecting the MCP to Bond, Codex or other clients
- Configuring the demo relay or local provider
- Understanding the MCP tool contract and safety boundaries

**Open a GitHub Issue or start a Discussion.**

When sharing setup problems, always mask or redact:

- API keys, auth tokens and endpoint secrets
- Phone numbers (use `+1555EXAMPLE` or similar placeholders)
- Full error messages that might contain credentials

See [`.env.example`](.env.example) for a complete list of configuration keys.

### Documentation references

- **[docs/MCP.md](docs/MCP.md)** — MCP client setup for Bond, Codex and generic clients
- **[docs/DEMO-RELAY.md](docs/DEMO-RELAY.md)** — zero-credential demo mode for jury machines
- **[docs/TELEPHONY.md](docs/TELEPHONY.md)** — Twilio callback URLs and local runtime setup
- **[.env.example](.env.example)** — environment variables and provider configuration

### Security vulnerabilities

**Do not open public issues for security vulnerabilities.**

See [SECURITY.md](SECURITY.md) for the private security reporting process.

## What never goes in a public issue

**Never paste in issues, discussions or pull requests:**

- Twilio account SIDs or auth tokens (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`)
- Deepgram API keys (`DEEPGRAM_API_KEY`)
- Endpoint secrets (`FREDO_ENDPOINT_SECRET`)
- Demo relay access tokens (`FREDO_DEMO_ACCESS_TOKEN`)
- Real phone numbers or allowlists (`FREDO_ALLOWED_NUMBERS`, `TWILIO_PHONE_NUMBER`)

Use redacted placeholders when describing configuration problems. The community
can still help debug most setup issues without seeing your real credentials.

## Contributing

If you'd like to contribute code, documentation or design improvements, see
[CONTRIBUTING.md](CONTRIBUTING.md).
