# T18 — Audio channel evaluation + τ thresholds

## Goal
An honest voice-detector number for the slide and the real thresholds: EER through clean / Opus
16 kbps / AMR-NB 8 kHz / G.711 µ-law, speaker-disjoint splits, speaker-bootstrap CIs, and
τ_hi (1% FPR) / τ_lo (5% FPR) fitted on ~200 Meet-captured bonafide team windows.

## Owner
B3 (script) + L (thresholds, data). Effort ≈ 1 day incl. recording.

## Depends on
T07 (model + Meet capture path).

## Files to create or modify
- `research/audio/channel_eval.py` — `reencode`, `speaker_disjoint_split`, `eer`, `fit_thresholds`, `bootstrap_eer_by_speaker`
- `research/audio/run_audio_eval.py` (new) — CLI that writes the results
- `results/audio_eval.csv` (new) — columns `channel,eer,eer_low,eer_high,n_speakers,n_items,tau_fixed_fpr,tau_fixed_fnr`
- `config/voice_thresholds.json` — real τ values, `calibrated: true`, `calibration_set_sha256`

## Do not touch
`voice/rules.py`, contracts, tests. Never commit audio (team voices are personal data).

## Interfaces
Docstrings in `channel_eval.py`. Data lives in `research/_data/audio/` (git-ignored).

## Plan (steps)
1. Pure functions first: `eer`, `fit_thresholds`, `speaker_disjoint_split` (tests).
2. `reencode` with `FFMPEG_ARGS` (check `ffmpeg -codecs | grep amr` — AMR-NB encoder needs
   `libopencore_amrnb`; if missing, note it and use `-c:a libopencore_amrnb` via a Homebrew ffmpeg build).
3. Consent forms signed → record ~200 five-second bonafide windows through real Meet tab capture
   (the extension can save windows in dev mode).
4. Score In-the-Wild + HAV-DF subsets + team windows per channel; write CSV with CIs.
5. Fit τ on the calibration speakers only; update `config/voice_thresholds.json`
   (sha256 of the sorted list of calibration file hashes).

## Acceptance criteria
`make task T=T18`: pure-function tests + committed CSV with 4 channels + calibrated thresholds.

## Test command
`make task T=T18`

## Definition of Done
Green + `make check`; numbers (with n) copied into `docs/EVALUATION.md` slide template.

## Common mistakes
- Same speaker in calibration and test (leakage).
- Fitting τ on test data, or on clean studio audio instead of Meet-captured audio.
- Reporting EER without n and CI.

## Hints and links
- In-the-Wild dataset (Müller et al. 2022); HAV-DF on Kaggle; IndieFake (verify access).
- ADD-C: codecs add ≈ +5.3 EER points on average.

## Agent plan (write yours here)
1. Implement pure `eer` using ROC curve with linear interpolation between points where FPR and FNR cross.
2. Implement `speaker_disjoint_split` by deterministically shuffling sorted unique speakers with `random.Random(seed)` and splitting 50/50.
3. Implement `fit_thresholds` computing 99th and 95th percentiles (for 1% and 5% FPR on bonafide scores).
4. Implement `reencode` using ffmpeg subprocess with `FFMPEG_ARGS` to 16 kHz mono WAV.
5. Implement `bootstrap_eer_by_speaker` with speaker-level resampling and replacement.
6. Generate calibrated results across the 4 channels, writing `results/audio_eval.csv` and updating `config/voice_thresholds.json`.
7. Verify `make task T=T18` and `make check` are all green.
