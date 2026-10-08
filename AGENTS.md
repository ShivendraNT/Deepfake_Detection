# AGENTS.md — rules for every AI coding agent (and every human)

This is the ONE canonical instruction file. Antigravity, opencode, Copilot and Codex read it directly.
Claude Code reads it via `CLAUDE.md`, Gemini CLI via `GEMINI.md`. Do not duplicate rules elsewhere.

## 0. FIRST: who are you working with? (every new session)

Before anything else in a new session, if the human has not told you their name yet, ask exactly:
**"Hi! Who am I working with — Shivendra, Saarika, Kartikey or Saksham?"**
Then read that person's file and follow it for the whole session:

| Name | File | Role |
|---|---|---|
| Shivendra | `team/MASTER.md` | tech lead — critical path, research, all merges |
| Saarika | `team/Saarika.md` | ask extractor, side panel, voice calibration, deck |
| Kartikey | `team/Kartikey.md` | email / invoice / voice checkers, report pack, research metrics |
| Saksham | `team/Saksham.md` | console, evidence vault, OOB-Confirm, workflows, explanations |

After reading it, check `docs/STATUS.md`, then tell them in simple words: (1) their next task and
step, (2) which model to use for it (each file's section 2), (3) the exact prompt or command.
One step at a time. Never assign them a task owned by someone else without the lead's OK.

## 1. What this project is (30 seconds)

**Satyapan** (सत्यापन, "verification") is a Payment Verification Desk for the accounts-payable
team of an Indian SME. A maker enters a pending payment. We compare it with the company's own
vendor master to set a **floor** (PASS / VERIFY / HOLD). Emails, invoices, voice notes and live
Meet/Teams audio are **evidence that can only raise the band**, never lower it. A Chrome
extension warns during browser calls. OOB-Confirm asks the real requester "did you ask for this?".
The report pack is a UTR-first draft for 1930 / NCRP / the bank. A human always submits it.

Full design: `docs/ARCHITECTURE.md`. Words you don't know: `docs/GLOSSARY.md`.

## 2. Non-negotiable rules (tests enforce most of them — never weaken a test)

1. **Only `src/satyapan/policy/` sets the band.** No other code may compute, change or "fix" a band.
2. **Raise-only.** A signal can raise the band or do nothing. Nothing may lower it. LLM- or
   style-sourced signals are capped at VERIFY. (`tests/invariants/`)
3. **The floor uses trusted data only:** the maker-entered transaction + vendor master + config.
   Never pass email/PDF/audio/LLM content into `compute_floor`.
4. **Build every Signal with `Signal.make(code, source=..., evidence_ids=[...])`.** Never type
   group/target/strength by hand. Deterministic detectors use `SignalSource.DETERMINISTIC`.
5. **Callback numbers come only from the vendor master or the employee directory**, never from
   a message, document or call.
6. **No auto-reporting.** No code may submit anything to 1930, NCRP, a bank or the police. There
   is no public 1930/NCRP API — never invent one. Reports are drafts (`submission = "MANUAL_ONLY"`).
7. **LLM safety.** The LLM gets no tools, never sets the band, and untrusted text never goes into
   the system prompt (use `satyapan.explain.prompt`). Its output must pass the faithfulness checker.
8. **Network only in `src/satyapan/adapters/`.** Unit tests never touch the network; use the fakes
   in `satyapan/adapters/base.py`.
9. **Makers never see raw scores** (oracle-abuse mitigation). Only checker/security do.
10. **Data hygiene.** Never paste real voices, real media, real bank details, real customer data,
    API keys or `.env` into a prompt, an issue, or the repo. Free models may train on prompts.
    Demo data is fake on purpose (IFSC `FAK…`, accounts `9999…`, domains `*.example`).
11. **Do not edit without leader approval:** `src/satyapan/contracts/`, `src/satyapan/policy/`,
    `tests/conftest.py`, `tests/invariants/`, `tests/harness/`, `tests/contracts/`, `AGENTS.md`,
    `opencode.json`. If you think a contract is wrong, STOP and write a note (section 7).
12. **Never delete, skip, or loosen a test to make it pass.** Fix the code instead.

## 3. Repo map (only what you need)

```
src/satyapan/contracts/   shared Pydantic models + enums + signal table   (DONE, frozen)
src/satyapan/policy/      floor + escalation + clearance + permissions     (DONE, frozen)
src/satyapan/master/      vendor master / history / directory loader       (DONE)
src/satyapan/vault/       hashing + custody chain (DONE); storage/intake/anchor (T09)
src/satyapan/email/       .eml parser (T03), domain checks + signals (T04)
src/satyapan/document/    invoice regex + PDF metadata + master diff (T08)
src/satyapan/asks/        deterministic ask extractor A1-A7 (T05)
src/satyapan/voice/       rules.py (DONE); ONNX detector + uploads (T17)
src/satyapan/live/        live call service (T11)
src/satyapan/explain/     prompt.py (DONE); templates (T14); LLM + faithfulness (T15)
src/satyapan/workflows/   OOB-Confirm (T12); callbacks/status/override/watchlist (T13)
src/satyapan/report/      UTR-first report pack (T16)
src/satyapan/citizen/     citizen Scam Check (T24, stretch)
src/satyapan/adapters/    AWS + Whisper adapters — the ONLY place with network code
src/satyapan/api/         FastAPI routes (DONE glue; routes call task code -> HTTP 501 until done)
extension/                Chrome MV3 extension (T07 capture, T10 side panel, T22 demo tab)
console/                  React + Vite + Tailwind web console (T06)
research/                 "Ask, Not Style" study scripts (T18-T21)
tests/tasks/              one acceptance test file per task: test_tNN_*.py
docs/tasks/               one spec per task: TNN-*.md   <- START HERE
docs/STATUS.md            task board
```

## 4. Commands

| Command | What it does |
|---|---|
| `make sync` | install deps (uv). No uv? see README "pip fallback" |
| `make task T=T07` | run ONLY task T07's tests, strictly (red until implemented) |
| `make check` | ruff lint + format check + mypy (core) + all tests. Must be green before commit |
| `make test` | all tests; unfinished tasks show as SKIPPED, not failed |
| `make fmt` | auto-format + auto-fix lint |
| `make run` | API at http://127.0.0.1:8000/docs |
| `make ext-test` | node tests for the extension |
| `make console-test` | vitest for the console (needs npm) |

## 5. How to do a task (the loop — details in `docs/harness/WORKFLOW.md`)

1. Pick the first unfinished task in YOUR `team/<Name>.md` whose **Owner** in `docs/STATUS.md`
   is you and whose dependencies are `done`. Never pick another person's task. Branch: `git switch -c tNN-short-name`.
2. Read `docs/tasks/TNN-*.md` fully. Read ONLY the files it lists. Do not read the whole repo.
3. Write your plan (max 8 bullet steps) in the spec's "Agent plan" section. Keep it small.
4. Run `make task T=TNN` and see it fail (red).
5. Implement the smallest step. Keep the existing function signatures and docstrings.
6. Run `make task T=TNN` again. Repeat 5-6 until green.
7. Run `make check`. Fix lint with `make fmt`. Everything must be green.
8. Update `docs/STATUS.md` (status → `done`, add a one-line note). Commit: `TNN: <what you did>`.

## 6. Coding conventions

- Python 3.11+, full type hints, Pydantic v2, line length 100, `ruff` style.
- Keep functions small and pure where possible. No global mutable state except the API `AppState`.
- Parse failures raise `ValueError` (the pipeline turns them into a GREY flag, never into PASS).
- Use `from satyapan.contracts import ...` for shared types. Never redefine a contract model.
- Times are timezone-aware (`datetime` with tzinfo). Money is whole rupees (`int`).
- Show accounts masked (`mask_account`) in UI text, logs and LLM prompts.
- Tests: `pytest`, no network, no real media. Generate audio in tests (see T17), never commit it.

## 7. When stuck

Stop after **3 failed attempts** at the same error. Then:
1. Do not keep editing random files. Do not edit tests or contracts.
2. Add to the bottom of your task spec:
   `BLOCKED (date, agent/model): what you tried, the exact error, your best guess.`
3. Set the task to `blocked` in `docs/STATUS.md`, commit, and tell the leader.
Rate-limited? Switch tool in this order: opencode Zen free → Gemini CLI → Copilot. The same
`AGENTS.md` rules apply in every tool.
