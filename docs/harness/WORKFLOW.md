# The agent workflow (every task, every tool)

This loop is what makes a free/mid-level model reliable: small specs, executable tests, one step
at a time, and a hard stop when stuck. Copy-paste prompts are in `docs/harness/PROMPTS.md`.

## The loop

```
pick task → read spec → read ONLY listed files → write plan → red test → smallest step
   → task test → (repeat) → make check → update STATUS.md → commit → PR
```

### 1. Pick a task
- Open `docs/STATUS.md`. Pick a `todo` task assigned to you whose **Depends on** tasks are `done`
  (or whose spec says which part you can start early).
- Set it to `in-progress` with your name. Create a branch: `git switch -c t05-ask-extractor`.

### 2. Read the spec
- Read `docs/tasks/TNN-*.md` top to bottom. It lists: goal, files you may change, files you must
  NOT touch, exact interfaces, steps, acceptance criteria, the test command and common mistakes.
- If something is ambiguous, ask the leader BEFORE coding. Do not guess interfaces.

### 3. Read only the listed files (context hygiene)
- Read: `AGENTS.md` (always), the spec, the files under "Files to create or modify", and the test
  file `tests/tasks/test_tNN_*.py`. That is usually enough.
- Do NOT ask the agent to "explore the repo" or read `src/` recursively. Free models lose track and
  start editing unrelated files.
- If you need a type, open `src/satyapan/contracts/__init__.py` (one file lists every model).
- Start a NEW agent session for each task. Long sessions drift.

### 4. Write the plan
- Ask the agent (or the `planner` agent) for a plan of **at most 8 steps**, each one small and
  testable. Paste it into the spec's "Agent plan" section (or the PR description).
- Each step names the function it implements and which test it should turn green.

### 5. Red first
- `make task T=TNN` → you should see FAILURES (strict mode: `NotImplementedError` = failure).
  This proves the tests are wired to your task.

### 6. Implement the smallest step
- Implement ONE function or ONE step. Keep the signature and the docstring exactly as given
  (the docstring is the spec). Do not touch other tasks' files.
- `make task T=TNN` again. Read the first failure only; fix it; repeat.

### 7. Full check
- `make check` (lint + format + mypy on core + all tests). Fix formatting with `make fmt`.
- Every other test must still pass or skip. If an invariant test fails, your change broke a
  safety rule: undo it, do not edit the invariant.

### 8. Finish
- `docs/STATUS.md`: set `done`, one-line note (e.g. "precision 0.94 / recall 0.88 on 84 sentences").
- Commit: `TNN: <what you did>` (e.g. `T05: lexicon v1.0 with 9 patterns per ask type`).
- Open a PR with `.github/pull_request_template.md`. Ask the `reviewer` agent to review the diff.

## When stuck (hard rule)

- **3 failed attempts on the same error → STOP.**
- Do not: delete tests, add `pytest.skip`, change a contract, change an invariant, "simplify" a
  test, or rewrite files outside the spec.
- Do: append to the spec
  ```
  BLOCKED (05 Oct 14:30, opencode / <model>): tried X, Y, Z. Error: <exact message>.
  Best guess: <one line>. Files touched: <list>.
  ```
  set the task to `blocked` in STATUS.md, commit, message the leader.
- Rate-limited? Switch tool (opencode Zen free → Gemini CLI → Copilot). Same AGENTS.md; same loop.
  Paste the spec's "Agent plan" so the new tool continues where the last one stopped.

## Context hygiene checklist

- [ ] New session per task.
- [ ] Only listed files in context.
- [ ] Never paste real media, bank details, `.env`, or dataset text into a prompt.
- [ ] Never accept a diff touching files outside the spec without reading it.
- [ ] After 20+ messages in one session, summarise progress into the spec and start fresh.

## Commit message format

```
TNN: <imperative summary, <= 72 chars>

- what changed (1-3 bullets)
- tests: make task T=TNN green; make check green
```

## Which agent for what (opencode)

| Agent | Mode | Use it to | Can edit? |
|---|---|---|---|
| `implementer` | primary | implement a task step by step | yes (not contracts/policy/invariants) |
| `reviewer` | subagent | check a diff against the spec + invariants | no |
| `planner` | primary (optional) | write the ≤ 8-step plan | no |
| `tester` | subagent (optional) | add extra tests in `tests/` | only `tests/` (not invariants) |
| `researcher-eval` | primary (optional) | research scripts T18-T21 | only `research/`, `results/`, `figures/` |
| `docs-pitch` | primary (optional) | docs and pitch (T23) | only `docs/` |

Switch primary agents with Tab; call a subagent with `@reviewer ...`. Custom commands:
`/task T07`, `/check`, `/review`, `/stuck`. Model: leave unset in agent files; pick a model with
`/models` (free Zen models appear as `opencode/<id>` and the list changes often).
