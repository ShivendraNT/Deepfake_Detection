---
description: Write a BLOCKED note for a task after 3 failed attempts, e.g. /stuck T08
agent: implementer
---
We are stuck on task $1. Do NOT try another fix.

Last test output:
!`make task T=$1 2>&1 | tail -30`

1. Append to `docs/tasks/$1-*.md` a line:
   `BLOCKED (<date>, opencode/<model>): tried <A, B, C>. Error: <exact message>. Best guess: <one line>. Files touched: <list>.`
2. In `docs/STATUS.md` set task $1's status to `blocked`.
3. Commit with message `$1: blocked - <short reason>` and tell me to message the leader.
