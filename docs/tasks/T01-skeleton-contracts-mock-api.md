# T01 — Skeleton, contracts, fixtures, mock API

> **Status: DONE (pre-implemented).** Read this to understand what already exists.

## Goal
A runnable repo where every shared data contract exists for real (Pydantic v2), 12 fixture cases
load from `data/demo/`, and `GET /cases` returns them with decisions from the real policy engine.
Everyone else builds against these contracts and this API.

## Owner
Shivendra. Already done.

## Depends on
Nothing.

## Files to create or modify
- `src/satyapan/contracts/` — all shared models, enums, `SIGNAL_TABLE`
- `src/satyapan/master/store.py` — vendor master / history / directory loader
- `src/satyapan/repository.py`, `src/satyapan/pipeline.py`, `src/satyapan/settings.py`
- `src/satyapan/adapters/base.py` — interfaces + fakes (FakeTranscriber, FakeLLM, InAppMailer)
- `src/satyapan/api/` — FastAPI app, demo auth headers, role-based views, all route glue
- `scripts/make_demo_data.py`, `scripts/export_schemas.py`, `scripts/decision_relevance.py`
- `data/demo/` — generated fixtures; `schemas/` — exported JSON Schemas

## Do not touch
Everything above is leader-owned. Changing a contract needs leader approval + `make schemas`.

## Interfaces
- `from satyapan.contracts import Case, PaymentAction, Signal, Decision, ...`
- `load_master(Path("data/demo")) -> MasterData`
- `CaseRepository.from_fixtures(master, Path("data/demo/cases"))`
- `GET /cases` → `[{"id": "case_s01", "band": "PASS", "action_type": "K1", ...}, ...]`
- Unfinished task endpoints → HTTP 501 `{"detail": "not implemented yet", "task": "T16"}`

## Plan (steps)
1. Contracts + signal table. 2. Master loader. 3. Policy engine (T02). 4. Fixture generator.
5. Repository + API. 6. Tests (contracts, invariants, harness, tasks).

## Acceptance criteria
- `pytest -q` runs; contract, invariant and harness tests pass.
- `GET /cases` returns 12 fixture cases with real decisions.

## Test command
`make task T=T01`

## Definition of Done
`make task T=T01` and `make check` green. ✔

## Common mistakes
- Editing fixtures by hand instead of changing `scripts/make_demo_data.py` and running `make demo-data`.
- Changing a contract without re-exporting `schemas/` and updating `console/src/types.ts`.

## Hints and links
- Pydantic v2 docs: https://docs.pydantic.dev/latest/
- FastAPI: https://fastapi.tiangolo.com/

## Agent plan (write yours here)
(done)
