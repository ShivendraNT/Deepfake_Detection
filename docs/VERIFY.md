# Verifying this repo (about 10 minutes, no model downloads)

What a reviewer can run on a fresh clone, what each step should print, and what is deliberately
not finished. Everything we did not write is listed in [`THIRD_PARTY.md`](../THIRD_PARTY.md).

## 1. Every check

```bash
make sync                    # Python deps via uv (no uv / no make: README "pip fallback")
make check                   # ruff + format + mypy + pytest -> "make check: ALL GREEN"
cd desktop && npm ci && npm run typecheck && npx vitest run && cd ..
make ext-test                # Chrome extension
cd console && npm ci && npm test && cd ..
```

Expected on a fresh clone (25 Oct, Linux x64, Python 3.13, Node 22):

| Suite | Result |
|---|---|
| pytest | 876 passed, 17 skipped |
| desktop vitest + typecheck | 86 passed, no type errors |
| extension (`node --test`) | 11 passed |
| console vitest | 1 passed |

## 2. The 17 skipped tests

Each skip names its task. None of them hides a failure.

| Tests | Why they skip | What would turn them on |
|---|---|---|
| T19 metrics (1) | needs scikit-learn, which is in the `research` extra | `uv sync --extra research`: then 8 of 8 pass |
| T18 audio calibration (1) | needs consented recordings made through Meet; no real voice is ever committed | team recordings under `docs/consent/` |
| T20 (8), T21 (5) | the separate "Ask, Not Style" research track on ICFD-31k. That data is under defensive-research terms and its text never enters this repo; it also needs GPU paraphrase runs | not part of the product |
| T22 dry runs (1) | `results/dry_runs.csv` must be the team's real rehearsal log | written after the rehearsals, never generated |
| T23 deck (1) | `docs/pitch/deck.pdf` | the team's deck |

## 3. The product, with no model downloaded

```bash
make run                     # then open http://127.0.0.1:8000/check
curl -s -X POST localhost:8000/scam-check -H 'content-type: application/json' \
  -d '{"text":"Share the OTP to stop your account block","lang":"en"}'      # -> HOLD
curl -s -X POST localhost:8000/scam-check -H 'content-type: application/json' \
  -d '{"text":"123456 is your OTP. Do not share it with anyone.","lang":"en"}'  # -> PASS
```

The text checks need nothing extra. The face, voice and speech checks need their models; see
`docs/JUDGES.md` §0:
- `make video`: face detectors and OCR;
- GenD: `research/video/export_gend.py`;
- `make voice`;
- `make asr`.

Without a model, the answer rests only on what was checked and lists the rest under "could
**not** check", for example "face (face model not installed)". A missing model never raises an
alarm; a PASS then means "nothing found in what was checked".

## 4. Where each number comes from

Each headline figure in the docs is a row in
[`results/EVIDENCE_LEDGER.md`](../results/EVIDENCE_LEDGER.md), with the script that wrote it.
`python -m research.run_all <suite>` reproduces a suite from the public datasets, which are
pinned by sha256 in `results/*_manifest.json`. Thresholds are fitted
on validation and frozen before the test sets are scored once. Withdrawn numbers are listed in
`results/INVALIDATED.md`.
