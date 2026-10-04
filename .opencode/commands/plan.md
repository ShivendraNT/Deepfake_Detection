---
description: Write a small step plan for a task without coding, e.g. /plan T13
agent: planner
---
Plan task $1: read `docs/tasks/$1-*.md`, its test file and the listed stubs; run `make task T=$1`
once; write at most 8 checklist steps into the spec's "Agent plan" section. No code.
