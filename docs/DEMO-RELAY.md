# Zero-credential demo relay

The local MCP never needs a user's Twilio or Deepgram key. For a public demo,
run the included relay once with the operator's provider credentials. Jury
machines only receive the public relay profile in `demo/profile.json`.

## Operator setup (one time)

1. Deploy `render.demo.yaml` (or `deploy/Dockerfile.relay`) to a private
   operator-controlled service.
2. Set the relay-only secrets in the hosting dashboard:
   `DEEPGRAM_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
   `TWILIO_PHONE_NUMBER`, `FREDO_ENDPOINT_SECRET` and
   `FREDO_DEMO_ACCESS_TOKEN`.
3. Set `FREDO_ALLOWED_NUMBERS` to exact consenting E.164 destinations and
   `FREDO_PUBLIC_URL` to the service's public HTTPS URL.
4. Copy `demo/profile.example.json` to `demo/profile.json`, put the relay URL
   and the scoped demo access token in it, and commit only that public profile.

The demo access token is not a provider credential. It is intentionally
scoped to the demo relay, and the relay still enforces allowlist, consent,
preview, one active call, 180-second duration and rate limits. Rotate it after
the demo. Never place Twilio or Deepgram credentials in `profile.json`.

## Jury flow

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
uv run bond-mcp install --client codex --print
```

No `.env`, Twilio account, Deepgram account or API key is required on the jury
machine once `demo/profile.json` points at the live relay. The first prompt can
then be a normal task such as:

> Call the consenting restaurant at +33600000000 and reserve a table for four
> at 9 PM tonight under Gab.

The MCP sends only the structured task and public demo token to the relay. It
never sends provider secrets, raw audio or full transcripts.

## Relay endpoints

- `GET /healthz`
- `POST /v1/calls`
- `GET /v1/calls/{call_id}`
- `POST /v1/calls/{call_id}/cancel`

All `/v1/*` endpoints require `Authorization: Bearer <demo-access-token>`.
Twilio status and media callbacks are validated separately with
`X-Twilio-Signature`.
