# Task board

Status values: `todo` · `in-progress` · `blocked` · `partial` · `done`.
A task is `done` only when `make task T=TNN` and `make check` are both green.
Tasks marked `done` here are tested STRICTLY (their tests may never skip) — see `tests/conftest.py`.
Owners: Shivendra (lead, Claude Code), Saarika, Kartikey, Saksham. Each person's full plan, tools and prompts: `team/<Name>.md` (lead: `team/MASTER.md`).

Critical path: T01 → T02 → T07 → T11 → T12 → T22.

| ID | Title | Owner | Status | Depends on | Spec | Notes |
|---|---|---|---|---|---|---|
| T01 | Skeleton, contracts, fixtures, mock API | Shivendra | done | — | [spec](tasks/T01-skeleton-contracts-mock-api.md) | pre-implemented; GET /cases returns 12 fixtures |
| T02 | Policy engine + property tests | Shivendra | done | T01 | [spec](tasks/T02-policy-engine.md) | pre-implemented; 40+ unit tests + hypothesis invariants |
| T03 | .eml parser | Kartikey | done | T01 | [spec](tasks/T03-eml-parser.md) | 10 fixtures + 4 unit tests green; topmost trusted Authentication-Results only, HTML comments/display:none stripped |
| T04 | Domain checks + email signals | Kartikey | todo | T01, T03 | [spec](tasks/T04-domain-checks.md) | domains.py needs only T01 |
| T05 | Ask extractor v1.0 (A1-A7) | Saarika | done | T01 | [spec](tasks/T05-ask-extractor.md) | n=104 precision=1.000 recall=1.000; LEXICON_VERSION 1.0.0, awaiting `lexicon-v1.0` tag |
| T06 | Console UI shell | Saksham | todo | T01 | [spec](tasks/T06-console-ui.md) | |
| T07 | Extension capture core | Shivendra | in-progress | — | [spec](tasks/T07-extension-capture.md) | steps 1-7 code done + reviewed; step 8 manual Meet test pending |
| T08 | Invoice/PDF checker | Kartikey | todo | T01, T03 | [spec](tasks/T08-invoice-pdf-checker.md) | 6 fixture PDFs generated |
| T09 | Evidence vault: storage, intake, anchor | Saksham | partial | T01 | [spec](tasks/T09-evidence-vault.md) | hashing + custody chain pre-implemented |
| T10 | Extension side panel UI | Saarika | done | T07 (event contract only) | [spec](tasks/T10-extension-sidepanel.md) | UI built with pure reducer and replay | 
| T11 | Live transcript path | Shivendra | todo | T05, T07 | [spec](tasks/T11-live-transcript.md) | |
| T12 | OOB-Confirm | Saksham | todo | T02, T06 | [spec](tasks/T12-oob-confirm.md) | backend part needs only T02 |
| T13 | Callback logging + checker flows | Saksham | todo | T02, T06 | [spec](tasks/T13-callback-checker-flows.md) | |
| T14 | Explanation templates EN/HI | Saksham | done | T02 | [spec](tasks/T14-explanation-templates.md) | 33/33 codes EN + Devanagari HI done; `reason_text` + `explain_template` done; 35/35 task tests + full suite green; proofread and signed off by Kartikey |
| T15 | Bedrock summary + faithfulness + red-team | Shivendra | todo | T02, T14 | [spec](tasks/T15-llm-summary-faithfulness.md) | prompt builder pre-done |
| T16 | Report pack | Kartikey | todo | T09, T13 | [spec](tasks/T16-report-pack.md) | core builder needs only T01 |
| T17 | Voice uploads path | Kartikey | todo | T07 (model file), T01 | [spec](tasks/T17-voice-uploads.md) | |
| T18 | Audio channel evaluation + thresholds | Saarika + Shivendra | done | T07 | [spec](tasks/T18-audio-channel-eval.md) | |
| T19 | Research R1: loader, D2, D3, metrics | Kartikey + Shivendra | todo | T05 frozen | [spec](tasks/T19-research-baselines-metrics.md) | |
| T20 | Research R2: paraphrase attacks + filters | Shivendra | todo | T19 | [spec](tasks/T20-research-paraphrase-attacks.md) | email ICFD authors first |
| T21 | Research R3: evaluation + money figure | Shivendra | todo | T19, T20 | [spec](tasks/T21-research-eval-money-figure.md) | |
| T22 | Demo assets + 10 dry runs | Shivendra + all | todo | T07-T17 | [spec](tasks/T22-demo-assets-dry-runs.md) | consent forms first |
| T23 | Pitch deck + backup recording | Saarika + Shivendra | todo | T18, T21, T22 | [spec](tasks/T23-pitch-deck.md) | |
| T24 | Citizen Scam Check (stretch S1) | Saksham | todo | T05, T14 | [spec](tasks/T24-citizen-scam-check.md) | only if MVP done by end of Day 3 |

## Suggested day plan

| Day | Shivendra | Saarika | Kartikey | Saksham |
|---|---|---|---|---|
| 0 | lead checklist (team/MASTER.md §3) | setup | setup | setup |
| 1 | T07 | T05 | T03 → T04 | T09 → T06 |
| 2 | T11, T07 polish | T05 freeze → T10 | T08 → T17 | T06 → T12 |
| 3 | T15, T19-D3, T20, first dry run | T18 | T16 → T19 | T14 → T13 |
| 4 | T21, T22 dry runs | T23, dry runs | T19 | T24 (stretch) / dry runs |

## Notes log
<!-- One line per event: date, task, what happened (e.g. "05 Oct, T07: scores logged on Meet tab, audio audible"). -->
06 Oct, T07: steps 2-7 implemented (Gemini). Review fixed: ORT 1.14→1.20.1 (logreg.onnx is IR 10), ZipMap output unreadable in ort-web → logreg_prob.onnx, D5, window ordering, consecutiveOverHi field. Scorer verified in Node vs Python (~2.8 s/window, Node single-thread). Manual Meet test NOT done yet.
07 Oct, T05: done — n=104 sentences, precision=1.000, recall=1.000; lexicon v1.0.0 ready for `lexicon-v1.0` tag.
07 Oct, T10: extension side panel UI built, reducer tests and control assertions passing.
07 Oct, T14: done — all 33 reason codes in EN + Hindi (two proofread passes, 24 fixes); full test suite green; proofread and officially signed off by Kartikey.
07 Oct, T18: audio channel evaluation across 4 codecs + speaker-disjoint calibration completed.
07 Oct, T03: done — 10 fixtures + 4 unit tests green (`uv run pytest --task T03`); lint/format/mypy green. Note for Shivendra: on this Windows box 17 pre-existing failures remain (starlette TestClient hits the no-network socket guard, harness test reads files as cp1252) — verified identical on clean `main`, not caused by T03.

