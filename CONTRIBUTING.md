# Contributing

Read [README.md](README.md), [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md),
[GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) and [SECURITY.md](SECURITY.md).

- Keep the MCP local, generic and easy to connect to any compatible client.
- Keep Bond-specific translation at the adapter boundary.
- Preserve consent, preview, allowlisting, verified caller ID and idempotency.
- Keep Fredo as a replaceable phone provider, not the MCP contract.
- Never commit credentials, real phone numbers, transcripts or recordings.
- Label mocked, offline-tested, live-qualified and planned behavior separately.

Verify changes with:

```bash
uv sync --frozen --extra dev
uv run ruff check src tests
uv run pytest
uv build
git diff --check
```
