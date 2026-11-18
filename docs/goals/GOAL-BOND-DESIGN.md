# GOAL — Fredo × Bond design and communication (design)

Version: `0.1-brussels`
Status: ready to execute

## Outcome

Produce a coherent website and slide deck that make the product immediately
understandable in the OpenAI hackathon room in Brussels:

> Bond finds the work. Fredo makes the call. Codex makes it happen.

This goal creates no MCP, telephony code or deployment. It is purely the visual
and narrative layer for the software goal in `GOAL-BOND-MCP.md`.

## Audience

- OpenAI hackathon jury seeing the product for the first time.
- Founders and operators who have unfinished tasks requiring a call.
- Engineers who need to understand the Bond/Codex/Fredo boundary in seconds.

## Core message hierarchy

1. **Problem:** AI can draft the message; some work still requires a voice.
2. **Product:** Fredo turns one Codex prompt into a safe, real phone call.
3. **Connection:** Bond identifies the task; Fredo executes it; the result
   closes the original task.
4. **Proof:** verified caller, human confirmation, no recording, factual result.
5. **Honesty:** current profile uses Twilio PSTN and provider-backed Deepgram voice.

## Visual direction — “the modern switchboard”

Use the tactile language of a telephone switchboard rebuilt as software:
signal wires, call lights, operator labels and a clear status sheet. It should
feel precise and alive, not like a generic AI SaaS template.

### Palette

| Token | Hex | Role |
| --- | --- | --- |
| Ink | `#151817` | text and dark panels |
| Paper | `#F5F0E6` | primary background |
| Signal | `#FF654A` | active call and main CTA |
| Cobalt | `#4267E8` | Bond/Codex connection and links |
| Relay | `#BEE8CF` | completed/safe state |
| Wire | `#A7A79D` | rules and inactive state |

### Typography

- Display: **Bricolage Grotesque**, 600–700.
- Body: **Instrument Sans**, 400–600.
- Utility/data: **IBM Plex Mono**, 400–500.

Use sentence case, short declarative headlines and mono for phone numbers,
timestamps and state labels.

### Signature visual

One continuous orange-red cable line connects:

```text
prompt → confirmation → phone → summary
```

Use it in the hero, the deck timeline and the demo UI progress indicator. This
is the only major decorative motif.

## Website deliverables

### Hero

Eyebrow: `A phone call, from one prompt.`

Headline: `The work does not stop at the screen.`

Body: `Fredo gives Codex a verified, consented voice. Ask it to call someone,
handle the conversation, and bring back the answer.`

CTAs: `Watch the call happen` and `See the Bond workflow`.

The hero animation must show a real task card, a confirmation state, a ringing
phone and a completed summary. Do not lead with a dashboard screenshot.

### Website sections

1. The gap: text automation stops where a person must answer.
2. One prompt: restaurant reservation example.
3. The call sheet: identity, masked number, purpose, language, consent.
4. The live call: synthetic-voice and no-recording disclosure.
5. The result: factual summary and completed task.
6. Bond × Fredo × Codex: find, understand, execute.
7. Guardrails: verified caller, allowlist, confirmation, 180-second cap.
8. Demo CTA: `Give Fredo a task that needs a voice.`

## Slide deck deliverables (8 slides)

1. `What if Codex could make the call?`
2. `AI can write the message. The last mile is human.`
3. One prompt with extracted fields.
4. Bond task → Codex intent → Fredo call → completed task.
5. Stack: Bond/Codex, Fredo, Twilio, Deepgram; label `provider-backed-voice`.
6. Safety: consent, E.164, allowlist, verified caller, no recording.
7. Before/after Bond task: `Needs you` → `Completed` with summary.
8. Live demo: two clicks and the phone rings.

## Demo UI components

- Task card with `phone_call` badge and consent state.
- Call preview with caller identity, masked number, goal, language, recording
  status, verified caller ID and duration cap.
- Live status strip: `Ready`, `Dialing`, `Connected`, `Listening`, `Speaking`,
  `Wrapping up`, `Completed`.
- Result card with outcome, summary, duration and next action.

Never show raw transcripts by default. Use public redacted numbers in all
screenshots and deck exports.

## Motion rules

- Draw the cable once on page load; no infinite ambient animation.
- Pulse the active call light at a human rhythm.
- Use the waveform only when audio is actually active.
- End with a short line-lock animation and the result card.
- Respect reduced-motion preferences.
- Never autoplay a fake phone conversation.

## Design acceptance gates

- A jury member understands the product in under 10 seconds.
- The Bond/Codex/Fredo division is visible on the first slide and hero.
- The live demo path is readable without technical narration.
- The current provider-backed voice boundary is stated accurately.
- Website and deck share the same tokens, cable motif and task language.
- Public assets contain no credential, full phone number, transcript or fake
  success evidence.
- Desktop, laptop, mobile, keyboard focus and reduced-motion variants exist.

## Not part of this goal

- MCP implementation or Bond API integration.
- Twilio/Deepgram configuration.
- Hosted deployment or marketplace publication.
- Production claims or unverified performance metrics.

## Definition of done

The website and slide deck are export-ready, use the same design tokens and
copy, show the two-click flow, explain the real technical boundary honestly,
and can be handed to a designer without additional product interpretation.
