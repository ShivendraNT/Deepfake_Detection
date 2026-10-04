---
description: Start or continue a task, e.g. /task T05
agent: implementer
---
Work on task $1 of this repo.

Current branch and changes:
!`git branch --show-current`
!`git status --short`

1. Find and read the spec `docs/tasks/$1-*.md` and the test file `tests/tasks/test_*` whose name
   starts with the lower-case task id (e.g. `test_t05_`). Read ONLY the files the spec lists.
2. If the spec's "Agent plan" section is empty, write a plan of at most 8 small steps there.
   If it has ticked steps, continue with the first unticked one.
3. Run `make task T=$1`, then implement ONE step, then run `make task T=$1` again.
4. Stop after each step and report: step done, tests passing/failing, next step.
Follow AGENTS.md. Never edit tests, contracts, policy or invariants.
