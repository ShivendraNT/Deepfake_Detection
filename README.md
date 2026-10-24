# Satyapan (सत्यापन) — Payment Verification Desk

**Deepfake detection for financial communications, anchored on the payment.**
Amazon hackathon project · team of 4 · Delhi Technological University.

Indian SME finance teams receive payment requests by email, WhatsApp and video calls. A deepfake
"CFO" on Google Meet, a compromised vendor mailbox, or an edited invoice can redirect lakhs in
minutes. Detectors alone are not enough (on 2026's newest fakes the best video detector scores
69.7% AUROC, and 34.5% on commercial generators). So:

- **The payment sets the floor, not the message.** We compare the pending payment with the
  company's own vendor master (new beneficiary? changed bank details? unusual amount?) and set a
  minimum band: PASS / VERIFY / HOLD.
- **Evidence can only raise the band.** Email authentication, invoice-vs-master checks, a
  deterministic "ask" detector (OTP, secrecy, new account… in English and Hinglish) and an
  on-device voice-deepfake detector in a Chrome side panel for Meet/Teams. No LLM can lower it.
- **Detectors decide who verifies.** A deepfake signal moves verification from the possibly
  manipulated maker to the checker. **OOB-Confirm** asks the real CFO "did you ask for this?"
  through their own login.
- **Actionable path.** A UTR-first draft for the 1930 helpline, the NCRP portal and the bank's
  fraud desk. A human always submits it.

Research core: *"Ask, Not Style"* — are Hinglish fraud-conversation detectors robust to LLM
paraphrase, and do detectors that look only at the attacker's unavoidable *ask* hold up?
See `docs/RESEARCH_PROTOCOL.md`.

## 60-second quickstart (macOS, Apple Silicon)

```bash
# 1. tools (once)
brew install uv ffmpeg node
# 2. install and verify
make sync          # creates .venv with core + dev dependencies
make check         # lint + types + tests -> must end with "ALL GREEN"
# 3. run the API with 12 demo cases
make run           # open http://127.0.0.1:8000/docs  -> try GET /cases
```

**pip fallback (no uv):**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest hypothesis httpx ruff mypy numpy
make check RUN=
```

## Repo map

| Path | What |
|---|---|
| `AGENTS.md` | **rules for every AI agent and human** (single source of truth) |
| `docs/tasks/` | T-task specs (`T01` … `T25`), mostly done |
| `docs/STATUS.md` | task board: owner, status, dependencies |
| `docs/ARCHITECTURE.md` | design: components, policy tables, API, AWS mapping, failure modes |
| `docs/THREAT_MODEL.md`, `docs/DATA_POLICY.md` | security + privacy/ethics |
| `docs/RESEARCH_PROTOCOL.md`, `docs/EVALUATION.md` | paper protocol + honest product numbers |
| `docs/finale/` | finale plan + mascot spec (demo script in `PLAN.md` §7) |
| `docs/DEMO_SCRIPT.md` | the Round-1 demo (superseded by `docs/finale/PLAN.md` §7) |
| `team/` | each person's finale cards |
| `desktop/` | Electron app: Satya the companion |
| `src/satyapan/` | Python backend (contracts, policy engine, detectors, API) |
| `extension/` | Chrome MV3 extension (tab audio → on-device voice score, side panel) |
| `console/` | React web console |
| `research/` | research scripts (metrics, baselines, attacks, evaluation) |
| `tests/` | contracts, safety invariants, harness checks, per-task acceptance tests |
| `data/demo/` | synthetic, obviously fake fixtures (vendors, emails, invoices, 12 cases) |
| `schemas/` | JSON Schemas exported from the contracts |

## Grand finale (IIT Delhi, 24–25 Oct 2026)

We are turning Satyapan into **Satya**, a small desktop companion that sits on the clerk's screen.
Read in this order:

1. `docs/GRAND_FINALS_ARCHITECTURE.md` — what we build and why (single source of truth).
2. `docs/finale/PLAN.md` — 48-hour plan, checkpoints, demo script, risks, Q&A.
3. `team/<YourName>.md` — your cards (F01–F16) with steps, checks and a ready prompt.
4. `docs/finale/MASCOT_SPEC.md` — Satya's drawing, poses, motion and copy.

Desktop quickstart: `cd desktop && npm install && npm run dev:web` (browser + mock, port 5174)
or `npm run dev` (Electron). Backend: `make run`.

## What is already built

T01 (contracts, fixtures, mock API), T02 (policy engine + property tests), the vault's hash
chain, the voice window rules (Python + JS), the LLM prompt isolation, and the evidence pipeline
are implemented and tested. Everything else is a precise stub with an acceptance test.

## License

MIT for this code (`LICENSE`). Third-party models and datasets keep their own terms — see
`docs/DATA_POLICY.md`.
