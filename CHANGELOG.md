# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-04

### Added

#### MCP Server Tools
- `bond.classify_task(task_text, context)` - Classify and validate phone task intent
- `bond.create_phone_task(task_input, idempotency_key)` - Create a consented phone call with preview
- `bond.get_phone_task_status(call_id)` - Query the status of an active or completed call
- `bond.cancel_phone_task(call_id)` - Cancel a pending or active phone task

#### CLI Commands
- `bond-mcp doctor` - Validate environment and configuration
- `bond-mcp serve` - Start the local MCP server

#### Safety Features
- Explicit consent required before dialing
- E.164 phone number validation and allowlist enforcement
- Verified caller identity requirement
- Human confirmation before carrier call
- Single active call limit with 180-second hard cap
- Recording disabled by default
- Agent disclosure of synthetic voice and no recording
- Idempotent call creation
- Credential and PII redaction from logs

#### Documentation
- Quick start guide with bootstrap script
- MCP client setup guide
- Demo relay configuration for no-credential testing
- Safety policy documentation
- Provider architecture documentation

#### Runtime
- Twilio integration for PSTN access and verified caller
- Deepgram integration for speech recognition, dialogue, and TTS
- Fredo phone runtime as default telephony executor
- Local MCP server with provider-neutral adapter pattern

[0.1.0]: https://github.com/Caezarr/Bond-OpenAI/releases/tag/v0.1.0
