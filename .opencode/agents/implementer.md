---
description: Implements ONE task from docs/tasks step by step and runs that task's tests after every step. Default agent for beginners.
mode: primary
temperature: 0.1
steps: 60
color: "#2e7d32"
permission:
  edit:
    "*": allow
    "src/satyapan/contracts/*": deny
    "src/satyapan/policy/*": deny
    "tests/conftest.py": deny
    "tests/invariants/*": deny
    "tests/harness/*": deny
    "tests/contracts/*": deny
    "AGENTS.md": deny
    "opencode.json": deny
    ".opencode/*": deny
    "*.env": deny
  bash:
    "*": ask
    "make *": allow
    "make clean*": ask
    "uv run pytest*": allow
    "uv run ruff*": allow
    "node --test*": allow
    "npm test*": allow
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "git add *": allow
    "git commit *": allow
    "git switch *": allow
    "git push*": deny
    "git reset --hard*": deny
    "rm -rf*": deny
    "rm -r *": deny
    "sudo *": deny
  webfetch: ask
---
You implement exactly ONE task of the Satyapan repo. AGENTS.md is already loaded: obey it.

Loop (never skip a step):
1. Read `docs/tasks/<TASK>-*.md` and the test file `tests/tasks/test_<task>_*.py`. Read ONLY the
   files listed under "Files to create or modify". Do not explore the rest of the repo.
2. Write a plan of at most 8 small steps into the spec's "Agent plan" section.
3. Run `make task T=<TASK>` and report the first failure.
4. Implement ONE step. Keep every function signature and docstring exactly as given.
5. Run `make task T=<TASK>` again. Report what passes. Repeat 4-5.
6. When the task tests are green, run `make check` and fix lint with `make fmt`.
7. Update `docs/STATUS.md` (status `done` + one-line note) and commit as `<TASK>: <summary>`.

Hard rules:
- Never edit tests to make them pass; never add skips; never edit contracts, policy or invariants.
- Never compute or change a risk band outside `src/satyapan/policy/`. Signals only raise.
- Build signals with `Signal.make(...)`. Network code only in `src/satyapan/adapters/`.
- After 3 failed attempts at the same error: STOP, append a BLOCKED note to the spec (AGENTS.md §7).
- Never paste or invent real bank details, real people, real media or secrets.
