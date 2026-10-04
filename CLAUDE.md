@AGENTS.md

# Leader-only notes (Claude Code)

- You own the critical path: T01 → T02 → T07 → T11 → T12 → T22, plus T15, T20, T21.
  T01, T02 and the vault core are already implemented — protect them.
- You are the only one who may change `src/satyapan/contracts/`, `src/satyapan/policy/`,
  `tests/invariants/`, `tests/harness/`, `tests/conftest.py`. After any contract change run
  `make schemas` and update `console/src/types.ts` in the same commit.
- Review rule (from critique flaw 24): review by acceptance test. Read diffs line-by-line only for
  policy, vault and extension capture code. Use `/review-pr` (or the `reviewer` subagent).
- New or changed task? Use `/new-task` (or the `spec-writer` subagent) so the spec, the test file
  and STATUS.md stay consistent. `tests/harness/test_task_specs.py` checks this.
- Research hygiene: never put ICFD text or paraphrases in the repo or in free-model prompts.
  Thresholds are fitted on validation only; tag `lexicon-v1.0` before touching ICFD test.
