# Zero-credential demo relay

The local MCP never needs a user's Twilio or Deepgram key. For a public demo,
run the included relay once with the operator's provider credentials. Jury
machines only receive the public relay profile in `demo/profile.json`.

## Operator setup (one time)

1. Deploy `render.demo.yaml` (or `deploy/Dockerfile.relay`) to a private
   operator-controlled service.
2. Set the relay-only secrets in the hosting dashboard:
   `DEEPGRAM_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
   `TWILIO_PHONE_NUMBER` and `FREDO_ENDPOINT_SECRET`.
3. Set `FREDO_PUBLIC_URL` to the service's public HTTPS URL. For today's
   public demo, set `FREDO_DEMO_PUBLIC=1` and
   `FREDO_ALLOW_UNLISTED_DESTINATIONS=1`. This removes the static number list
   but keeps E.164, forbidden-number, explicit-consent and confirmation gates.
4. From the repository root, publish the public profile with one command:

   ```bash
   uv run bond-mcp demo configure \
     --endpoint https://your-relay.example.com \
     --public
   ```

   Commit only the resulting public profile. The command refuses to overwrite
   an active profile unless `--force` is explicitly supplied.

The public mode still enforces E.164 validation, forbidden-number blocking,
consent, preview, one active call, 180-second duration and rate limits. Disable
it after the demo. A private
token-authenticated relay remains available when public mode is off. Never
place Twilio or Deepgram credentials in `profile.json`.

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

The MCP sends only the structured task to the relay. It never sends provider
secrets, raw audio or full transcripts.

## Relay endpoints

- `GET /healthz`
- `POST /v1/calls`
- `GET /v1/calls/{call_id}`
- `POST /v1/calls/{call_id}/cancel`

In public demo mode, `/v1/*` is protected by the allowlist, consent gate,
rate limit and single-active-call policy instead of a client token. Private
mode requires `Authorization: Bearer <demo-access-token>`.
Twilio status and media callbacks are validated separately with
`X-Twilio-Signature`.
