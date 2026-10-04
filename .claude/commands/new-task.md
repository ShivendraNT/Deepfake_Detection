---
description: Create or update a task spec + stubs + acceptance tests + STATUS row consistently
argument-hint: "[TNN] [short title]"
---
Use the `spec-writer` subagent to create or update task $ARGUMENTS.
Afterwards run `uv run pytest tests/harness -q` and `make check`, and show me the new spec's
"Files to create or modify" and "Test command" sections.
