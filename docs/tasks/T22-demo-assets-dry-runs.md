# T22 — Demo assets + 10 logged end-to-end dry runs

## Goal
Everything the 2:45 demo needs, rehearsed until it works 10 times in a row: signed consent forms,
pre-generated clone clips (local only), fixture emails/invoices, the offline "demo call" tab, and a
dry-run log.

## Owner
L + all. Effort ≈ 1 day across the team.

## Depends on
T07-T17 (the demo path).

## Files to create or modify
- `extension/demo_call.html` — offline call tab (remove `STUB(T22)`): pick local clips, play them
- `docs/consent/VOICE_CLONE_CONSENT_TEMPLATE.md` — print and sign (signed copies NOT in git)
- `results/dry_runs.csv` (new) — `run,date,moment1_voice_alert,oob_hold,moment2_floor_verify,pack_utr_first,ask_chip_latency_s,notes`
- `scripts/dry_run_check.py` (new, optional) — API checks for moments 1-3 against fixtures

## Do not touch
Policy, contracts, fixtures (unless via `scripts/make_demo_data.py` with leader review).

## Interfaces
Demo storyline and fixtures: `docs/DEMO_SCRIPT.md` (`case_s06`, `case_s07`, `case_s12`).

## Plan (steps)
1. Consent forms signed by every teammate whose voice is used.
2. Generate clone clips on Colab (F5-TTS / XTTS-v2) from consenting voices only; keep local.
3. Pre-test 10 clips through ACTUAL Meet capture; keep the ones the detector catches; note the rate.
4. Build `demo_call.html` (file picker + `<audio>`; no files bundled).
5. Run the full script 10 times (Meet, then the offline tab once); log every run in the CSV.
6. Record a full backup screen recording.

## Acceptance criteria
`make task T=T22`: ≥ 10 rows, all four checks "yes"; demo tab implemented; consent template present.

## Test command
`make task T=T22`

## Definition of Done
Green + `make check`; recording link in `docs/pitch/backup_recording.md` (T23).

## Common mistakes
- Committing clips or signed forms. - Never testing through real Meet (codecs change everything).
- Rehearsing only the happy path — rehearse the fallbacks too.

## Hints and links
- F5-TTS: https://github.com/SWivid/F5-TTS · XTTS-v2 (Coqui) — check licenses for demo use.

## Agent plan (write yours here)
