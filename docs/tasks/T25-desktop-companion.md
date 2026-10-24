# T25 — Desktop Guardian Companion ("Pahredaar / Satya")

> **Goal:** Transform Satyapan from a static web dashboard into an ambient on-screen desktop guardian ("Pahredaar / Satya") with live call audio listening, email/document verification, and Golden Hour automated incident scribing (BSA 2023 Sec 63 + 1930).

> **Finale redesign (22 Oct):** the backend below stays. The desktop shell is being rebuilt as
> mascot-only + bubble + Notebook — see `docs/GRAND_FINALS_ARCHITECTURE.md` (v2),
> `docs/finale/PLAN.md` and the F-cards in `team/<Name>.md`. Section 2 ownership is replaced by
> PLAN §3.

---

## 1. Owner & Scope
* **Owner:** Shivendra (with Saarika, Saksham, Kartikey)
* **Effort:** Hackathon Grand Finals module
* **Specification:** `docs/GRAND_FINALS_ARCHITECTURE.md`

---

## 2. Team Ownership & Folder Boundaries
* **Shivendra:** `desktop/main/**`, `desktop/preload/**`, `src/satyapan/api/companion/**`
* **Saarika:** `desktop/renderer/src/companion/**`, `desktop/renderer/src/assets/**`
* **Saksham:** `desktop/renderer/src/workspace/**`
* **Kartikey:** `desktop/capture/**`, `src/satyapan/report/**`

---

## 3. Mock Interfaces to Establish First
1. `CompanionApiClient` — mock SSE event stream and case fixtures for UI testing without backend.
2. `CaptureSource` — fake capture adapter emitting PCM chunks before OS loopback wiring.
3. `ReportDraftClient` — fake draft responses for Scribe and review UI.

---

## 4. Safety Gates & Repo Invariants
* The UI **never sets or lowers a policy band**. Only `src/satyapan/policy/` sets the band.
* No raw scores are exposed to the user (mitigates oracle abuse). Only reason codes and explanations are shown.
* The app must launch into **Sleep / DND** by default. Monitoring is strictly opt-in and visibly active.
* Never auto-submit reports to police, 1930, or banks. All reports are human-reviewed drafts (`MANUAL_ONLY`).

---

## 5. Acceptance Test
```bash
make task T=T25
```

## 6. Companion API (implemented)

The local FastAPI engine exposes a versioned companion contract under `/companion`:

* `GET /companion/health` — liveness, policy authority, `MANUAL_ONLY` flag.
* `GET /companion/state` — consented mode/source snapshot (never raw scores).
* `GET /companion/events` — SSE stream (`Last-Event-ID` replay, `?replay_only=true`).
* `POST /companion/session/start` / `POST /companion/session/stop` — explicit consent lifecycle.
* `POST /companion/commands` — typed command router (`demo.replay`, `session.sleep`, `ui.hide`, `ui.disable`).
* `POST /companion/submit-evidence` — consented text intake; deterministic asks only, no band set.
* `POST /companion/drafts` — Section 63 / helpline-1930 drafts, always `MANUAL_ONLY`.
* `GET /companion/workspace` — case snapshot for the details window.

The HTTP layer never accepts a `band`, `score`, `confidence` or `probability` field. The demo
scenario calls `satyapan.policy.engine.decide()` and only relays its `Decision`.

## 7. Files to create or modify
- `docs/tasks/T25-desktop-companion.md` — keep this task plan and file scope explicit.
- `docs/GRAND_FINALS_ARCHITECTURE.md` — existing master design.
- `docs/STATUS.md` — record completion and a one-line note after checks pass.
- `src/satyapan/api/companion/**` — event bus, contracts, service, SSE/command router.
- `src/satyapan/api/app.py` — mount the companion router.
- `tests/tasks/test_t25_companion.py` — backend, safety and desktop-integrity tests.
- `desktop/**` — Electron + React + TypeScript + Tailwind + Framer Motion companion app.

## 8. Agent plan
1. Read the frozen contracts/policy APIs; keep companion band output as a relay of `Decision`, never a computation.
2. Build `api/companion/models.py` (versioned envelopes, mode/mood enums, draft models) and `bus.py` (bounded replay, subscriber queues, monotonic ids).
3. Build `service.py` (Sleep/DND default, consent session lifecycle, fail-closed hide, policy scenario, evidence intake, drafts, workspace snapshot, audit).
4. Build `router.py` with SSE (`Last-Event-ID`, replay-only, keep-alive), session and command endpoints; mount in `create_app`.
5. Expand `tests/tasks/test_t25_companion.py`: contract validation, consent, fail-closed, raise-only/band authority, no raw scores, replay, drafts `MANUAL_ONLY`, workspace masking, desktop security/static checks.
6. Scaffold `desktop/` (electron-vite, React, Tailwind, Framer Motion): frameless transparent always-on-top window, tray, global shortcuts, typed preload bridge, backend SSE proxy, clipboard check.
7. Build the Satya renderer: animated mascot moods, speech/alert/consent cards, chimes, replay badge, workspace view, mock clients + fake capture for offline demo.
8. `npm install && npm run typecheck && npm run build`, then `make check`, update STATUS and commit.

## 9. Resolution of the previous block
The earlier `make check` block came from Ruff findings in `src/satyapan/report/pack.py`; `pyproject.toml` now carries the authorised `E501` per-file ignore and its `F541` line is fixed. Baseline `make check` is green before this implementation.
