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

Unfinished tasks show up as **SKIPPED** tests and their endpoints return **HTTP 501** with the task
id. That is expected.

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
| `docs/tasks/` | 24 task specs (`T01` … `T24`) — start here when you work |
| `docs/STATUS.md` | task board: owner, status, dependencies |
| `docs/ARCHITECTURE.md` | design: components, policy tables, API, AWS mapping, failure modes |
| `docs/THREAT_MODEL.md`, `docs/DATA_POLICY.md` | security + privacy/ethics |
| `docs/RESEARCH_PROTOCOL.md`, `docs/EVALUATION.md` | paper protocol + honest product numbers |
| `docs/DEMO_SCRIPT.md` | the 2:45 demo |
| `docs/harness/` | agent workflow + copy-paste prompts |
| `src/satyapan/` | Python backend (contracts, policy engine, detectors, API) |
| `extension/` | Chrome MV3 extension (tab audio → on-device voice score, side panel) |
| `console/` | React web console |
| `research/` | research scripts (metrics, baselines, attacks, evaluation) |
| `tests/` | contracts, safety invariants, harness checks, per-task acceptance tests |
| `data/demo/` | synthetic, obviously fake fixtures (vendors, emails, invoices, 12 cases) |
| `schemas/` | JSON Schemas exported from the contracts |

## Start working with your AI agent in 5 steps

1. **Pick your task** in `docs/STATUS.md` (your initials in the Owner column, dependencies `done`).
   `git switch -c t05-ask-extractor`.
2. **Open your tool in the repo root.** opencode: `opencode` (it loads `AGENTS.md` and
   `opencode.json` automatically; choose a model with `/models`). Gemini CLI: `gemini`.
   Copilot: VS Code agent mode. Claude Code: `claude`.
3. **Start the task:** opencode `/task T05` · Gemini `/task T05` · Copilot: paste the prompt from
   `docs/harness/PROMPTS.md` §1.
4. **Let it go step by step.** After each step it runs `make task T=T05`. Red → green.
   Stuck 3 times on the same error? `/stuck T05` and tell the leader.
5. **Finish:** `make check` green → update `docs/STATUS.md` → commit `T05: ...` → PR →
   `/review` (opencode) for an automatic review.

Free model IDs change often: in opencode run `/models` and pick an `opencode/<id>` free model.
Never paste real voices, bank details, dataset text or `.env` into any AI tool.

## What is already built

T01 (contracts, fixtures, mock API), T02 (policy engine + property tests), the vault's hash
chain, the voice window rules (Python + JS), the LLM prompt isolation, and the evidence pipeline
are implemented and tested. Everything else is a precise stub with an acceptance test.

## License

MIT for this code (`LICENSE`). Third-party models and datasets keep their own terms — see
`docs/DATA_POLICY.md`.
