# AGENTS.md — rules for every AI coding agent (and every human)

This is the ONE canonical instruction file. Antigravity, opencode, Copilot and Codex read it directly.
Claude Code reads it via `CLAUDE.md`, Gemini CLI via `GEMINI.md`. Do not duplicate rules elsewhere.

## 0. Start here (finale, 24–25 Oct 2026)

1. The human tells you their name and card (e.g. "Saarika, F06 step 2"). Open `team/<Name>.md`
   and work **only** on that card.
2. The design lives in `docs/GRAND_FINALS_ARCHITECTURE.md`; the plan in `docs/finale/PLAN.md`;
   mascot art, motion and copy in `docs/finale/MASCOT_SPEC.md`.
3. One step per message. After each step run the card's check command and show the output.
4. Edit only the files your card lists. Never edit someone else's folder (PLAN §3 table).

## 1. What this project is (30 seconds)

**Satyapan** (सत्यापन, "verification") protects Indian SME finance teams from deepfake and
impersonation payment fraud. Its face is **Satya**, a small desktop companion: he listens to a call
only after a yes, checks emails/invoices/voice notes you hand him, makes you verify the
*transaction* with the real approver (OOB-Confirm), and writes the golden-hour report pack.
Underneath, a deterministic policy engine compares each payment with the company's vendor master to
set a **floor** (PASS / VERIFY / HOLD). Emails, invoices, voice notes and call audio are
**evidence that can only raise the band**, never lower it. A human always submits reports.

Words you don't know: `docs/GLOSSARY.md`.

## 2. Non-negotiable rules (tests enforce most of them — never weaken a test)

1. **Only `src/satyapan/policy/` sets the band.** No other code may compute, change or "fix" a band.
   The desktop app and the companion API only relay the policy's `Decision`.
2. **Raise-only.** A signal can raise the band or do nothing. Nothing may lower it. LLM- or
   style-sourced signals are capped at VERIFY. (`tests/invariants/`)
3. **The floor uses trusted data only:** the maker-entered transaction + vendor master + config.
   Never pass email/PDF/audio/LLM content into `compute_floor`.
4. **Build every Signal with `Signal.make(code, source=..., evidence_ids=[...])`.** Never type
   group/target/strength by hand. Deterministic detectors use `SignalSource.DETERMINISTIC`.
5. **Callback / OOB contacts come only from the vendor master or the employee directory**, never
   from a message, document or call.
6. **No auto-reporting.** No code may submit anything to 1930, NCRP, CERT-In, a bank or the police.
   There is no public 1930/NCRP API — never invent one. Reports are drafts
   (`submission = "MANUAL_ONLY"`). Opening a `tel:`/`mailto:`/portal link on a user click is fine.
7. **LLM safety.** The LLM gets no tools, never sets the band, and untrusted text never goes into
   the system prompt (use `satyapan.explain.prompt`). Its output must pass the faithfulness checker.
8. **Network only in `src/satyapan/adapters/`.** Unit tests never touch the network; use the fakes
   in `satyapan/adapters/base.py`. The desktop app talks only to `127.0.0.1:8000`.
9. **Makers never see raw scores** (oracle-abuse mitigation). Only checker/security do.
10. **Consent first.** Satya starts asleep. No capture before a visible consent card is accepted;
    call audio is analysed only after a yes for that call. **Never capture the microphone.**
    Hide / Off / Quit stop the session first. Any capture error → Sleeping.
11. **Data hygiene.** Never paste real voices, real media, real bank details, real customer data,
    API keys or `.env` into a prompt, an issue, or the repo. Free models may train on prompts.
    Demo data is fake on purpose (IFSC `FAK…`, accounts `9999…`, domains `*.example`).
    Cloned voices only from a teammate who signed `docs/consent/`.
12. **Do not edit without leader approval:** `src/satyapan/contracts/`, `src/satyapan/policy/`,
    `desktop/shared/`, `desktop/preload/`, `desktop/package.json`, `tests/conftest.py`,
    `tests/invariants/`, `tests/harness/`, `tests/contracts/`, `AGENTS.md`, `opencode.json`.
    If you think a contract is wrong, STOP and write `NEEDS-CONTRACT:` under your card.
13. **Never delete, skip, or loosen a test to make it pass.** Fix the code instead.

## 3. Repo map (only what you need)

```
desktop/                  Electron app — Satya (finale focus)
  main/                   windows, tray, hotkeys, IPC, backend client   (Shivendra; capture.ts: Kartikey)
  preload/                the ONLY bridge: window.satyapan               (Shivendra)
  shared/contracts.ts     frozen TS contracts                            (Shivendra)
  renderer/src/companion/ mascot, radial menu, bubble cards              (Saarika)
  renderer/src/workspace/ Notebook window + Reports                      (Saksham)
  renderer/src/capture/   hidden capture window (system audio)           (Kartikey)
  renderer/src/shared/    api.ts + mock (Shivendra), tokens.ts + copy.ts (Saarika)
src/satyapan/contracts/   shared Pydantic models + enums + signal table   (frozen)
src/satyapan/policy/      floor + escalation + clearance + permissions     (frozen)
src/satyapan/api/companion/ companion API + SSE bus                        (Shivendra)
src/satyapan/report/      UTR-first report pack (+ pack_v2, Kartikey)
src/satyapan/{asks,email,document,voice,live,vault,workflows,explain,seal}/  detectors & workflows (built)
extension/                Chrome MV3 extension (Meet/Teams tab capture, side panel)
console/                  React web console (OOB approver page lives here)
research/                 "Ask, Not Style" study scripts
tests/tasks/              one acceptance test file per T-task: test_tNN_*.py
tests/finale/             finale tests (F-tasks)
docs/tasks/               T-task specs (T01–T25, mostly done)
docs/finale/              finale plan + mascot spec
team/<Name>.md            each person's finale cards (F01–F16)
```

## 4. Commands

| Command | What it does |
|---|---|
| `make sync` | install Python deps (uv). No uv? see README "pip fallback" |
| `make run` | API at http://127.0.0.1:8000/docs |
| `make check` | ruff lint + format check + mypy (core) + all tests. Must be green before commit |
| `make task T=T25` | run ONLY one T-task's tests, strictly |
| `make fmt` | auto-format + auto-fix lint |
| `uv run pytest tests/finale -q` | finale backend tests |
| `cd desktop && npm run dev:web` | renderer in the browser with the mock bridge (port 5174) |
| `cd desktop && npm run dev` | the real Electron app |
| `cd desktop && npm run typecheck && npx vitest run` | desktop checks |
| `make ext-test` / `make console-test` | extension / console tests |

## 5. How to do a card (the loop)

1. Read your card in `team/<Name>.md` and the docs it lists. Read ONLY the files it lists.
2. For backend T-tasks the old loop still applies: `make task T=TNN` red → smallest step → green.
3. Implement **one step**. Keep existing function signatures and docstrings.
4. Run the card's check command. Red → fix → green.
5. Before committing: `make check` (backend) and/or `npm run typecheck` (desktop) green.
6. Commit small: `F06: blink + breathe loop`. The leader decides branches/merges.

## 6. Coding conventions

- Python 3.11+, full type hints, Pydantic v2, line length 100, `ruff` style.
- TypeScript strict, React function components, Framer Motion for animation, Tailwind or tokens
  from `shared/tokens.ts` — no new UI libraries without the leader.
- Keep functions small and pure where possible. Reducers and placement maths are pure and tested.
- Parse failures raise `ValueError` (the pipeline turns them into a GREY flag, never into PASS).
- Times are timezone-aware. Money is whole rupees (`int`), shown as `₹48,50,000`.
- Show accounts masked (`mask_account`, `••••4821`) in UI text, logs and LLM prompts.
- Tests: `pytest` / `vitest`, no network, no real media.

## 7. When stuck

Stop after **3 failed attempts** at the same error. Then:
1. Do not keep editing random files. Do not edit tests or contracts.
2. Add under your card in `team/<Name>.md`:
   `BLOCKED (time, agent/model): what you tried, the exact error, your best guess.`
3. Tell the leader. Rate-limited? Switch tools (opencode free → Gemini CLI → Copilot); the same
   `AGENTS.md` rules apply everywhere.
