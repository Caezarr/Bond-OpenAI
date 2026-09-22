# Bond — provider / telephony failure runbook

What to do when Deepgram, the MCP phone path, or the demo relay misbehaves. Complements `docs/TELEPHONY.md` and `docs/MCP.md`.

## Symptoms

- MCP phone tools time out or return empty transcripts
- Demo relay (`docs/DEMO-RELAY.md`) connects but audio is silent
- uvicorn / starlette errors after a dependency bump

## First checks

1. Confirm `.env` matches `.env.example` keys — no placeholder tokens in the active shell.
2. Health: hit the local HTTP health endpoint if exposed; otherwise start with `uv run` / project scripts from README and watch stderr.
3. Isolate layers: MCP tool only → demo relay → full telephony path.
4. If a Dependabot PR just landed (starlette / uvicorn / deepgram-sdk majors), roll back that bump before deep debugging.

## Deepgram failures

- 401/403 → API key scope or revoked key; rotate and update env.
- 429 → back off; do not tight-loop MCP retries from the client.
- Empty transcript → check sample rate / codec assumptions in `docs/TELEPHONY.md`.

## MCP client failures

- Client pointing at the wrong host/port after a reload.
- Process crashed mid-session — restart the MCP server, then retry a single cheap tool.
- Never paste live tokens into issue trackers; use `SECURITY.md`.

## After a major dependency bump

1. Recreate the venv / `uv sync`.
2. Run the test suite (`pytest` / project script).
3. Smoke one MCP phone action in a dry environment.
4. Only merge Dependabot majors when the above is green (keep large majors gated).

## Escalation

Capture: UTC timestamp, tool name, request id if any, package versions (`uv pip freeze` snippet without secrets), and whether demo relay was involved.
