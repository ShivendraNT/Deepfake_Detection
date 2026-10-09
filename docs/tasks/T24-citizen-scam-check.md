# T24 — Citizen "Scam Check" page (stretch S1)

> Build ONLY if the MVP is done by the end of Day 3.

## Goal
A mobile web page in Hindi/English: paste a message → band + action only, "impossible claim"
rules, 1930 tap-to-call, NCRP and Chakshu links, and a WhatsApp trusted-contact share. No scores,
no forensic dashboard.

## Owner
Saksham. Effort ≈ 4 h.

## Depends on
T05 (ask extractor), T14 (text style).

## Files to create or modify
- `src/satyapan/citizen/rules.py` — extend `IMPOSSIBLE_CLAIMS`; implement `scam_check`
- `console/public/scam-check.html` (new) — single static page calling `POST /api/scam-check`

## Do not touch
API route (already wired), contracts (`CitizenResult` is fixed), tests.

## Interfaces
`scam_check(text, lang) -> CitizenResult(band, action_text, rule_hits, links)`;
`links` = `{"call_1930": "tel:1930", "ncrp": ..., "chakshu": ..., "share": "https://wa.me/?text=..."}`.

## Plan (steps)
1. `scam_check` per docstring; 5 parametrised tests.
2. Add rules: courier/customs parcel, KYC expiry, electricity disconnection, "refund" with OTP.
3. Static page: big buttons, Hindi toggle, `SpeechSynthesis` reads the action aloud (hi-IN).
4. Rate limit note: 20 checks/day per device in production (not needed for the demo).

## Acceptance criteria
`make task T=T24`: bands, no "score" anywhere in output, links, Hindi action text, API 200.

## Test command
`make task T=T24`

## Definition of Done
Green + `make check`; works on a phone browser (screenshot in PR).

## Common mistakes
- Returning detector details (oracle). - Telling users something is "safe".
- Claiming the page can protect live phone calls (it cannot).

## Hints and links
- `tel:` and `wa.me` links: https://faq.whatsapp.com/5913398998672934

## Agent plan (write yours here)

1. `src/satyapan/citizen/rules.py`: add 4 rules to `IMPOSSIBLE_CLAIMS` (courier/customs parcel
   fee, KYC expiry, electricity disconnection, "refund" needing OTP), each with EN + Devanagari
   HI text and a stable snake_case `rule_id`.
2. Implement `scam_check`: `hits` = rules whose regex matches with `re.I | re.S`;
   `spans` = `extract_asks(text)`; any hit or `A2`/`A3` → `HOLD`; any of `A1`/`A4`..`A7` →
   `VERIFY`; else `PASS`.
3. `action_text` per band, EN + HI: HOLD / VERIFY / PASS wording from the docstring plus a
   Devanagari equivalent (no reassuring words, never "safe").
4. `links` = `LINKS` + `share` = `https://wa.me/?text=` + `urllib.parse.quote(<short warning>)`
   built from `action_text`; no "score" anywhere in the payload.
5. Run the task tests (`uv run pytest --task T24 -v`; `make` is not installed on this Windows
   box) — all 8 must go green.
6. `console/public/scam-check.html` (new): textarea + big Check button, band badge (colour +
   word), action text, tap-to-call `tel:1930`, NCRP + Chakshu links, WhatsApp share button,
   EN/HI toggle, `SpeechSynthesis` reads the action aloud (`hi-IN`); posts to `/api/scam-check`.
7. Full gate: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
   `uv run pytest` (the `make check` equivalents).
8. `docs/STATUS.md` → `in-progress` now, `done` + one-line note when green; commit
   `T24: …`.
