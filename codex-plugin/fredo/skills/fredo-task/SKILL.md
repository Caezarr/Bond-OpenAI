---
name: fredo-task
description: Handle a whole spoken task end to end - resolve the number, place the call, run the conversation, and hand any structured result to another MCP (e.g. calendar).
---

# Fredo end-to-end task orchestration

Use this when the user gives a full task ("call the restaurant and book a table
for four tonight, then put it in my calendar") and expects the whole thing
handled without step-by-step confirmation.

This skill orchestrates existing tools; it does not add new call logic. The
local Bond-OpenAI MCP places and controls the call. A separate calendar MCP (if
present) receives the structured result.

## Prerequisites

Full-auto runs unattended, so it is opt-in in the local `.env`:

```bash
FREDO_ALLOW_UNLISTED_DESTINATIONS=1
FREDO_AUTOCONFIRM=1
```

When these are off, the MCP still returns a confirmation preview and requires a
pre-enrolled destination. Never put credentials in a task or prompt.

## Non-negotiable safety (always enforced, even full-auto)

- Destinations must be valid E.164.
- Emergency, premium/surtaxe, short-code and anonymous numbers are always
  rejected by the MCP. Do not try to work around this.
- One active call, hard duration cap, synthetic-voice and no-recording
  disclosure, no recording, idempotency. These cannot be disabled.

## Flow

1. `bond.classify_task` with the task text and any context.
2. If the destination number is missing, resolve it with `/browse`:
   - navigate to a maps/search result for the named entity;
   - extract a phone number from structured data first (`data --jsonld`,
     `data --og`), then `links` (`tel:` hrefs), then visible `text`;
   - verify the result actually matches the intended entity (name + city);
     if you cannot verify it, ask the user rather than dialing a guess.
3. Normalize the number to E.164. Build `task_input` including provenance:

```json
{
  "task_id": "reserve-2026-07-19",
  "caller_identity": "Gab",
  "destination_phone": "+33XXXXXXXXX",
  "call_goal": "Reserve a table for four at 9 PM tonight under Gab",
  "language": "fr",
  "destination_source": {
    "method": "browse",
    "url": "https://maps.example/...",
    "query": "restaurant name city",
    "confidence": "high"
  }
}
```

4. `bond.create_phone_task` with `task_input` and a stable `idempotency_key`.
   In full-auto the call starts immediately; otherwise confirm the preview.
5. Poll `bond.get_phone_task_status` until a terminal state. Treat the
   structured terminal state as authoritative, not the phone surface.
6. On `completed`, read `summary`, `answer`, `details` and `next_actions`.
   If `next_actions` contains a `calendar.create_event`, actually create it using
   whatever calendar/scheduling tool is available in this session (e.g. a Google
   Calendar / Pipedream create-event tool). Map the payload fields directly:
   `event.title` -> summary/title, `event.start`/`event.end` -> start/end datetime
   (already ISO 8601 with timezone), `event.location`, `event.notes`. The phone MCP
   never writes to the calendar itself; you own that step.
   Only if there is genuinely no calendar tool available at all, present the event
   details plainly so the user can add it manually. Do not say the calendar is "not
   connected" unless you actually checked and found no calendar tool.
7. Report a clear final summary: what was asked, what the person answered, the
   concrete result, and whether the calendar event was created (or the exact event
   details if it could not be created).

## Result shape

`bond.get_phone_task_status` returns, among other fields:

```json
{
  "status": "completed",
  "summary": "Reserved a table for four at 9 PM under Gab.",
  "answer": "Confirmed for four at nine",
  "details": {"datetime_iso": "2026-07-19T21:00:00+02:00", "party_size": 4, "status": "confirmed"},
  "next_actions": [
    {"type": "calendar.create_event", "event": {"title": "...", "start": "2026-07-19T21:00:00+02:00", "end": "2026-07-19T22:00:00+02:00"}}
  ]
}
```

## Hard rules

- `/browse` resolution is best-effort and non-deterministic. Verify the entity
  before dialing; when unsure, ask.
- Never dial an emergency, premium or bulk destination; the MCP blocks them and
  you must not attempt to bypass it.
- A carrier request accepted is not a completed task; require a terminal result.
- Only forward `next_actions` produced by the MCP; do not fabricate calendar
  events from an uncertain outcome.
