# Task board

Status values: `todo` · `in-progress` · `blocked` · `partial` · `done`.
A task is `done` only when `make task T=TNN` and `make check` are both green.
Tasks marked `done` here are tested STRICTLY (their tests may never skip) — see `tests/conftest.py`.
Owners: **L** = leader (Claude Code); **B1/B2/B3** = first-years (opencode / Gemini CLI / Copilot).

Critical path: T01 → T02 → T07 → T11 → T12 → T22.

| ID | Title | Owner | Status | Depends on | Spec | Notes |
|---|---|---|---|---|---|---|
| T01 | Skeleton, contracts, fixtures, mock API | L | done | — | [spec](tasks/T01-skeleton-contracts-mock-api.md) | pre-implemented; GET /cases returns 12 fixtures |
| T02 | Policy engine + property tests | L | done | T01 | [spec](tasks/T02-policy-engine.md) | pre-implemented; 40+ unit tests + hypothesis invariants |
| T03 | .eml parser | B2 | todo | T01 | [spec](tasks/T03-eml-parser.md) | |
| T04 | Domain checks + email signals | B2 | todo | T01, T03 | [spec](tasks/T04-domain-checks.md) | domains.py needs only T01 |
| T05 | Ask extractor v1.0 (A1-A7) | B1 | done | T01 | [spec](tasks/T05-ask-extractor.md) | n=92, P=0.927, R=0.950 on 3 scripts; freeze + tag |
| T06 | Console UI shell | B3 | todo | T01 | [spec](tasks/T06-console-ui.md) | |
| T07 | Extension capture core | L | todo | — | [spec](tasks/T07-extension-capture.md) | manifest + voice_rules.js pre-done |
| T08 | Invoice/PDF checker | B2 | todo | T01, T03 | [spec](tasks/T08-invoice-pdf-checker.md) | 6 fixture PDFs generated |
| T09 | Evidence vault: storage, intake, anchor | B3 | partial | T01 | [spec](tasks/T09-evidence-vault.md) | hashing + custody chain pre-implemented |
| T10 | Extension side panel UI | B1 | todo | T07 (event contract only) | [spec](tasks/T10-extension-sidepanel.md) | build from replay file |
| T11 | Live transcript path | L | todo | T05, T07 | [spec](tasks/T11-live-transcript.md) | |
| T12 | OOB-Confirm | B3 | todo | T02, T06 | [spec](tasks/T12-oob-confirm.md) | backend part needs only T02 |
| T13 | Callback logging + checker flows | B3 | todo | T02, T06 | [spec](tasks/T13-callback-checker-flows.md) | |
| T14 | Explanation templates EN/HI | B1 | todo | T02 | [spec](tasks/T14-explanation-templates.md) | |
| T15 | Bedrock summary + faithfulness + red-team | L | todo | T02, T14 | [spec](tasks/T15-llm-summary-faithfulness.md) | prompt builder pre-done |
| T16 | Report pack | B2 | todo | T09, T13 | [spec](tasks/T16-report-pack.md) | core builder needs only T01 |
| T17 | Voice uploads path | B1 | todo | T07 (model file), T01 | [spec](tasks/T17-voice-uploads.md) | |
| T18 | Audio channel evaluation + thresholds | B3 + L | todo | T07 | [spec](tasks/T18-audio-channel-eval.md) | |
| T19 | Research R1: loader, D2, D3, metrics | B2 + L | todo | T05 frozen | [spec](tasks/T19-research-baselines-metrics.md) | |
| T20 | Research R2: paraphrase attacks + filters | L | todo | T19 | [spec](tasks/T20-research-paraphrase-attacks.md) | email ICFD authors first |
| T21 | Research R3: evaluation + money figure | L | todo | T19, T20 | [spec](tasks/T21-research-eval-money-figure.md) | |
| T22 | Demo assets + 10 dry runs | L + all | todo | T07-T17 | [spec](tasks/T22-demo-assets-dry-runs.md) | consent forms first |
| T23 | Pitch deck + backup recording | B1 + L | todo | T18, T21, T22 | [spec](tasks/T23-pitch-deck.md) | |
| T24 | Citizen Scam Check (stretch S1) | B3 | todo | T05, T14 | [spec](tasks/T24-citizen-scam-check.md) | only if MVP done by end of Day 3 |

## Suggested day plan

| Day | L | B1 | B2 | B3 |
|---|---|---|---|---|
| 1 | T07, review T03-T05 | T05 | T03 → T04 | T09 → T06 |
| 2 | T11, T07 polish | T14, T10 | T08 | T06, T12 |
| 3 | T15, T20, T22 | T17 | T16, T19 | T13, T18 |
| 4 | T21, T22 dry runs | T23 | T19 | T24 if time |

## Notes log
<!-- One line per event: date, task, what happened (e.g. "05 Oct, T07: scores logged on Meet tab, audio audible"). -->
07 Oct, T05: ask extractor v1.0 done (n=92, P=0.927, R=0.950 on 3 scripts).
