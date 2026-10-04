---
description: Review the current branch (or PR) against its spec and the invariants
argument-hint: "[optional PR number]"
allowed-tools: Bash(git diff *) Bash(git log *) Bash(make task *) Bash(make check) Bash(gh pr diff *)
---
## Changed files
!`git diff --stat main...HEAD || true`

## Commits
!`git log --oneline main..HEAD || true`

Use the `reviewer` subagent on this branch (PR $ARGUMENTS if given: use `gh pr diff $ARGUMENTS`).
Return its checklist verdict and, if REQUEST CHANGES, a ready-to-paste PR comment for the teammate
written in simple English.
