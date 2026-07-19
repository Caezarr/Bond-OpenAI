# Bond-OpenAI goals

The repository has two independent goals:

- [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) — local, generic MCP software layer.
- [GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) — website, deck and product story.

The runtime distribution is intentionally simple: clone the repository,
bootstrap once, start the MCP, and connect any compatible agent. No marketplace
provider or hosted deployment is required for the local integration path.

## Execution command

Copy this into Codex to execute the software goal:

```text
/gsd-autonomous Build the complete Bond-OpenAI local MCP repository from GOAL-BOND-MCP.md. Implement the generic phone-task layer, the Fredo provider adapter, the Bond/Codex MCP tools, one-command bootstrap and client installation, policy and consent gates, call lifecycle/status persistence, documentation, tests, and a live-test checklist. Work feature-by-feature on focused branches and open one PR per feature; if GitHub access is unavailable, leave each branch and commit PR-ready and report the exact blocker. Do not add a marketplace, hosted deployment, or vendor-specific platform layer. Do not claim completion until the repository is clean, the offline test/build/audit gates pass, and only environment variables plus controlled live-provider verification remain.
```
