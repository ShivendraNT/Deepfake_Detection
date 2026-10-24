# Voice-clone benchmark (research/voice/bench.py)

Protocol fixed before scoring: docs/VOICE_DEEPFAKE.md. Clips = first 5 s, 16 kHz. AUC/EER: 95% bootstrap over speakers; rates: Wilson 95%. In-the-Wild val and test speakers are disjoint; ASVspoof eval attacks A07-A19 (A16 = A04 and A19 = A06 were seen in training).

Our model (XLS-R layer 7 + LR on ASVspoof 2019 LA train): C = 10.0, speaker-grouped CV AUC 1.0 ± 0.0001.

## Gate (val, clean; >= 0.70 to be tested)

| Model | Licence | Trained on | val AUC |
|---|---|---|---|
| satya_xlsr_l7 | Apache-2.0 (backbone) + our LR head | ASVspoof 2019 LA train, 3,000 clips (ours) | 0.847 [0.773, 0.946] |
| gustking_xlsr | Apache-2.0 | ASVspoof 2019 (per its card) | 0.964 [0.904, 0.993] |
| garystafford_xlsr | Apache-2.0 | garystafford/deepfake-audio-detection (CC-BY-4.0; TTS / cloning services) | 0.467 [0.325, 0.759] |
| melody_w2v2 | Apache-2.0 | undocumented 'audiofolder' | 0.501 [0.223, 0.661] |
| ast_asvspoof5 | BSD-3-Clause | ASVspoof5 (per its card) | 0.378 [0.246, 0.687] |

## Selection (val, replace ours only if val AUC (opus16) gain > 1 bootstrap SE)

Decision: **gustking_xlsr**. Thresholds (logit): tau_hi 2.233, tau_lo 1.224 (1% / 5% FPR on val bonafide, max over conditions).
- gustking_xlsr − ours: +0.157 (SE 0.054)

## satya_xlsr_l7

| Set / channel | n bonafide / spoof | AUC | EER | spoof caught @ tau_hi | bonafide flagged @ tau_hi | spoof @ tau_lo | bonafide @ tau_lo |
|---|---|---|---|---|---|---|---|
| val/opus16 | 778 / 679 | 0.791 [0.706, 0.904] | 0.281 [0.181, 0.365] | – | – | – | – |

## gustking_xlsr (shipped)

| Set / channel | n bonafide / spoof | AUC | EER | spoof caught @ tau_hi | bonafide flagged @ tau_hi | spoof @ tau_lo | bonafide @ tau_lo |
|---|---|---|---|---|---|---|---|
| val/clean | 778 / 679 | 0.957 [0.893, 0.990] | 0.085 [0.043, 0.203] | 20.9% [18.0, 24.1] | 0.3% [0.1, 0.9] | 54.3% [50.6, 58.1] | 2.7% [1.8, 4.1] |
| val/opus16 | 778 / 679 | 0.949 [0.892, 0.982] | 0.098 [0.062, 0.199] | 28.1% [24.9, 31.6] | 0.6% [0.3, 1.5] | 60.2% [56.5, 63.8] | 3.5% [2.4, 5.0] |
| val/gsm | 778 / 679 | 0.959 [0.902, 0.989] | 0.090 [0.046, 0.180] | 32.8% [29.4, 36.5] | 0.9% [0.4, 1.8] | 77.8% [74.5, 80.7] | 4.9% [3.6, 6.6] |
| test_itw/clean | 669 / 331 | 0.921 [0.868, 0.957] | 0.160 [0.105, 0.213] | 26.0% [21.6, 31.0] | 0.1% [0.0, 0.8] | 53.5% [48.1, 58.8] | 1.6% [0.9, 2.9] |
| test_itw/clean (>= 3 s speech) | 160 / 155 | 0.952 [0.910, 0.980] | 0.110 [0.058, 0.168] | 34.8% [27.8, 42.6] | 0.0% [0.0, 2.3] | 63.9% [56.1, 71.0] | 0.6% [0.1, 3.5] |
| test_itw/opus16 | 669 / 331 | 0.909 [0.857, 0.948] | 0.169 [0.114, 0.221] | 34.4% [29.5, 39.7] | 0.1% [0.0, 0.8] | 58.3% [52.9, 63.5] | 1.8% [1.0, 3.1] |
| test_itw/opus16 (>= 3 s speech) | 160 / 155 | 0.947 [0.903, 0.978] | 0.119 [0.057, 0.171] | 45.8% [38.2, 53.7] | 0.0% [0.0, 2.3] | 66.5% [58.7, 73.4] | 0.6% [0.1, 3.5] |
| test_asv/clean | 300 / 390 | 0.999 [0.997, 1.000] | 0.003 [0.000, 0.011] | 62.8% [57.9, 67.5] | 0.0% [0.0, 1.3] | 86.2% [82.4, 89.2] | 0.3% [0.1, 1.9] |
| test_asv/clean (>= 3 s speech) | 5 / 83 | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 79.5% [69.6, 86.8] | 0.0% [0.0, 43.5] | 91.6% [83.6, 95.9] | 0.0% [0.0, 43.5] |
| test_asv/opus16 | 300 / 390 | 0.999 [0.997, 1.000] | 0.003 [0.000, 0.011] | 70.8% [66.1, 75.1] | 0.0% [0.0, 1.3] | 90.3% [86.9, 92.8] | 0.3% [0.1, 1.9] |
| test_asv/opus16 (>= 3 s speech) | 5 / 83 | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 90.4% [82.1, 95.0] | 0.0% [0.0, 43.5] | 95.2% [88.2, 98.1] | 0.0% [0.0, 43.5] |

ASVspoof 2019 eval, AUC per attack (vs all bonafide): A07 1.000, A08 1.000, A09 1.000, A10 0.998, A11 1.000, A12 1.000, A13 1.000, A14 1.000, A15 1.000, A16 0.998, A17 0.999, A18 1.000, A19 0.997
