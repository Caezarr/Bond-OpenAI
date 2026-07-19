# Fredo call widget

This directory owns the Codex/ChatGPT phone surface. It intentionally contains
no telephony or provider code.

## Product behavior

- The widget is attached only to `bond.create_phone_task`.
- Native host approval remains the confirmation boundary. The widget never
  dials or confirms on its own.
- Once a confirmed call starts, the widget polls
  `bond.get_phone_task_status(call_id)` while the state is active.
- `Raccrocher` calls `bond.cancel_phone_task(call_id)`.
- Polling stops when the document is hidden or the call reaches a terminal
  state.
- The UI never schedules phases, connection, completion, or hangup. Those
  transitions come exclusively from the backend/provider.
- The timer remains at `00:00` while dialing, starts from the authoritative
  `connected_at`, and freezes only when the backend returns `ended_at` or a
  terminal state.
- Live listening is opt-in, listen-only, and available only during
  `in_progress`. The widget never requests microphone access.
- The component stores nothing. Its only direct network access is the
  user-initiated, short-lived audio stream from the configured audio origin.
- Full phone numbers, provider IDs, raw audio, stream credentials, and
  transcripts must never appear in model-visible MCP content. The audio stream
  reaches the widget directly and is never persisted.

The UI follows the Fredo “modern switchboard” visual system from
`docs/BRAND-DESIGN-BRIEF.md`. Its single signature element is the signal cable
from ready to completed.

## UI resource

Serve `phone-call.html` from the MCP server as:

```text
ui://fredo/phone-call-v2.html
```

The resource response must use:

```json
{
  "uri": "ui://fredo/phone-call-v2.html",
  "mimeType": "text/html;profile=mcp-app",
  "_meta": {
    "ui": {
      "csp": {
        "connectDomains": ["https://audio.example.com"],
        "resourceDomains": ["https://audio.example.com"]
      }
    }
  }
}
```

Replace `https://audio.example.com` with the single configured audio origin.
Do not allowlist the telephony provider or a wildcard domain; the widget talks
only to the Fredo audio relay.

## Tool descriptor metadata

Add this metadata to `bond.create_phone_task` only:

```json
{
  "annotations": {
    "readOnlyHint": false,
    "destructiveHint": false,
    "openWorldHint": true,
    "idempotentHint": true
  },
  "_meta": {
    "ui": {
      "resourceUri": "ui://fredo/phone-call-v2.html",
      "visibility": ["model", "app"]
    },
    "openai/outputTemplate": "ui://fredo/phone-call-v2.html",
    "openai/toolInvocation/invoking": "Preparing the call…",
    "openai/toolInvocation/invoked": "Phone ready"
  }
}
```

Do not attach the template to `bond.get_phone_task_status`; otherwise each
poll may create a fresh iframe instead of updating the existing phone.

## Structured content contract

Every create/status/cancel result should retain the existing task fields and
add the following safe display projection:

```json
{
  "call_id": "call_…",
  "task_id": "task_…",
  "status": "in_progress",
  "display": {
    "recipient_label": "Restaurant Le Select",
    "destination_masked": "+32 •••• ••42",
    "call_goal": "Reserve a table for four tonight at 21:00 under Gabriel.",
    "language": "fr",
    "max_duration_seconds": 180,
    "elapsed_seconds": 7,
    "connected_at": "2026-07-19T14:22:08.000Z",
    "ended_at": null,
    "server_now": "2026-07-19T14:22:15.000Z",
    "phase": "listening",
    "recorded": false,
    "live_listen_available": true
  },
  "outcome": null,
  "summary": null,
  "error": null
}
```

Required state values:

```text
needs_confirmation
dialing
in_progress
completed | no_answer | declined | failed | cancelled
```

Optional `display.phase` values:

```text
ringing | listening | speaking | wrapping_up
```

`status` and `display.phase` must reflect provider events, never a UI timeline.
The backend must not report `in_progress` until the remote party has actually
answered.

`connected_at`, `ended_at`, and `server_now` are ISO 8601 UTC timestamps.
`elapsed_seconds` is an authoritative fallback snapshot at the time of each
result. While `in_progress`, the widget interpolates between polls using
`connected_at` and `server_now`; it does not increment while `dialing` and has
no automatic completion timeout. When the provider supplies `ended_at`, the
final duration is derived from the two authoritative timestamps.

## Listen-only audio contract

Expose an app-only tool named `bond.open_phone_audio_stream`. The phone calls
it only after the user presses `Écouter`; do not attach an output template to
this tool. Its model-visible result stays intentionally minimal:

```json
{
  "structuredContent": {
    "call_id": "call_…",
    "status": "ready"
  },
  "_meta": {
    "audio_stream": {
      "url": "https://audio.example.com/live/one-time-token",
      "mime_type": "audio/mpeg",
      "expires_at": "2026-07-19T14:23:15.000Z"
    }
  }
}
```

`_meta.audio_stream` is widget-only and must never be copied into
`structuredContent`, logs, summaries, errors, or transcripts. The URL must be
HTTPS, bound to the authenticated user and `call_id`, short-lived, and safe to
close without a separate stop request.

The relay may mix both call legs in memory, but must not write audio to disk or
object storage. It should expose a browser-decodable continuous stream. Closing
the media connection, hiding/closing the widget, pressing `Couper l’écoute`,
or reaching any terminal call state stops delivery immediately. No microphone
permission, upstream media track, recording API, replay, or download endpoint
is part of this feature.

## MCP resource support

The raw stdio server must advertise and implement:

```text
resources/list
resources/read
```

`resources/read` returns the literal HTML file in `contents[0].text`. Advertise
the resource capability during `initialize` and keep the URI versioned when a
breaking widget change ships.

## Local preview

Open `phone-call.html` directly in a browser. Without the Apps SDK bridge it
renders an explicitly labelled, non-interactive preview and never attempts a
tool call.
