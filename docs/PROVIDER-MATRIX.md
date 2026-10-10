# Provider matrix

Bond-OpenAI distributes a **local MCP server** with provider adapters for
hosted telephony and speech services. This document defines the runtime
boundary and current pinned versions.

## Runtime boundary

```text
┌─────────────────────────────────────────────┐
│ Local components                            │
├─────────────────────────────────────────────┤
│ Bond / Codex / compatible MCP client        │
│   • Task context and intent                 │
│                                             │
│ Bond-OpenAI MCP server                      │
│   • Classification                          │
│   • Clarification                           │
│   • Validation                              │
│   • Confirmation request                    │
│   • Transport-neutral interface             │
│                                             │
│ Fredo telephony executor                    │
│   • Provider adapter                        │
│   • Call lifecycle management               │
│   • Status persistence                      │
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│ Hosted services                             │
├─────────────────────────────────────────────┤
│ Twilio                                      │
│   • Verified caller identity                │
│   • PSTN access                             │
│                                             │
│ Deepgram                                    │
│   • Hosted speech recognition               │
│   • Hosted dialogue                         │
│   • Hosted text-to-speech                   │
└─────────────────────────────────────────────┘
```

## Pinned dependencies

Current major and minor versions after the deepgram 7.9 merge:

| Package        | Version  | Purpose                              |
|----------------|----------|--------------------------------------|
| deepgram-sdk   | 7.12.0   | Hosted speech recognition and TTS    |
| twilio         | 9.11.2   | PSTN telephony and verified caller   |
| starlette      | 1.7.0    | MCP HTTP transport                   |
| uvicorn        | 0.54.0   | ASGI server                          |
| httpx          | 0.28.1   | HTTP client                          |
| PyJWT          | 2.15.1   | Token validation                     |
| python-dotenv  | 1.2.4    | Environment configuration            |

See `pyproject.toml` for exact pinned versions.

## Gated major version updates

The following Dependabot major version updates remain gated behind validation
in [issue #31](https://github.com/Caezarr/Bond-OpenAI/issues/31):

- Further starlette 1.x minors and related majors require CI validation,
  full test suite pass, and smoke testing of one MCP phone path before merge.

Do not merge Dependabot PRs for gated packages until issue #31 is resolved.

## What this means

- **Local inference**: This repository does not provide local speech processing.
  Deepgram performs hosted speech recognition, dialogue and TTS.
- **Recording**: Recording is disabled by policy; no audio is persisted.
- **Voice cloning**: Not provided.
- **Bulk calling**: Not supported; one active call with 180-second hard cap.
- **Verified caller**: Twilio supplies caller verification; Fredo relays it.

The MCP layer is transport-neutral and provider-adapter based. Alternative
telephony or speech providers can be added by implementing the Fredo adapter
contract.
