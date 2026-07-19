# Fredo — brand, website and slide-deck brief

Version: `0.1-brussels`
Audience: OpenAI hackathon jury in Brussels, founders, product/engineering teams

## 1. The product in one sentence

Fredo turns one natural-language Codex request into one safe, consented phone
call and a factual result.

## 2. The problem

AI tools can draft emails, create tickets and summarize meetings. They still
stop at the edge of the real world: a restaurant, supplier, candidate or human
contact often requires a phone conversation.

Bond identifies the work that needs doing. Codex understands the request.
Fredo is the execution layer that can actually speak to someone.

## 3. The product story

### Short version

> Bond finds the work. Fredo makes the call. Codex makes it happen.

### Jury version

The user writes one prompt. The local MCP prepares the verified Fredo capability. Fredo
checks the destination, consent and intent, asks for missing details, shows a
human confirmation, then places a real call from a verified Twilio number.
Deepgram handles live speech recognition, dialogue and synthetic speech. Fredo
returns the answer and closes the loop in the same Codex task.

### Bond extension

Bond already turns commitments from Slack, Gmail, calendars and documents into
ranked work. A `phone_call` task is the natural next action: Bond detects it,
Fredo executes it, and Bond marks it complete with the outcome.

## 4. Be honest about the current MVP

The active profile is `provider-backed-voice`, not all-local inference:

```text
Codex prompt
  -> local MCP task validation
  -> Fredo policy + native confirmation
  -> Twilio verified caller ID and PSTN
  -> Cloudflare quick tunnel
  -> Deepgram hosted STT, dialogue and TTS
  -> consenting phone
  -> structured answer in Codex
```

The user never receives or enters the team Twilio/Deepgram credentials in the
judge flow. The call is not recorded. The phone number and intent stay out of
the MCP task payload.

Do not claim: fully local voice inference, production-grade global telephony,
voice cloning, unattended bulk calls, or a public Bond API integration before
those are independently qualified.

## 5. Brand personality

- Warm, direct and slightly mischievous; the name Fredo should feel human.
- Operational rather than futuristic: show the call being completed, not an
  abstract AI brain.
- Calm at the dangerous moments: consent, confirmation, caller identity and
  no recording are visible and precise.
- Technical details are evidence, not the hero. Lead with the phone ringing.

Avoid the generic “AI assistant” look: no glowing brains, robot faces, stock
call-center photography, purple gradients or unreadable terminal walls.

## 6. Visual direction: “the modern switchboard”

The visual world is a tactile telephone switchboard redesigned for a software
product: hard signal lines, small operator labels, a single bright call light,
and a generous field of quiet space.

### Palette

| Token | Hex | Use |
| --- | --- | --- |
| `ink` | `#151817` | primary text, dark panels, call-state backdrop |
| `paper` | `#F5F0E6` | main background, printed call-sheet feel |
| `signal` | `#FF654A` | live call, primary CTA, alert light |
| `cobalt` | `#4267E8` | Bond/Codex connection, links, secondary actions |
| `relay` | `#BEE8CF` | completed/safe state, confirmation surfaces |
| `wire` | `#A7A79D` | rules, inactive waveform, metadata |

The signature color is `signal` orange-red. Use it sparingly: a single active
call light should be the first thing the eye finds.

### Typography

- Display: **Bricolage Grotesque**, variable, 600–700. Use for the hero and
  slide titles; its irregular rhythm gives Fredo a distinct voice.
- Body: **Instrument Sans**, 400–600. Use for explanations and UI labels.
- Utility/data: **IBM Plex Mono**, 400–500. Use for phone numbers, timestamps,
  state labels, IDs and technical evidence.

Type should be large, short and declarative. Use sentence case. Never use a
wall of uppercase marketing copy.

### Shape and spacing

- 2px dark rules and thin “telephone wire” connectors.
- 4px radius on functional cards; no pill-shaped everything.
- 8px radius only for the primary CTA and status chips.
- 8px base spacing unit; wide 64–96px section rhythm.
- Prefer asymmetric two-column layouts over centered SaaS cards.

### Signature element

One continuous orange-red cable line travels through the product story:

```text
prompt  ────────●────────  confirmation  ────────●────────  phone  ────────●────────  summary
```

On the website it becomes the hero diagram. On slides it becomes the bottom
timeline. In the UI it becomes the call progress indicator. It is the one
visual motif people should remember.

## 7. Website brief

### Hero

Eyebrow: `A phone call, from one prompt.`

Headline:

> The work does not stop at the screen.

Supporting copy:

> Fredo gives Codex a verified, consented voice. Ask it to call someone,
> handle the conversation, and bring back the answer.

Primary CTA: `Watch the call happen`

Secondary CTA: `See the Bond workflow`

Hero interaction: a task card enters on the left, the cable line lights up,
the phone card rings, then the summary card resolves on the right. Do not use a
generic dashboard screenshot as the first visual.

### Section order

1. **The gap** — “AI can write the message. Some work still needs a voice.”
2. **One prompt** — show the exact restaurant reservation request.
3. **The call sheet** — destination, consent, purpose, language and caller ID.
4. **The live call** — synthetic voice disclosure, interruption, no recording.
5. **The result** — factual summary and task completion.
6. **Bond × Fredo × Codex** — Bond finds the task, Codex orchestrates, Fredo
   executes.
7. **Built with guardrails** — verified caller, allowlist, 180-second cap,
   idempotency, no recording.
8. **Demo CTA** — “Give Fredo a task that needs a phone.”

### Website copy snippets

- `From “someone should call them” to “it’s handled.”`
- `No spoofing. No mystery caller. No recording.`
- `A real conversation, returned as a structured result.`
- `The phone is an interface too.`

### Website proof block

Use three compact evidence cards, not inflated metrics:

```text
01  Verified caller identity
02  Human confirmation before dialing
03  Factual result returned to the task
```

## 8. Slide deck: 8-slide structure

### Slide 1 — The hook

Large title: `What if Codex could make the call?`

Show a dark field, one lit orange-red call indicator and the destination
hidden as `+33 6 •••• ••••`.

### Slide 2 — The unfinished task

Show a Bond-style list item: `Reserve dinner for four — waiting on a call`.
Message: `AI handles text. The last mile is human.`

### Slide 3 — The one-prompt experience

Show the exact user prompt, then highlight extracted fields: person, number,
purpose, language, consent.

### Slide 4 — The product loop

Use the continuous cable line:

```text
Bond task → Codex intent → Fredo confirmation → phone call → task complete
```

### Slide 5 — The stack

Show only the necessary layers:

```text
Bond / Codex
MCP verification
Fredo policy and runtime
Twilio PSTN
Deepgram voice agent
```

Label the current release clearly: `provider-backed-voice`.

### Slide 6 — The guardrails

Use a “call sheet” visual with five checks: consent, E.164, allowlist, verified
caller, no recording. Make this slide reassuring, not legalistic.

### Slide 7 — The Bond connection

Before: `Needs you — call the restaurant`.

After: `Completed — 4 seats confirmed at 21:00 under Gab`.

Message: `Bond finds the work. Fredo closes the loop.`

### Slide 8 — The live demo / ask

Title: `Give Fredo a task that needs a voice.`

Show the two clicks and the phone ringing. End with the repository and MCP
app link, not a feature list.

## 9. UI components for the demo

### Task card

Fields: title, source (`Bond`), priority, extracted phone task badge,
consent badge, missing-field state, last update.

### Call preview

Fields: caller identity, masked destination, purpose, language, recording
status, max duration, verified caller ID, buttons `Back` and `Call with Fredo`.

### Live status strip

States: `Ready`, `Dialing`, `Connected`, `Listening`, `Speaking`, `Wrapping up`,
`Completed`.

### Result card

Show outcome, factual summary, duration, answered-by label and next action.
Never show a raw transcript by default.

## 10. Motion and sound

- On load, the cable line draws once from prompt to phone; no infinite ambient
  animation.
- The active call indicator pulses at a human rhythm, not a loading spinner.
- Waveform amplitude reflects actual audio only during a live call.
- Completion is a short line-lock animation followed by the result card.
- Respect `prefers-reduced-motion`.
- Do not autoplay a fake phone conversation on the website; use captions and a
  user-triggered demo.

## 11. Design handoff checklist

- Figma page: `00 Foundations`, `01 Website`, `02 Deck`, `03 Demo UI`.
- Define desktop 1440px, laptop 1280px and mobile 390px frames.
- Export the cable/waveform as SVG; keep all text live.
- Use real prompt copy and redacted phone numbers in public assets.
- Include light, dark and high-contrast states for `Ready`, `In progress`,
  `Completed`, `Needs input` and `Failed`.
- Provide keyboard focus, screen-reader labels and a reduced-motion variant.
- Keep the active call color distinct from error red; `signal` is action, not
  failure.

## 12. Final positioning

Fredo is not another chat interface and not a robo-dialer. It is a guarded
execution layer for the work that still requires a human conversation.

> The last mile of automation is a voice.
