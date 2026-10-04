# Copilot instructions (short version — the full rules are in AGENTS.md at the repo root)

Read `AGENTS.md` first. Then read only the task spec you are working on (`docs/tasks/TNN-*.md`)
and the files it lists.

Key rules:
- Only `src/satyapan/policy/` sets the risk band. Signals only RAISE the band. LLM/style ≤ VERIFY.
- Build signals with `Signal.make(code, source=..., evidence_ids=[...])`.
- Network code only in `src/satyapan/adapters/`. Tests never use the network.
- No auto-reporting; no invented 1930/NCRP APIs; reports are drafts.
- Callback numbers only from the vendor master / directory.
- Never edit `src/satyapan/contracts/`, `src/satyapan/policy/`, `tests/invariants/`,
  `tests/harness/`, `tests/conftest.py` without the leader.
- Never weaken or delete a test. Never paste real media, bank details or secrets.
- Verify with `make task T=TNN` then `make check`. Commit as `TNN: <summary>`.
