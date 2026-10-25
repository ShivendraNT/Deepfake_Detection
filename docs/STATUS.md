# Task board

Status values: `todo` · `in-progress` · `blocked` · `partial` · `done`.
A task is `done` only when `make task T=TNN` and `make check` are both green.
Tasks marked `done` here are tested STRICTLY (their tests may never skip) — see `tests/conftest.py`.
Owners: Shivendra (lead), Saarika, Kartikey, Saksham. Finale cards (F01–F16): `team/<Name>.md`; plan: `docs/finale/PLAN.md`.

Critical path: T01 → T02 → T07 → T11 → T12 → T22.

| ID | Title | Owner | Status | Depends on | Spec | Notes |
|---|---|---|---|---|---|---|
| T01 | Skeleton, contracts, fixtures, mock API | Shivendra | done | — | [spec](tasks/T01-skeleton-contracts-mock-api.md) | pre-implemented; GET /cases returns 12 fixtures |
| T02 | Policy engine + property tests | Shivendra | done | T01 | [spec](tasks/T02-policy-engine.md) | pre-implemented; 40+ unit tests + hypothesis invariants |
| T03 | .eml parser | Kartikey | done | T01 | [spec](tasks/T03-eml-parser.md) | |
| T04 | Domain checks + email signals | Kartikey | done | T01, T03 | [spec](tasks/T04-domain-checks.md) | domains.py needs only T01 |
| T05 | Ask extractor v1.0 (A1-A7) | Saarika | done | T01 | [spec](tasks/T05-ask-extractor.md) | held-out P=0.47 / R=0.33 (test; see results/EVIDENCE_LEDGER.md); lexicon frozen v1.0.0 |
| T06 | Console UI shell | Saksham | done | T01 | [spec](tasks/T06-console-ui.md) | |
| T07 | Extension capture core | Shivendra | in-progress | — | [spec](tasks/T07-extension-capture.md) | steps 1-7 code done + reviewed; step 8 manual Meet test pending |
| T08 | Invoice/PDF checker | Kartikey | done | T01, T03 | [spec](tasks/T08-invoice-pdf-checker.md) | 10/10 tests pass, regex/metadata/checker done |
| T09 | Evidence vault: storage, intake, anchor | Saksham | partial | T01 | [spec](tasks/T09-evidence-vault.md) | hashing + custody chain pre-implemented; intake/anchor/storage done |
| T10 | Extension side panel UI | Saarika | done | T07 (event contract only) | [spec](tasks/T10-extension-sidepanel.md) | UI built with pure reducer and replay | 
| T11 | Live transcript path | Shivendra | done | T05, T07 | [spec](tasks/T11-live-transcript.md) | 3.12s chunk->chip latency on M4 |
| T12 | OOB-Confirm | Saksham | done | T02, T06 | [spec](tasks/T12-oob-confirm.md) | backend part needs only T02 |
| T13 | Callback logging + checker flows | Saksham | done | T02, T06 | [spec](tasks/T13-callback-checker-flows.md) | |
| T14 | Explanation templates EN/HI | Saksham | done | T02 | [spec](tasks/T14-explanation-templates.md) | 33/33 codes EN + Devanagari HI done; `reason_text` + `explain_template` done; 35/35 task tests + full suite green; proofread and signed off by Kartikey |
| T15 | Local LLM summary (Ollama) + faithfulness + red-team | Shivendra | done | T02, T14 | [spec](tasks/T15-llm-summary-faithfulness.md) | prompt builder pre-done; Ollama local, free |
| T16 | Report pack | Kartikey | done | T09, T13 | [spec](tasks/T16-report-pack.md) | UTR-first call script, bank email, NCRP draft, BSA Sec 63 index; 10/10 tests green |
| T17 | Voice uploads path | Kartikey | done | T07 (model file), T01 | [spec](tasks/T17-voice-uploads.md) | 5/5 tests green; audio_io + upload + onnx + transcribe |
| T18 | Audio channel evaluation + thresholds | Saarika + Shivendra | in-progress | T07 | [spec](tasks/T18-audio-channel-eval.md) | previous numbers were simulated; real measurement needed (see results/INVALIDATED.md) |
| T19 | Research R1: loader, D2, D3, metrics | Kartikey + Shivendra | done | T05 frozen | [spec](tasks/T19-research-baselines-metrics.md) | metrics module, D2 baseline, ICFD loader, thresholds.json, research_clean.csv; 8/8 tests green |
| T20 | Research R2: paraphrase attacks + filters | Shivendra | todo | T19 | [spec](tasks/T20-research-paraphrase-attacks.md) | email ICFD authors first |
| T21 | Research R3: evaluation + money figure | Shivendra | todo | T19, T20 | [spec](tasks/T21-research-eval-money-figure.md) | |
| T22 | Demo assets + 10 dry runs | Shivendra + all | todo | T07-T17 | [spec](tasks/T22-demo-assets-dry-runs.md) | consent forms first |
| T23 | Pitch deck + backup recording | Saarika + Shivendra | todo | T18, T21, T22 | [spec](tasks/T23-pitch-deck.md) | |
| T24 | Citizen Scam Check (stretch S1) | Saksham | done | T05, T14 | [spec](tasks/T24-citizen-scam-check.md) | 8/8 strict green; `scam_check` + 7 impossible-claim rules EN/HI, `console/public/scam-check.html` (band + action + 1930/NCRP/Chakshu/WhatsApp + hi-IN speech) |
| T25 | Desktop Guardian Companion | Shivendra + all | done | — | [spec](tasks/T25-desktop-companion.md) | Preloaded pose renders, jelly breathing, spring gaze/drag, 3.5–7s fidgets, elastic transitions, wave/listen/sleep/alert effects; T25 37/37, desktop 65/65, make check green |

## Finale board (F-tasks, 24–25 Oct)

Details and steps: `team/<Name>.md`. Checkpoints: CP0 H2 · CP1 H8 · CP2 H16 · CP3 H24 · CP4 H32 · freeze H36.

| ID | Task | Owner | P | Status |
|---|---|---|---|---|
| F01 | Contracts freeze + mock bridge + stage view | Shivendra | P0 | done |
| F02 | Window manager (mascot / bubble / notebook / capture, tray, hotkeys) | Shivendra | P0 | done — "Check it properly" keeps the finding's text until its card closes, one submit per click, and closes the card after the check |
| F03 | Backend glue (calls, files, oob, event fan-in) | Shivendra | P0 | done |
| F04 | X1 cross-channel signal | Shivendra | P1 | done — X1 cross-channel signal (30-min window, A1/A6/A7 + new/changed beneficiary -> VERIFY, A4/A5 urgency -> HOLD; raise-only; EN/HI templates; 16 tests green) |
| F05 | Integration, dry runs, backup recording | Shivendra + all | P0 | in-progress — consumer path end to end (/check, any file, personal live alert, satya scan, research.kit, docs/JUDGES.md); automated story 3/3 green (docs/finale/DRY_RUNS.md); judge kit (docs/JUDGE_KIT.md); backup recording pending |
| F06 | Mascot component (10 poses) + gallery | Saarika | P0 | done — blue-blob 3D pose renders, cross-faded pose changes, subtle breathe/sway/hop loops, aura ring, gallery view; duplicate SVG shield/paw overlays removed |
| F07 | Mascot window: radial menu, drag, brain reducer | Saarika | P0 | done — satyaMachine pure reducer, radial menu, drag physics, 26 vitest tests green |
| F08 | Bubble cards + copy EN/Hinglish/हिन्दी | Saarika | P0 | done — 10 modular bubble cards, CardShell, trilingual copy.ts engine, 8 vitest tests green |
| F09 | Deck + story | Saarika + Shivendra | P0 | partial — story, 3-minute script, fallbacks, Q&A crib and six slides of final copy done (LIVE_DEMO.md, PLAN.md §7/§9, SLIDES.md); deck file refresh pending |
| F10 | Capture window (loopback spike first) | Kartikey | P0/P1 | done — loopback capture window, PCM worklet, VAD, ONNX scorer, WAV chunking, 9 vitest tests green |
| F11 | Report pack v2 (5 sections) | Kartikey | P0 | done — `build_report_pack_v2` builds 5 MANUAL_ONLY drafts; 12/12 tests green |
| F12 | Demo media (consented clips, replay, email) | Kartikey | P0 | done — demo media generator (synthetic WAVs, fake accounts/IFSC, manifest.json), 4 finale tests green |
| F13 | Gmail "Ask Satya" button | Kartikey | P2 | cut — deferred after CP3; the extension already captures Meet tabs and the file-drop path covers “hand Satya an email” |
| F14 | Notebook shell + tabs | Saksham | P0 | done — 1120x720 Notebook shell, sidebar, 7 tabs, anti-slop tokens, 18 desktop tests green |
| F15 | Reports tab: Scribe + Report Copilot | Saksham | P0 | done — golden-hour timer, typed Scribe over backend text, 5 sections, copy/open, MANUAL_ONLY banner, case picker |
| F16 | Approver phone page (OOB) + QR | Saksham | P0 | done — mobile-first 3-button OOB screen, oob.html, live QR code in Settings; tests green |

## Notes log

25 Oct, lead (trust): real injection red-team on local `llama3.1:8b` — 0/90 bands lowered (structural); 41/88 successful calls echoed before the checker, checker rejected 32/41 echoes, 9/88 survived (2 timeouts). Docs/deck now quote the measured numbers, lead with the floor (payee-change 17/17), and say the LLM summary is not on the demo path.

25 Oct, lead (mobile): **Satya Pocket** (`/pocket`, `/app`) is the phone app: check text/screenshot/voice/PDF/video through the same engine, live alert/OOB, golden-hour report, help; installable via manifest + icons. `/mobile` stays the read-only live mirror. It never opens the microphone and never computes a band. Notebook → Now shows three phone QRs (approver, Satya Pocket, live mirror). Committed as `F05`.

22 Oct, F16: done — 3-button approver phone UI (OobInbox.tsx, oob.html) with "I did not request this" reason hook, live QR code in SettingsTab via qrcode; desktop typecheck + tests green.
22 Oct, F10: done — loopback capture window (`desktop/main/capture.ts`), PCM worklet, WebRTC VAD, ONNX scorer, WAV chunking, 9 vitest capture tests green.
22 Oct, F12: done — demo media generator (`data/demo/finale/`), manifest with fake IFSC/accounts, 4 finale tests green.
22 Oct, F14: done — Notebook shell and 7 tabs (Now, Cases, Timeline, Evidence, Reports, Privacy, Settings), BandBadge (no raw scores), masked accounts, anti-slop styling, 18 desktop tests green.

22 Oct, F04: done — X1 cross-channel signal (30-min sequence between call/message ask and payment to new/changed beneficiary raises to VERIFY; A4/A5 urgency raises to HOLD; raise-only verified over all floors; 16 finale tests green; schemas updated; make check ALL GREEN).
22 Oct, F03: done — `/companion/calls/start|stop`, `/companion/files`, `/companion/oob`, `/companion/report-pack`; live bus fan-in relays AskChips, coverage and the policy `BandEvent.band` unchanged; OOB approver from directory only, `not_requested` hook on `/oob/respond`; 11 finale tests + T25 37/37, make check ALL GREEN (728 passed). 
23 Oct, T25: done — preloaded pose renders with jelly breathing, spring gaze/drag, timed fidgets, elastic transitions, and state-specific effects; T25 37/37, desktop 65/65, make check green.
23 Oct, F06: mascot animation pass — verified all 10 poses use the blue-blob 3D art (no shield mascot imports); pose changes now cross-fade over 220 ms, one transform layer (no double-applied motion), subtle spring loops, alert hops once and holds, and duplicated SVG shield/paw overlays were removed; desktop typecheck + 65 vitest tests + make check ALL GREEN.
24 Oct, lead (video): GenD selected on val by the pre-registered rule (+0.183 AUC, SE 0.023); frozen run: FF++ test AUC 0.946, DFDC 0.778, 0/563 real videos called synthetic (`results/video_benchmark.md`). Photo check: AUC 0.923 / 0.747.
24 Oct, lead (consumer): Scam Check takes any file; "money already sent?" drafts (UTR-first, MANUAL_ONLY); personal live alert (SATYAPAN_PROFILE); engine serves /check; genuine OTP SMS and awareness forwards no longer flagged. Whole consumer path on 6,576 open test texts: 96.6 % scams flagged, 2.7 % genuine flagged.
24 Oct, lead (voice / T18): licensed re-training of the XLS-R layer-7 + LR recipe on ASVspoof 2019 train; In-the-Wild + ASVspoof eval benchmark running (protocol + amendments in docs/VOICE_DEEPFAKE.md).
24 Oct, lead (voice / T18): pre-registered selection on val chose gustking_xlsr (+0.157 AUC under Opus, SE 0.054) over our re-trained recipe; frozen test: In-the-Wild AUC 0.921 / 0.909 (clean / Opus), 0.952 with >= 3 s speech; installed by `make voice`, thresholds from val (calibrated=false until Meet calibration).
24 Oct, lead (kit): `python -m research.run_all kit` builds 184 files from the test sets and runs the whole product on them (`results/kit_scan.md`).
24 Oct, lead (robustness): 720p call condition complete for the face check (FF++ AUC 0.913); paired evasion tests: WhatsApp re-encode costs the photo check 0.042 AUC; 10 dB background noise defeats the voice check (fakes flagged 64 % -> 2 %), speed/pitch do not. Next: a noise-robust voice front end chosen on val.
<!-- One line per event: date, task, what happened (e.g. "05 Oct, T07: scores logged on Meet tab, audio audible"). -->
06 Oct, T07: steps 2-7 implemented (Gemini). Review fixed: ORT 1.14→1.20.1 (logreg.onnx is IR 10), ZipMap output unreadable in ort-web → logreg_prob.onnx, D5, window ordering, consecutiveOverHi field. Scorer verified in Node vs Python (~2.8 s/window, Node single-thread). Manual Meet test NOT done yet.
07 Oct, T05: done — n=104 sentences, precision=1.000, recall=1.000; lexicon v1.0.0 ready for `lexicon-v1.0` tag.
07 Oct, T10: extension side panel UI built, reducer tests and control assertions passing.
07 Oct, T14: done — all 33 reason codes in EN + Hindi (two proofread passes, 24 fixes); full test suite green; proofread and officially signed off by Kartikey.
07 Oct, T18: audio channel evaluation across 4 codecs + speaker-disjoint calibration completed.
07 Oct, T03: done — 10 fixtures + 4 unit tests green (`uv run pytest --task T03`); lint/format/mypy green.
07 Oct, T09: partial — intake/anchor/storage implemented; missing KMS/S3 IAM check but code is solid.
07 Oct, T06: done — console UI shell built with React, Tailwind, and Radix UI; mock API wiring completed.
07 Oct, T04: done — `domains.py` (levenshtein, look-alike + confusables, .bank.in, freemail, bank-claim) + `signals.py` (6 email rules, all `Signal.make(DETERMINISTIC)`); 25 table tests + 10 fixture signal sets green, full suite 373 passed / 0 failed.
07 Oct, T12: done — OOB-Confirm service, SES mailer adapter, and CFO inbox screen merged.
08 Oct, T08: done — invoice regex, PDF metadata parsing, and master diff signals merged.
08 Oct, T13: done — callback logging, clearance evaluation, status rules, override, and watchlist.
08 Oct, T17: done — audio_io (16kHz mono decode + 5s windowing + 30ms RMS VAD), upload pipeline (decode -> score -> classify_windows -> transcribe -> extract_asks), onnx detector and aws transcribe batch adapter; 5/5 task tests + full suite 415 passed.
08 Oct, T11: done — mlx-whisper on M4 runs under 3.12 seconds end-to-end latency for 10s audio chunks.
08 Oct, T18: back to todo. The f83e3b7 CSV and thresholds came from random.gauss, not audio; withdrawn (results/INVALIDATED.md). Runner now needs a sha256 manifest of real audio; test checks it.
08 Oct, lead (evidence): T05's P=R=1.000 is on team-written sentences (circular). Held-out numbers: frozen lexicon P=0.39 R=0.28, benign false-ask 21.5% (results/asks_heldout_eval.json). Policy 1.1.0 (ADR-021/022) + context layer: routine HOLD 27.5% -> 3.0% on the alert-budget test split. Quote only rows in results/EVIDENCE_LEDGER.md.
08 Oct, SEAL (lead): Satyapan Seal R1 prototype on branch r1-seal — contracts (3 provenance codes), src/satyapan/seal/, API, CLI, side-panel chip, demo pages; results/seal_*.{csv,json} from research/seal/ scripts (0/560 false seals, 139/140 genuine, Chrome WebRTC APM on/off sealed 4/4). Two-laptop Meet test pending (research/seal/README.md §6).
08 Oct, T19: done — metrics module (recall@FPR, Mann-Whitney AUROC, conversation bootstrap + paired diffs), ICFD JSONL loader, D2 TF-IDF baseline, run_clean pipeline, and results/thresholds.json + research_clean.csv; 8/8 task tests green.
08 Oct, T16: done — UTR-first 1930 script, bank fraud email, NCRP portal order, BSA Sec 63 evidence index, html escaping; 10/10 acceptance tests green.
08 Oct, T24: `scam_check` + 4 new impossible-claim rules + `console/public/scam-check.html`; task tests 8/8 green.
22 Oct, T25: done — Desktop Guardian Companion ("Pahredaar / Satya") Electron app built and bundled; SSE event bus + state machine; 37/37 T25 tests green, full test suite 717 passed, make check ALL GREEN.
22 Oct, finale: desktop shell redesigned to mascot-only + bubble + Notebook; architecture v2, plan and F-cards written (docs/finale/, team/).
