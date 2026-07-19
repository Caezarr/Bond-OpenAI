# Security boundary

Bond-OpenAI is a local MCP that can trigger real telephone calls. The default
policy is deny-by-default.

- Consent must be explicit and visible.
- Destinations must be canonical E.164 and allowlisted.
- Caller ID comes only from the configured verified carrier number.
- The local preview is mandatory; closing it means no dial.
- One active call is enforced. Call duration defaults to a hard 180-second cap.
  Exceeding it is possible only with the explicit `FREDO_ALLOW_EXTENDED_CALLS=1`
  opt-in and remains hard-capped at 3600 seconds; longer calls increase cost and
  exposure and are an operator decision, not the default posture.
- Recording is disabled.
- The voice agent cannot change the destination, invoke tools or read secrets.
- Call creation is idempotent and uncertain outcomes are never blindly retried.
- Twilio webhooks and media streams require signature validation.
- Secrets live only in an ignored local `.env` or a secret store.
- Logs contain no credentials, raw audio, full transcripts or full phone numbers.

The current runtime uses provider-backed speech processing. Do not claim that
call audio never leaves the local machine until a separately qualified local
voice profile exists.
