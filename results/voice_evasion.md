# Voice evasion attempts (research/voice/evasion.py)

In-the-Wild test clips with >= 3 s of speech (160 bonafide, 155 spoof), the product's scorer `gustking_xlsr@f7050b5`, frozen tau_lo 0.773. Flagged = VERIFY or above for a one-window voice note.

| Edit | AUC [95% CI] | change vs as recorded (paired) | fakes flagged | genuine flagged |
|---|---|---|---|---|
| as recorded | 0.952 [0.910, 0.980] | – | 63.9% [56.1, 71.0] | 0.6% [0.1, 3.5] |
| + white noise, 10 dB SNR | 0.843 [0.750, 0.910] | -0.110 [-0.177, -0.059] | 1.9% [0.7, 5.5] | 0.0% [0.0, 2.3] |
| 10 % faster (pitch kept) | 0.948 [0.906, 0.977] | -0.004 [-0.012, +0.002] | 63.9% [56.1, 71.0] | 0.6% [0.1, 3.5] |
| 2 semitones up (duration kept) | 0.946 [0.885, 0.984] | -0.007 [-0.036, +0.012] | 76.8% [69.5, 82.7] | 0.6% [0.1, 3.5] |
