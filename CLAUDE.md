@AGENTS.md

# Leader-only notes (Claude Code)

- Finale: you own F01–F05 (`team/Shivendra.md`): contracts, window manager, backend glue,
  X1 signal, integration and the demo. Protect the built core (contracts, policy, vault).
- You are the only one who may change `src/satyapan/contracts/`, `src/satyapan/policy/`,
  `tests/invariants/`, `tests/harness/`, `tests/conftest.py`. After any contract change run
  `make schemas` and update `console/src/types.ts` in the same commit.
- Review rule (from critique flaw 24): review by acceptance test. Read diffs line-by-line only for
  policy, vault and extension capture code. Use `/review-pr` (or the `reviewer` subagent).
- New or changed task? Use `/new-task` (or the `spec-writer` subagent) so the spec, the test file
  and STATUS.md stay consistent. `tests/harness/test_task_specs.py` checks this.
- Research hygiene: never put ICFD text or paraphrases in the repo or in free-model prompts.
  Thresholds are fitted on validation only; tag `lexicon-v1.0` before touching ICFD test.
