# Still-image face check: GenD on one face crop (research/video/image_eval.py)

Thresholds (logit) frozen on val real crops: tau_hi 4.6858 (1% FPR), tau_lo 3.7513 (5%). One crop = one photo. AUC: identity-cluster bootstrap 95% CI; rates: Wilson 95%.

| Set / channel | real / fake crops | AUC | fakes flagged @ tau_hi | reals flagged @ tau_hi | fakes @ tau_lo | reals @ tau_lo |
|---|---|---|---|---|---|---|
| ffpp_test/orig | 560 / 2800 | 0.923 [0.909, 0.936] | 22.7% [21.2, 24.3] | 0.4% [0.1, 1.3] | 54.4% [52.5, 56.2] | 1.1% [0.5, 2.3] |
| dfdc/orig | 1693 / 995 | 0.747 [0.714, 0.779] | 3.8% [2.8, 5.2] | 0.0% [0.0, 0.2] | 14.9% [12.8, 17.2] | 0.9% [0.5, 1.5] |
| ffpp_test/call360 | 560 / 2800 | 0.797 [0.777, 0.817] | 13.1% [11.9, 14.4] | 0.5% [0.2, 1.6] | 35.7% [34.0, 37.5] | 4.6% [3.2, 6.7] |
| dfdc/call360 | 1680 / 975 | 0.621 [0.592, 0.649] | 4.0% [2.9, 5.4] | 1.6% [1.1, 2.3] | 15.8% [13.6, 18.2] | 8.2% [7.0, 9.6] |

ffpp_test/orig AUC per method: Deepfakes 0.984, Face2Face 0.966, FaceShifter 0.792, FaceSwap 0.971, NeuralTextures 0.902

ffpp_test/call360 AUC per method: Deepfakes 0.914, Face2Face 0.819, FaceShifter 0.678, FaceSwap 0.886, NeuralTextures 0.690
