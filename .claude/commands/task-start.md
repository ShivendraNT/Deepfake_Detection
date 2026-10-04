---
description: Leader workflow for implementing a task (plan first, then step by step)
argument-hint: "[TNN]"
---
Implement task $ARGUMENTS following AGENTS.md §5 and `docs/harness/WORKFLOW.md`:
read `docs/tasks/$ARGUMENTS-*.md` and its test file, write the plan into the spec's Agent plan
section, run `make task T=$ARGUMENTS` (expect red), implement step by step, then `make check`,
update `docs/STATUS.md`, and propose a commit message `$ARGUMENTS: ...`.
For policy/vault/extension-capture code, explain every safety-relevant line in the summary.
