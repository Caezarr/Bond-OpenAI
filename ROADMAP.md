# Bond-OpenAI roadmap

## P0 — Local MCP vertical slice

- expose `classify_task`, `create_phone_task`, `get_phone_task_status` and
  `cancel_phone_task`;
- map one normalized task into the existing Fredo call runtime;
- support English and French;
- preserve consent, preview, allowlist, idempotency and no-recording gates;
- return a terminal structured result.

## P1 — Universal client setup

- one bootstrap command;
- one MCP configuration snippet for Bond;
- one MCP configuration snippet for Codex;
- documented generic stdio transport;
- doctor command with redacted diagnostics.

## P2 — Product proof

- Bond task classification fixtures;
- live reservation demo with a consenting fixture;
- task completion payload and concise summary;
- website and eight-slide deck using the same design system.

## P3 — Provider adapters

- keep Fredo as the default phone executor;
- add a provider interface for another carrier or local voice engine;
- never couple the MCP contract to one vendor.
