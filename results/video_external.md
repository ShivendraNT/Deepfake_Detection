# Off-the-shelf detectors vs ours, matched protocol (research/video/hf_baselines.py)

Same stored face crops (K = 4 per 9.2 s clip), same videos, identity-cluster bootstrap 95% CIs, tau = 1% FPR on val reals of the same condition. Rule and candidates fixed before scoring: docs/VIDEO_DEEPFAKE.md 5b. FF++ rows of models marked * may include videos they were trained on (training lists unpublished).

| Model | Hub id @ revision | Licence | Params (M) | Trained on |
|---|---|---|---|---|
| satya_sbi | ours (`research/video/train_sbi.py`) | FF++ terms | 4.0 | FF++ train **reals** + self-blended pseudo-fakes |
| gend_clip_l14 | `yermandy/GenD_CLIP_L_14` @ 891ce01 | MIT | 304 | FF++ c23 official train split, 4 methods (paper Sec. 4) |
| ms_eff_gcvit_b0 | `KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus` @ db131ba | MIT | 8.7 | FF++ c23 with the authors' own train/test lists (not published in the wheel) |
| vit_dima806 | `dima806/deepfake_vs_real_image_detection` @ 29e4cf9 | Apache-2.0 | 86 | undocumented image dataset (Kaggle-style real/fake faces) |
| vit_prithiv_v2 | `prithivMLmods/Deep-Fake-Detector-v2-Model` @ 3a99ae2 | Apache-2.0 | 86 | undocumented image dataset |
| community_forensics | `buildborderless/CommunityForensics-DeepfakeDet-ViT` @ ac6ee45 | MIT | 22 | 2.7M AI-generated images from 4,803 generators (CVPR 2025); no face swaps |

## Condition `orig`

| Model | val AUC | FF++ test AUC (4 seen) | FaceShifter AUC (unseen) | DFDC AUC (unseen) | DFDC TPR @ tau | DFDC FPR @ tau |
|---|---|---|---|---|---|---|
| satya_sbi | 0.808 [0.771, 0.844] | 0.780 [0.755, 0.807] | 0.750 [0.708, 0.793] | 0.636 [0.590, 0.682] | 2.4% [1, 5] | 0.0% [0, 1] |
| gend_clip_l14 | 0.971 [0.957, 0.983] | 0.974 [0.963, 0.984] | 0.837 [0.796, 0.874] | 0.800 [0.761, 0.840] | 17.6% [13, 23] | 0.0% [0, 1] |
| ms_eff_gcvit_b0 * | 0.985 [0.971, 0.995] | 0.978 [0.962, 0.989] | 0.965 [0.945, 0.981] | 0.695 [0.659, 0.732] | 0.0% [0, 2] | 0.0% [0, 1] |
| vit_dima806 * | 0.570 [0.527, 0.611] | 0.551 [0.523, 0.581] | 0.465 [0.422, 0.509] | 0.462 [0.413, 0.510] | 6.4% [4, 10] | 5.2% [3, 8] |
| vit_prithiv_v2 * | 0.517 [0.476, 0.562] | 0.522 [0.493, 0.551] | 0.488 [0.441, 0.539] | 0.616 [0.576, 0.655] | 0.0% [0, 2] | 0.0% [0, 1] |
| community_forensics * | 0.641 [0.588, 0.689] | 0.647 [0.619, 0.677] | 0.618 [0.561, 0.670] | 0.483 [0.443, 0.522] | 0.0% [0, 2] | 0.0% [0, 1] |

Paired delta AUC vs our SBI CNN (same videos):

| Model | val | FF++ test | DFDC |
|---|---|---|---|
| gend_clip_l14 | 0.163 [0.126, 0.198] | 0.173 [0.144, 0.198] | 0.164 [0.118, 0.213] |
| ms_eff_gcvit_b0 | 0.177 [0.140, 0.212] | 0.201 [0.171, 0.229] | 0.059 [0.006, 0.112] |
| vit_dima806 | -0.237 [-0.297, -0.182] | -0.240 [-0.280, -0.202] | -0.174 [-0.230, -0.121] |
| vit_prithiv_v2 | -0.291 [-0.344, -0.236] | -0.259 [-0.300, -0.221] | -0.020 [-0.090, 0.050] |
| community_forensics | -0.166 [-0.232, -0.104] | -0.133 [-0.172, -0.094] | -0.153 [-0.216, -0.090] |

## Condition `call720`

| Model | val AUC | FF++ test AUC (4 seen) | FaceShifter AUC (unseen) | DFDC AUC (unseen) | DFDC TPR @ tau | DFDC FPR @ tau |
|---|---|---|---|---|---|---|
| satya_sbi | – | 0.721 [0.696, 0.749] | 0.704 [0.659, 0.751] | – | – | – |
| ms_eff_gcvit_b0 * | – | 0.914 [0.888, 0.937] | 0.896 [0.861, 0.927] | – | – | – |

Paired delta AUC vs our SBI CNN (same videos):

| Model | val | FF++ test | DFDC |
|---|---|---|---|
| ms_eff_gcvit_b0 | – | 0.193 [0.158, 0.227] | – |

## Condition `call360`

| Model | val AUC | FF++ test AUC (4 seen) | FaceShifter AUC (unseen) | DFDC AUC (unseen) | DFDC TPR @ tau | DFDC FPR @ tau |
|---|---|---|---|---|---|---|
| satya_sbi | 0.702 [0.663, 0.743] | 0.683 [0.658, 0.709] | 0.657 [0.616, 0.702] | 0.600 [0.557, 0.639] | 0.4% [0, 2] | 0.5% [0, 2] |
| gend_clip_l14 | 0.885 [0.863, 0.909] | 0.889 [0.866, 0.910] | 0.733 [0.689, 0.780] | 0.671 [0.628, 0.711] | 3.6% [2, 7] | 1.9% [1, 4] |
| ms_eff_gcvit_b0 * | 0.752 [0.711, 0.792] | 0.770 [0.741, 0.799] | 0.778 [0.737, 0.818] | 0.537 [0.491, 0.584] | 0.0% [0, 2] | 0.0% [0, 1] |

Paired delta AUC vs our SBI CNN (same videos):

| Model | val | FF++ test | DFDC |
|---|---|---|---|
| gend_clip_l14 | 0.183 [0.138, 0.227] | 0.180 [0.152, 0.207] | 0.071 [0.015, 0.128] |
| ms_eff_gcvit_b0 | 0.050 [-0.003, 0.101] | 0.094 [0.060, 0.126] | -0.062 [-0.115, -0.011] |

## Pre-registered selection (val only)

Decision: **gend_clip_l14**.
GenD - SBI val AUC under call360: +0.183 (bootstrap SE 0.022, 95% CI [0.138, 0.227]).
