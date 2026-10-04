---
description: Review the current branch against its task spec and the safety invariants
agent: reviewer
subtask: true
---
Review the current branch.

Changed files:
!`git diff --stat main...HEAD`

Commits:
!`git log --oneline main..HEAD`

Follow your reviewer checklist (spec scope, signatures, raise-only bands, Signal.make, network
boundary, data hygiene, scores hidden from makers, no auto-reporting, tests not weakened).
Run `make task` for the task id in the branch name and `make check`. End with APPROVE or
REQUEST CHANGES.
