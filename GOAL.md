# Bond-OpenAI goals

The repository has two independent goals:

- [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) — local, generic MCP software layer.
- [GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) — website, deck and product story.

The runtime distribution is intentionally simple: clone the repository,
bootstrap once, start the MCP, and connect any compatible agent. No marketplace
provider is required for the local integration path. The optional public demo
path uses the operator-controlled relay described in `docs/DEMO-RELAY.md`, so
jury machines never receive provider credentials.

## Execution command

Copy this into Codex to execute the software goal:

```text
/gsd-autonomous Build the complete Bond-OpenAI local MCP repository from GOAL-BOND-MCP.md. Implement the generic phone-task layer, the Fredo provider adapter, the Bond/Codex MCP tools, one-command bootstrap and client installation, policy and consent gates, call lifecycle/status persistence, the zero-credential operator demo relay, documentation, tests, and a live-test checklist. Work feature-by-feature on focused branches and open one PR per feature; if GitHub access is unavailable, leave each branch and commit PR-ready and report the exact blocker. Do not add a marketplace or Bond-specific hosted dependency. Keep Twilio and Deepgram credentials relay-only, and make a configured public demo profile require no end-user API key. Do not claim completion until the repository is clean, the offline test/build/audit gates pass, and only one-time operator relay configuration plus controlled live-provider verification remain.
```
