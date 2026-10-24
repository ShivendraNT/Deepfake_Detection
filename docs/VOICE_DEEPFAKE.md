# Voice-clone check — protocol (fixed before any model was scored) and results

> Code: `src/satyapan/voice/` (product), `research/voice/` (benchmark). Results:
> `results/voice_benchmark.md`, `results/voice_selection.json`. Run: `python -m research.run_all voice`.

## 1. Why this exists

Until 24 Oct the product had **no** voice-deepfake model it was allowed to ship: the browser
plug-in model it was designed around (Pascu et al., XLS-R layer 7 + logistic regression) has no
licence file, and the thresholds once committed for it were fitted to simulated scores and
withdrawn (`results/INVALIDATED.md`). A dropped voice note was transcribed and its *asks*
checked, but the voice itself was "not analysed". This benchmark fixes that with licensed
models and licensed data only.

## 2. Data (all public, licences recorded, sha256 in `results/voice_eval_manifest.json`)

| Role | Data | Licence | Used for |
|---|---|---|---|
| `train` | ASVspoof 2019 LA **train** (mirror `Bisher/ASVspoof_2019_LA`), seeded 1,500 bonafide + 1,500 spoof (attacks A01–A06) | ODC-By | training our model only |
| `val` | In-the-Wild (Müller et al., Interspeech 2022; `SpeechAntiSpoofingBenchmarks/InTheWild`), a seeded 30 % of the **speakers**, up to 1,500 clips | CC-BY-SA-4.0 / Apache-2.0 packaging | model selection, gate, thresholds |
| `test_itw` | In-the-Wild, the other 70 % of speakers, seeded 3,000 clips | same | real-world deepfakes of public figures, speakers never used for anything else |
| `test_asv` | ASVspoof 2019 LA **eval** (`SpeechAntiSpoofingBenchmarks/ASVspoof2019_LA`), seeded 2,000 clips; attack labels from the official CM protocol | ODC-By | 13 attacks, 11 of them unseen in training (A07–A19) |

Each clip is scored on its first 5 s window (the product's window), 16 kHz mono. Channel
conditions, applied to every val/test clip: `clean`; `opus16` (libopus 16 kbps: WhatsApp voice
notes, VoIP); `gsm` (GSM 06.10 at 8 kHz: a mobile call). No sox/AMR encoder is available on the
benchmark machine, so GSM stands in for AMR-NB.

## 3. Candidates

| Name | What | Licence | Trained on |
|---|---|---|---|
| `satya_xlsr_l7` (ours) | `facebook/wav2vec2-xls-r-300m` (Apache-2.0), first 7 transformer layers, mean-pooled, standardised, logistic regression — the published Pascu et al. recipe, re-trained by us on licensed data | Apache-2.0 + our head | ASVspoof 2019 LA train (above); C by speaker-grouped 5-fold CV on train |
| `gustking_xlsr` | `Gustking/wav2vec2-large-xlsr-deepfake-audio-classification` | Apache-2.0 | ASVspoof 2019 (per its card) |
| `garystafford_xlsr` | `garystafford/wav2vec2-deepfake-voice-detector` (fine-tuned from the above) | Apache-2.0 | `garystafford/deepfake-audio-detection` (CC-BY-4.0, commercial TTS/cloning services) |
| `melody_w2v2` | `MelodyMachine/Deepfake-audio-detection-V2` | Apache-2.0 | undocumented "audiofolder" (**not eligible** to ship) |
| `ast_asvspoof5` | `MattyB95/AST-ASVspoof5-Synthetic-Voice-Detection` | BSD-3-Clause | ASVspoof5 (per its card) |

## 4. Rules (fixed now)

1. **Gate:** every candidate is scored on a seeded 500-clip subset of `val` (`clean`). Only
   candidates with gate AUC ≥ 0.70 go further: full `val` (all channels) and the test sets under
   `clean` and `opus16`; the shipped model also under `gsm`. *(Amended 24 Oct, before any
   candidate was scored: on this CPU the large models take 2.5–3.3 s per clip, so the full grid
   would not finish in the event.)* *(Amendment 2, 24 Oct 16:55 UTC, after the gate and before
   any `opus16` or test score of any model: measured 4.75 s per clip for the 315 M models with
   the video jobs sharing the CPU, the grid above is ≈ 19 CPU-hours per large model. Now: every
   gate-passer is scored on the full `val` under `opus16` (the selection condition, unchanged);
   the full `val` grid and the test sets are scored for the **shipped** model only. If an
   off-the-shelf model is shipped, its test sets are seeded subsets (1,000 In-the-Wild clips;
   300 bonafide + 30 per attack of ASVspoof eval) under `clean` and `opus16`.
   `research/voice/bench.py::test_subset`.)*
2. **Selection for the product:** eligible = licence allows redistribution + documented training
   data that does not include In-the-Wild. Among eligible gate-passers, an off-the-shelf model
   replaces ours only if its `val` AUC under `opus16` exceeds ours by more than one bootstrap SE
   of the paired difference (speakers resampled). Ties go to ours (smaller, ours to explain).
3. **Thresholds:** τ_hi = 1 % FPR and τ_lo = 5 % FPR on `val` bonafide windows, per condition,
   the highest kept (the same rule as the video check). `calibrated: false` until consented
   Meet audio exists (T18): these are public recordings, not our calls.
4. **What the person sees** (same mapping as the face check): two 5 s windows in a row over
   τ_hi → `VOICE_LIKELY_SYNTHETIC` (+1 band); enough speech (≥ 3 s) and a window over τ_lo →
   `VOICE_SUSPICIOUS` (VERIFY: call back on a number you already have); less speech → "could
   not judge" (no band effect). A short voice note is one window, so the benchmark's
   "spoof @ τ_lo" column is its call-back rate. *(Added 24 Oct, before any test score.)*
5. **Test once:** the test sets never select or tune anything. AUC/EER with 95 % bootstrap over
   speakers (2,000 resamples), rates with Wilson intervals; per-attack AUC on ASVspoof eval.

## 5. Results

Filled from `results/voice_benchmark.md` after the frozen run.
