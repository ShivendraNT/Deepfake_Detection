# T10 — Extension side panel UI (built from a recorded event stream)

## Goal
The side panel the maker sees during a call: voice meter, transcript lines, ask chips, suggested
line card, "Confirm with…" (OOB) and "Link to payment" buttons, and a visible "Protection on"
indicator. Built and tested from `extension/replay/sample_events.jsonl` — no live call needed.

## Owner
B1. Effort ≈ 1 day.

## Depends on
T07 only for the event contract (already fixed in `schemas/LiveEvent.schema.json`).

## Files to create or modify
- `extension/lib/panel_state.js` — pure reducer `initialState`, `applyEvent`, `ASK_LABELS`
- `extension/sidepanel.html` — real markup with the required ids (remove `STUB(T10)`)
- `extension/sidepanel.js` — render state; `?replay=1` dev mode
- `extension/sidepanel.css` — styles

## Do not touch
`extension/tests/panel_state.test.mjs` (acceptance), `extension/lib/voice_rules.js`,
`extension/replay/sample_events.jsonl`, capture code (T07), backend.

## Interfaces
Events (see `schemas/LiveEvent.schema.json`):
`voice {window_index, label}`, `transcript {chunk_index, text}`, `ask {ask_type, reason_code, span_text}`,
`band {band, reason_codes, suggested_line}`, `status {message}`.
Required element ids: `voice-meter`, `transcript`, `ask-chips`, `suggested-line`, `btn-confirm`,
`btn-link-payment`, `protection-indicator`.
State shape: see the comment block at the top of `lib/panel_state.js`.

## Plan (steps)
1. Implement `initialState` + `applyEvent` (return NEW objects; never store scores).
2. `make ext-test` until `panel_state.test.mjs` passes. Remove the `STUB(T10)` line.
3. HTML with the 7 ids; CSS: band banner with text (PASS/VERIFY/HOLD), chips, meter.
4. `sidepanel.js`: replay mode fetches `replay/sample_events.jsonl` and applies one event every
   300 ms; live mode listens to `chrome.runtime.onMessage` + `subscribe()` from `lib/api.js`.
5. Buttons: `btn-confirm` → choose requester from `/employees` → `POST /cases/{id}/oob`;
   `btn-link-payment` → prompt for a case id (simple) and store it.
6. Load unpacked in Chrome (`chrome://extensions` → Developer mode → Load unpacked → `extension/`),
   open the side panel with `?replay=1` to check visually.

## Acceptance criteria
- Node reducer tests pass (replay ends in HOLD, chips A1, A4, A5, no scores, no mutation).
- `sidepanel.html` contains all 7 ids. `make task T=T10` green.

## Test command
`make ext-test` and `make task T=T10`

## Definition of Done
Both green; screenshot in PR; `make check` green.

## Common mistakes
- Mutating state in the reducer (`state.asks.push`) — the test checks the old state.
- Showing numbers like "0.97" to the maker. Show words: "Likely synthetic voice (2 windows)".
- Colour-only signals; tiny fonts. The maker is mid-call — big, short text.

## Hints and links
- Side panel API: https://developer.chrome.com/docs/extensions/reference/api/sidePanel
- Node test runner: https://nodejs.org/api/test.html

## Agent plan (write yours here)
1. Implement pure reducer `initialState`, `applyEvent`, and `ASK_LABELS` in `extension/lib/panel_state.js` without mutations.
2. Remove `STUB(T10)` from `extension/lib/panel_state.js` and verify node tests pass.
3. Build `extension/sidepanel.html` with all required element IDs (`voice-meter`, `transcript`, `ask-chips`, `suggested-line`, `btn-confirm`, `btn-link-payment`, `protection-indicator`).
4. Style `extension/sidepanel.css` with clean layout, band banner, chips, and meter.
5. Implement `extension/sidepanel.js` with DOM rendering and dev replay mode (`?replay=1`).
6. Run `make ext-test` and `make task T=T10` until green.
7. Run `make check` and update `docs/STATUS.md`.
