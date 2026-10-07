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
| T03 | .eml parser | Kartikey | todo | T01 | [spec](tasks/T03-eml-parser.md) | |
| T04 | Domain checks + email signals | Kartikey | todo | T01, T03 | [spec](tasks/T04-domain-checks.md) | domains.py needs only T01 |
| T05 | Ask extractor v1.0 (A1-A7) | Saarika | todo | T01 | [spec](tasks/T05-ask-extractor.md) | freeze + tag for research when done |
| T06 | Console UI shell | Saksham | todo | T01 | [spec](tasks/T06-console-ui.md) | |
| T07 | Extension capture core | Shivendra | todo | — | [spec](tasks/T07-extension-capture.md) | manifest + voice_rules.js pre-done |
| T08 | Invoice/PDF checker | Kartikey | todo | T01, T03 | [spec](tasks/T08-invoice-pdf-checker.md) | 6 fixture PDFs generated |
| T09 | Evidence vault: storage, intake, anchor | Saksham | done | T01 | [spec](tasks/T09-evidence-vault.md) | LocalStorage + intake + anchor_head + S3Storage (GOVERNANCE); 8/8 strict green |
| T10 | Extension side panel UI | Saarika | todo | T07 (event contract only) | [spec](tasks/T10-extension-sidepanel.md) | build from replay file |
| T11 | Live transcript path | Shivendra | todo | T05, T07 | [spec](tasks/T11-live-transcript.md) | |
| T12 | OOB-Confirm | Saksham | todo | T02, T06 | [spec](tasks/T12-oob-confirm.md) | backend part needs only T02 |
| T13 | Callback logging + checker flows | Saksham | todo | T02, T06 | [spec](tasks/T13-callback-checker-flows.md) | |
| T14 | Explanation templates EN/HI | Saksham | todo | T02 | [spec](tasks/T14-explanation-templates.md) | |
| T15 | Bedrock summary + faithfulness + red-team | Shivendra | todo | T02, T14 | [spec](tasks/T15-llm-summary-faithfulness.md) | prompt builder pre-done |
| T16 | Report pack | Kartikey | todo | T09, T13 | [spec](tasks/T16-report-pack.md) | core builder needs only T01 |
| T17 | Voice uploads path | Kartikey | todo | T07 (model file), T01 | [spec](tasks/T17-voice-uploads.md) | |
| T18 | Audio channel evaluation + thresholds | Saarika + Shivendra | todo | T07 | [spec](tasks/T18-audio-channel-eval.md) | |
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
- 07 Oct, T09: `pytest --task T09` 8/8 green, ruff + mypy clean. `make check` not runnable here (no `make`/`uv` on this Windows box); full `pytest` shows 17 failures that are identical on a pristine checkout — API tests blocked by the conftest network guard (asyncio socketpair) and one cp1252 decode in tests/harness. Needs a Linux/WSL run to confirm.
