# Invalidated results

Results listed here were removed from `results/` because they were not measured on real data.
Git history keeps the files. Do not quote them anywhere (deck, PDF, README, chat).

## 2026-10-07: voice detector channel evaluation (T18)

| What | Where it was | Status |
|---|---|---|
| EER per channel (clean 4%, Opus 0%, AMR-NB 4%, G.711 2%; n=100, 10 speakers) | `results/audio_eval.csv` (commit f83e3b7) | **Removed. Not a measurement.** |
| `tau_hi=0.5926`, `tau_lo=0.4899`, `calibrated: true`, `calibration_set_sha256` | `config/voice_thresholds.json` (commit f83e3b7) | **Reverted** to the uncalibrated placeholder (0.9 / 0.6, `calibrated: false`), which matches `extension/lib/thresholds.js`. |

**Why.** The script that produced them (`research/audio/run_audio_eval.py` at f83e3b7) did not
load audio, did not run the voice model and did not re-encode anything. It drew "bonafide" and
"spoof" scores from `random.gauss(...)` for 20 invented speaker IDs and fitted thresholds on
those random numbers. The note in the thresholds file ("Calibrated on Meet-captured bonafide
windows") and the `calibration_set_sha256` (a hash of the random numbers) therefore described
something that did not happen. The acceptance test only checked CSV columns and
`calibrated is True`, so it passed.

**What changed so this cannot pass again.**
- `research/audio/run_audio_eval.py` now refuses to run without a data manifest of real audio
  files (`results/audio_eval_manifest.json`: dataset name, model version, sha256 of every file)
  and verifies every hash on disk before it writes anything.
- `tests/tasks/test_t18_audio_eval.py` requires that manifest and checks that the thresholds'
  `calibration_set_sha256` is recomputable from the manifest's calibration files.
- `tests/harness/test_results_provenance.py`: no script under `research/` or `scripts/` that
  writes into `results/` (or anything it imports from `research/`) may use `random` /
  `numpy.random`, except lines explicitly allow-listed for seeded resampling (bootstrap CIs,
  speaker splits) with the comment `# provenance: seeded-resampling-ok`.
- T18 is back to `todo` in `docs/STATUS.md`.

**Current honest status of the voice detector:** no measured number exists yet. The PDF should
cite the model authors' published figure as *external* and mark our own channel/Meet numbers
as *pending* (see `results/EVIDENCE_LEDGER.md`).
