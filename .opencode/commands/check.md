---
description: Run the full verification (lint, format, types, tests) and explain any failure
agent: implementer
---
Here is the output of `make check`:

!`make check 2>&1 | tail -60`

If it ends with "ALL GREEN", say so in one line and stop.
Otherwise: list each failure (file:line, one-sentence cause). For lint/format problems suggest
`make fmt`. For test failures, propose the smallest fix in SOURCE code (never in tests).
Do not edit anything until I confirm.
