# Fredo telephony and media path

Status: Twilio/Deepgram implementation exists; live carrier qualification is
pending.

## Why a carrier is unavoidable

Deepgram provides voice intelligence, not PSTN termination. Reaching a normal
phone number requires a carrier account and verified caller identity. The MVP
uses Twilio. Desktop caller-ID “spoofing” is neither required nor supported.

## Outbound call creation

Fredo accepts only a request already checked for:

- structurally valid, unexpired local MCP task fields;
- canonical E.164 destination in the operator's exact allowlist;
- explicit recipient consent;
- native confirmation;
- one active call;
- required idempotency key.

The API never accepts a caller-ID or callback URL. `TwilioTelephony` selects the
configured verified caller number and derives callbacks from
`FREDO_PUBLIC_URL`.

Inline TwiML is generated locally:

```xml
<Response>
  <Connect>
    <Stream url="wss://PUBLIC/twilio/media">
      <Parameter name="fredoCallId" value="OPAQUE_UUID" />
    </Stream>
  </Connect>
</Response>
```

Twilio receives a 180-second `time_limit` plus status callbacks for initiated,
ringing, answered and completed states.

## Media bridge

Twilio sends JSON Media Stream events containing base64 μ-law audio. Fredo:

1. decodes base64;
2. sends raw μ-law bytes to Deepgram Voice Agent;
3. receives raw μ-law agent audio;
4. base64-encodes it into Twilio `media` events.

Both sides use 8 kHz mono μ-law, so no transcoder is required. A Deepgram
`UserStartedSpeaking` event sends Twilio `clear`, which drops queued outbound
agent audio for barge-in.

## Authentication

- The local MCP process is launched over stdio by the client; no public API
  endpoint is exposed for task creation.
- Each task requires an idempotency key; the local SQLite store fingerprints the
  task identity, destination and intent and replays exact retries safely.
- Twilio status callbacks validate `X-Twilio-Signature` against the exact public
  HTTPS URL and form fields.
- WebSocket handshakes validate the signature against the public HTTPS/WSS
  media URL before acceptance.
- The opaque Fredo call ID and matching Twilio SID must already exist before a
  media session starts.

## Call termination

The current call ends when:

- the callee/Twilio closes the stream, producing failure unless a structured
  outcome was already captured;
- Deepgram invokes `finish_demo`; Fredo waits for final agent audio, sends a
  Twilio `mark`, and hangs up after its playback acknowledgement or a bounded
  timeout;
- the 180-second duration task calls Twilio hangup;
- an operator interrupts the one-shot process.

No code requests Twilio recording. Live qualification must also confirm in the
Twilio console/API that no recording resource was created.

## Failure and status

Public results hide Twilio SID and show only a masked destination hint. Carrier
errors are normalized rather than returning raw Twilio exceptions. Transcripts
are held in local process memory for the current result and are not logged by
the bridge.

The task correlation and idempotency state is durable in the local SQLite store.
A process crash after Twilio accepts a call can still leave an unknown carrier
outcome. The safe response remains no automatic retry; an operator should
reconcile the carrier status before attempting any new task.

## Live qualification checklist

- Twilio France geographic permissions enabled;
- verified non-spoofed caller number;
- trial disclaimer understood/removed for judging;
- exact fixture allowlisted and consenting;
- tunnel URL stable for the call;
- signed callbacks accepted and forged ones rejected;
- French greeting intelligible;
- bidirectional facts and barge-in verified;
- hard hangup tested;
- no recording created;
- five of five controlled calls pass before the jury call.
