# T25 — Desktop Guardian Companion ("Pahredaar / Satya")

> **Goal:** Transform Satyapan from a static web dashboard into an ambient on-screen desktop guardian ("Pahredaar / Satya") with live call audio listening, email/document verification, and Golden Hour automated incident scribing (BSA 2023 Sec 63 + 1930).

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

## Files to create or modify
- `docs/tasks/T25-desktop-companion.md` — keep this task plan and file scope explicit.
- `docs/GRAND_FINALS_ARCHITECTURE.md` — expand threat handling, UX, counter-challenge, and evidence dossier design.
- `docs/STATUS.md` — record completion and a one-line note after checks pass.

## Agent plan
1. Review the existing architecture and T25 acceptance boundary; run the strict task test before implementation.
2. Specify audio quality gates, accent/noise/codec handling, jitter behavior, and a clearly labeled offline demo fallback.
3. Refine the companion state/alert UX into a respectful cognitive pause that cannot manipulate or control external banking UI.
4. Define an OOB counter-challenge using independently trusted channels, one-time transaction-bound challenges, and the existing confirmation flow.
5. Define a verifiable evidence dossier with canonical manifests, chunk hashes, chain/signature fields, time-quality metadata, and a separate 1930 draft artifact.
6. Add adversarial demo scenarios, failure outcomes, and judge-facing limitations; make no legal admissibility or detection guarantees.
7. Run T25 after each documentation step, then `make check` (use `make fmt` only if needed), update STATUS, and commit per the task workflow.

BLOCKED (21 Oct 2026, opencode-go / GPT-6 Luna): T25 acceptance passes, but three full-check/format attempts stop at Ruff findings in the out-of-scope `src/satyapan/report/pack.py`. Tried `make check` (391 findings), `make fmt` (6 auto-fixes; 365 findings remain), and `make check` again (391 findings after restoring the formatter's unrelated edits). Exact final error: `Found 391 errors` / `make: *** [lint] Error 1`; findings are primarily E501 lines over 100 characters, plus F541 at `src/satyapan/report/pack.py:643`. Best guess: the current report-pack HTML strings need a separate, authorized cleanup; changing that file is outside T25's listed file scope. Files touched: `docs/tasks/T25-desktop-companion.md`, `docs/GRAND_FINALS_ARCHITECTURE.md`, `docs/STATUS.md`.
