# Denoiser probe on VALIDATION clips (research/voice/denoise_probe.py)

In-the-Wild val, >= 3 s speech (366 bonafide, 197 spoof); scorer `gustking_xlsr@f7050b5`; denoiser `afftdn=nf=-25`; noise = white, 10 dB SNR. The test set is not used. Fakes over tau_lo use the current thresholds, which were fitted without a denoiser.

| Version | AUC [95% CI] | fakes over current tau_lo |
|---|---|---|
| clean | 0.982 [0.943, 0.999] | 71.6% |
| clean+dn | 0.959 [0.920, 0.997] | 43.7% |
| noisy | 0.871 [0.815, 0.951] | 5.1% |
| noisy+dn | 0.861 [0.766, 0.961] | 1.5% |

Denoiser on noisy clips: AUC -0.010 [-0.059, +0.038]; on clean clips: -0.023 [-0.035, -0.002].
