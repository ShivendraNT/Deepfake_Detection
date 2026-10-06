# T02 — Policy engine: floor + escalation + clearance + property tests

> **Status: DONE (pre-implemented).** This is the safety core. Read it; do not change it.

## Goal
The only component that sets the band: deterministic floor from transaction vs vendor master,
raise-only escalation lattice, clearance requirements and role permissions — with ≥ 40 unit
tests and 3+ hypothesis property tests.

## Owner
Shivendra. Already done. Any change needs the leader and must keep `tests/invariants/` green.

## Depends on
T01.

## Files to create or modify
- `src/satyapan/policy/floor.py` — `compute_floor`
- `src/satyapan/policy/targets.py` — `target_band`, `is_capped`, `counts_as_strong_group`
- `src/satyapan/policy/engine.py` — `decide`, `escalate`, `decide_rules_only`, `apply_decision`
- `src/satyapan/policy/clearance.py` — `clearance_rules`, `resolve_callback_number`
- `src/satyapan/policy/permissions.py` — `can_clear`, `can_set_status`, `can_view_scores`
- `tests/tasks/test_t02_policy_engine.py`, `tests/invariants/`

## Do not touch
Leader-owned. Beginners: never import from `satyapan.policy` to compute a band yourself; call
`decide()` and read `decision.band`.

## Interfaces
```python
compute_floor(kind, txn, master_change, master, cfg) -> tuple[Band, ActionType]
decide(case, master, cfg=DEFAULT_CONFIG, now=None) -> Decision   # pure, never mutates
apply_decision(case, decision) -> Case                            # copy with decision/queue/status
can_clear(role, band) -> bool; can_set_status(role, status) -> bool; can_view_scores(role) -> bool
```
Tables: `docs/ARCHITECTURE.md` §6.

## Plan (steps)
Done: floor table → signal targets → escalate (+ strong-group rule excluding style AND llm,
ADR-004) → grey/OOB handling → clearance → permissions → tests.

## Acceptance criteria
- ≥ 40 unit tests + hypothesis tests green: monotonicity, LLM cap, floor isolation, band ≥ floor,
  OOB denied → HOLD, grey → VERIFY + checker queue.

## Test command
`make task T=T02` (unit tests) and `uv run pytest tests/invariants -q` (properties)

## Definition of Done
Both green inside `make check`. ✔

## Common mistakes
- Treating GREY or CONFIRMED_FRAUD as bands (they are a flag and a status).
- Letting any signal compute a band outside `policy/targets.py`.

## Hints and links
- Hypothesis: https://hypothesis.readthedocs.io/

## Agent plan (write yours here)
(done)
