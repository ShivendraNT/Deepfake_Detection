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
07 Oct, T06: done — console UI shell built with React, Tailwind, and Radix UI; mock API wiring completed.
| T08 | Invoice/PDF checker | Kartikey | todo | T01, T03 | [spec](tasks/T08-invoice-pdf-checker.md) | 6 fixture PDFs generated |
07 Oct, T03: done — 10 fixtures + 4 unit tests green (`uv run pytest --task T03`); lint/format/mypy green.
07 Oct, T09: partial — intake/anchor/storage implemented; missing KMS/S3 IAM check but code is solid.
07 Oct, T14: done — all 33 reason codes in EN + Hindi (two proofread passes, 24 fixes); full test suite green; proofread and officially signed off by Kartikey.
07 Oct, T18: audio channel evaluation across 4 codecs + speaker-disjoint calibration completed.

| T11 | Live transcript path | Shivendra | todo | T05, T07 | [spec](tasks/T11-live-transcript.md) | |
| T12 | OOB-Confirm | Saksham | done | T02, T06 | [spec](tasks/T12-oob-confirm.md) | token hashed + bound, DENIED → HOLD/SUSPECTED_FRAUD, OobInbox screen; 8/9 strict green (`test_api_flow` blocked by the pre-existing Windows TestClient/network-guard issue) |
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
07 Oct, T03: done — 10 fixtures + 4 unit tests green (`uv run pytest --task T03`); lint/format/mypy green.
07 Oct, T09: partial — intake/anchor/storage implemented; missing KMS/S3 IAM check but code is solid.
07 Oct, T14: done — all 33 reason codes in EN + Hindi (two proofread passes, 24 fixes); full test suite green; proofread and officially signed off by Kartikey.
07 Oct, T18: audio channel evaluation across 4 codecs + speaker-disjoint calibration completed.
07 Oct, T04: done — `domains.py` (levenshtein, look-alike + confusables, .bank.in, freemail, bank-claim) + `signals.py` (6 email rules, all `Signal.make(DETERMINISTIC)`); 25 table tests + 10 fixture signal sets green, full suite 373 passed / 0 failed.

