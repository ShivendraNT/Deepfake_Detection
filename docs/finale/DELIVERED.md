# Delivered vs the Round-1 plan

> Honest delivery table for the finale. “Done” means the code exists, is wired into the demo,
> and has a check you can run. “Partial” means the core works but a named piece is missing or
> untested on the stage laptop. “Cut” means we chose not to build it, with the reason.

The rubric rows this supports:

| Rubric row | Evidence |
|---|---|
| 1. Working prototype | `docs/finale/LIVE_DEMO.md`, `make dry-run`, `make judge` |
| 2. Spot-check + measured accuracy | `docs/JUDGE_KIT.md`, `results/EVIDENCE_LEDGER.md` |
| 3. Own engineering | `docs/ENGINEERING_DEEP_DIVE.md` |
| 4. Alert + response + safeguards | `docs/finale/SAFEGUARDS.md`, `make dry-run` |
| 5. Delivery against the plan | this file |

---

## 1. F-card delivery

| Card | Plan priority | Status | Evidence / what is actually true |
|---|---|---|---|
| **F01** Contracts freeze + mock + stage | P0 | **done** | `desktop/shared/contracts.ts`, Python models, `shared/mockScenario.ts`, `?view=stage`; typecheck green |
| **F02** Window manager (mascot/bubble/Notebook/capture, tray, hotkeys) | P0 | **done** | `desktop/main/`; click-through, drag/snap, bubble placement, tray, hotkeys; 84 vitest tests green. The “Check it properly” dead-button bug is fixed (commit `1a79267`). |
| **F03** Backend glue (calls, files, OOB, events, reports) | P0 | **done** | `src/satyapan/api/companion/`; `tests/finale/test_companion_finale.py`; real SSE bus; report pack |
| **F04** X1 cross-channel signal | P1 | **done** | `pipeline.derive_cross_channel_signals`; `tests/finale/test_x1.py`; raise-only, 30-min window, idempotent |
| **F05** Integration, demo, dry runs, backup | P0 | **partial** | Automated end-to-end rehearsal **3/3 green** (`docs/finale/DRY_RUNS.md`, ~100 ms/run); 12 demo scenarios 12/12 expected bands; human on-stage dry runs and the backup recording are still **pending** (they need the stage laptop, Meet and a phone) |
| **F06** Mascot component + gallery | P0 | **done** | `desktop/renderer/src/satya/`, `?view=gallery`; 10 poses, breathe/sway; F06 test coverage |
| **F07** Mascot window + radial menu + brain reducer | P0 | **done** | `satyaMachine.ts`, radial menu, drag; 38 reducer tests |
| **F08** Bubble cards + trilingual copy | P0 | **done** | 10 card kinds in `companion/bubble/cards/`, `copy.ts` EN/Hinglish/हिन्दी; 8 bubble tests |
| **F09** Deck + story | P0 | **partial** | Story, 3-minute script, fallbacks and Q&A crib are in `docs/finale/PLAN.md` §7/§9 and `LIVE_DEMO.md`; six slides of exact finale copy (with the measured numbers) are in `docs/finale/SLIDES.md`; the Round-1 deck exists at `Satyapan_Pitch_Deck.pptx`; the deck file itself needs the slides pasted in |
| **F10** Capture window (loopback, VAD, ONNX, WAV) | P0/P1 | **done** | `desktop/renderer/src/capture/`, `desktop/main/capture.ts`; 9 vitest tests; replay path works; system-audio loopback is macOS-permission-dependent |
| **F11** Report pack v2 (5 sections) | P0 | **done** | `src/satyapan/report/`; 12/12 tests; `MANUAL_ONLY`, UTR first |
| **F12** Demo media (synthetic clips, replay, email) | P0 | **done** | `data/demo/finale/generate_media.py`, `manifest.json`, 4 tests; fake voices only |
| **F13** Gmail “Ask Satya” button | P2 | **cut** | Deferred after CP3: the Chrome extension already captures Meet/Teams tabs, and the Gmail button adds no value to the 3-minute demo. The drop-a-file path covers “hand Satya an email”. |
| **F14** Notebook shell + tabs | P0 | **done** | `workspace/Workspace.tsx`, 7 tabs, 5 workspace tests; 1120×720 |
| **F15** Reports tab: Scribe + Report Copilot | P0 | **done** | `workspace/tabs/ReportsTab.tsx` is fully wired: golden-hour timer, typed Scribe over the backend text, 5 sections, copy/open, `MANUAL_ONLY` banner, case picker. It compiles and typechecks; add one UI test before the stage run if time allows. |
| **F16** Approver phone page + QR | P0 | **done** | `console/public/oob.html`; live QR in Settings; phone tests; `not_requested` third button. A regression test now fetches the served page at `/oob` and drives its real `/api/oob/*` endpoints end to end. |

---

## 2. P0 / P1 / P2 scope

### P0 — the demo path (all built)

| P0 item | Status |
|---|---|
| mascot-only window, radial menu, drag, three modes | done |
| consent card + scopes | done |
| call via Chrome extension (route A) + replay (route C) | done; route A rehearsed in the browser, replay is the deterministic fallback |
| live chips + alert card | done |
| OOB from the alert, approver on a phone | done; `not_requested` path tested |
| drag-drop a file → result card | done |
| Scribe animation + Report Copilot (5 sections) | done |
| Notebook: Now, Cases, Timeline, Evidence, Reports, Privacy | done (Settings also present) |

### P1 — built, with one honest gap

| P1 item | Status |
|---|---|
| system-audio loopback (route B) | built but **platform/permission-dependent** (macOS Screen & System Audio Recording; when launched from Terminal the terminal app needs the permission). The stage plan is route A + replay fallback. |
| X1 cross-channel signal | done, tests green |
| Hinglish / हिन्दी copy toggle | done |
| Settings tab | done |
| “Keep as evidence” for call audio | **partial**: the vault and privacy copy exist, and dropped files are preserved; there is no explicit “Keep this call as evidence” button in the demo path. Not on the critical path for the 3-minute story. |

### P2 — deliberately not built

| P2 item | Status / reason |
|---|---|
| Gmail “Ask Satya” button | cut; see F13 |
| screenshot OCR drop | the Screen Guard already scans the screen and the clipboard; a separate drop target adds UI, not detection |
| Windows build | packaging targets exist (`npm run dist:win`, `scripts/satya.py`), but **not tested on real Windows hardware** in this window. The Python path is pure-Python and OS-agnostic; the OS-specific parts are capture and OCR, with documented fallbacks (`README.md`). Do not claim “tested on Windows” on stage. |

---

## 3. What is real vs mocked (say this out loud)

| Real, live | Mocked / fallback / not claimed |
|---|---|
| system-audio capture of the call (or Chrome tab capture) | the **speech engine** in the automated dry run is a `FakeTranscriber`; on stage it is local Whisper (`make asr`) |
| on-device Whisper transcription, utterance cutting | the **caller** on laptop B is a teammate; the consented clone is optional and labelled |
| ask + cue detection, context filter, policy band | the **approver phone** can be a real phone on the hotspot or the localhost fallback; both use the same token |
| OOB question, single-use token, “not me” → HOLD | the **backup recording** is not made yet |
| report pack drafts, UTR-first, `MANUAL_ONLY` | the **video deepfake** check is raise-only and depends on model files; if absent it abstains |
| Screen Guard OCR, clipboard check, file/email/invoice checks | the **Windows/Linux** packaging is untested on real hardware |
| audit trail, Privacy tab, delete session | — |

---

## 4. Cuts and why (the one-slide version)

1. **Gmail button (P2)** — the demo is about the *moment of decision*, not another inbox. The
   extension already captures Meet tabs; the drop-a-file path already covers “hand Satya an
   email”. Cutting it protected the P0 integration time.
2. **Route B as the primary call route** — loopback is real but the macOS permission is a
   stage risk. We kept it as a P1 option and made route A + replay the reliable path. The
   fallback is labelled **DEMO REPLAY — NOT LIVE CAPTURE**.
3. **“Keep call audio as evidence” UI** — the vault supports it; the 3-minute story does not need
   it, and a half-wired button is worse than an honest “audio stays in memory”.
4. **Fresh finale deck (F09)** — the story, script, fallbacks and Q&A are written and rehearsed in
   `LIVE_DEMO.md`; the deck is the remaining artifact. The judges score the working prototype and
   the measured numbers, which are ready.
5. **Human dry runs / backup recording (F05)** — cannot be completed without the stage laptop,
   Meet, a phone and the venue. The automated rehearsal is 3/3 green; the human table is in
   `DRY_RUNS.md` waiting to be filled.

---

## 5. Verify the delivery in five minutes

```bash
# the whole story in-process: consent -> live call -> alert -> OOB "not me" -> report -> stop
make dry-run

# the measured scoreboard + a judge's own input or labelled kit
make judge
uv run python scripts/judge_kit.py --file data/demo/emails/02_bec_bank_change_narmada.eml
uv run python scripts/judge_kit.py --labels my_kit.jsonl

# every surface: Python + desktop + OOB console + extension
make ci

# the safety invariants
uv run pytest tests/invariants -q

# the desktop
cd desktop && npm run typecheck && npx vitest run
```

Expected: dry run 3/3 PASS, scoreboard below a second, email check → VERIFY (floor PASS, asks
raise), labelled kit prints exact/unsafe/false-alarm rates with a confusion matrix, all surfaces
green, invariants green, desktop 84/84.

---

## 6. Remaining risks before the stage

| Risk | Mitigation |
|---|---|
| macOS permission popup | grant Screen & System Audio Recording the night before; replay fallback |
| venue Wi-Fi isolates the phone | phone hotspot; localhost fallback for the approver page |
| live ASR is slow | `SATYAPAN_ASR_MODEL=base`; replay fallback |
| bubble steals focus from Meet | passive cards use `showInactive()`; rehearse with Meet focused |
| a judge asks for a number not in the ledger | say “pending” or show `docs/JUDGE_KIT.md`; never improvise |
| Windows/Linux claim challenged | say “build targets exist; the demo laptop is macOS; packaging is untested on real Windows hardware” |
