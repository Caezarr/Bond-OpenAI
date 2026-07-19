# Human setup: one-click demo

This is the operator checklist for a demo where a non-technical user never
enters a Twilio, Deepgram, OpenAI, or relay credential.

## What the user experiences

1. Clone the repository (or open the prepared Bond/Codex workspace).
2. Run `./scripts/bootstrap.sh` once. It installs the pinned dependencies.
3. Install the generated MCP configuration in Codex/Bond.
4. Write one normal request, for example:

   > Call the consenting restaurant at +33600000000 and reserve a table for four at 9 PM tonight under Gab.

The local MCP reads the public `demo/profile.json`, sends only the structured
task to the relay, and returns the call result and concise summary. No user
`.env` and no provider key are needed.

## The phone surface inside Codex (nothing to configure)

Once the MCP is installed, the live phone appears **inside the Codex
conversation** on its own, no extra setup:

1. You ask for a call in plain language.
2. Codex confirms the preview (who, why, number masked).
3. After you confirm, a phone card renders in the chat and updates live:
   status (Dialing -> Connected -> Done), a running timer, the goal, and a
   final result summary. The full number is never shown (masked as
   `+33 •••• ••78`), nothing is recorded.
4. `Hang up` ends the call; `Refresh` re-checks status.

How it works: the MCP serves the widget as an app resource
(`ui://fredo/phone-call-v2.html`) and attaches it to `bond.create_phone_task`.
Codex renders it and drives it only through the safe `bond.*` tools. If the
client cannot render apps, everything still works as plain text.

### Live listening (optional, operator-enabled)

The `Listen` button is **listen-only** and appears only while a call is
`in_progress` **and** an audio relay is configured. To enable it, set
`FREDO_AUDIO_STREAM_ORIGIN` to the single HTTPS origin that serves the mixed,
non-recorded live stream. Left empty, the button stays hidden and calls run
normally. The audio stream reaches only the widget through short-lived,
one-time metadata; it is never logged, persisted, or shown to the model.

## Operator setup (one time)

The operator owns the provider account and the relay. Provider secrets never
go in Git, `demo/profile.json`, prompts, screenshots, or jury machines.

1. Deploy `render.demo.yaml` to a private operator-controlled Render service,
   or run `uv run bond-mcp relay` on a machine reachable through HTTPS.
2. Set the relay variables in the host's secret environment:
   `DEEPGRAM_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
   `TWILIO_PHONE_NUMBER`, `FREDO_ENDPOINT_SECRET`,
   `FREDO_ALLOWED_NUMBERS`, and `FREDO_PUBLIC_URL`.
   For today's public demo, also set `FREDO_DEMO_PUBLIC=1`. No relay token is
   placed in GitHub or on jury machines.
3. Keep `FREDO_TELEPHONY_PROVIDER=real`, `FREDO_MAX_CONCURRENT_CALLS=1`,
   and the 180-second default for the demo.
4. Verify `GET /healthz` and `uv run bond-mcp doctor --json` before publishing.
5. Publish only the relay URL:

   ```bash
   uv run bond-mcp demo configure \
     --endpoint https://relay.example.com \
     --public
   ```

6. Commit and push `demo/profile.json`. Disable public mode after the event.

## Fast local rehearsal

For a short controlled rehearsal, start the relay with the operator `.env`,
open a temporary HTTPS tunnel (for example `cloudflared tunnel --url
http://127.0.0.1:8080`), set `FREDO_PUBLIC_URL` to that URL, restart the relay,
and run the same health and doctor checks. A quick tunnel is ephemeral: do not
publish its URL as the permanent jury profile.

## Go/no-go checklist

- [ ] The exact consenting destination is in `FREDO_ALLOWED_NUMBERS` in E.164.
- [ ] Twilio Geo Permissions allow that destination's country.
- [ ] Twilio caller ID is verified and can place the call.
- [ ] Deepgram and Twilio credentials are set only on the relay.
- [ ] `FREDO_PUBLIC_URL` is HTTPS and reachable from the public internet.
- [ ] `/healthz` returns `200` and `doctor --json` reports no missing values.
- [ ] The first live call is explicitly confirmed by the consenting participant.
- [ ] After the demo, disable `FREDO_DEMO_PUBLIC` or stop the relay.
