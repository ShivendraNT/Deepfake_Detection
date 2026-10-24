# Video deepfake check — feasibility, design, protocol, results

> Owner: Shivendra (lead). Code: `src/satyapan/video/` (product), `research/video/` (benchmark).
> Decision record: ADR-025 in `docs/DECISIONS.md`. Measured numbers: `results/video_benchmark.md`,
> `results/video_lipsync.json`, rows in `results/EVIDENCE_LEDGER.md` §7.

## 1. The question we were asked

"When we are on a video call (or playing any video), take the screen recording after asking
permission, analyse the pixels, test lip-sync, use a CNN on the blurring/sharpness of the face
edges, check lighting and reflection inconsistencies, and check the faint red flush that each
heartbeat pushes through the face." Verify the ideas, check feasibility, do better where possible.

## 2. Verdict, idea by idea

| Idea | Verdict | Why (literature + our measurements) | What we built |
|---|---|---|---|
| Screen capture during a call, after permission | **Feasible, shipped** | Electron `getDisplayMedia` already gives Satya the screen + system audio. We keep the video track only after a yes for *this* call, sample ~15 frames/s, downscale to ≤1280 px, keep frames in RAM for one 6 s window. The practical limit is **face size**: in a 3×3 Meet grid a face is ~80–120 px, so we gate at 64 px and tell the user to pin/enlarge the caller. | `desktop/renderer/src/capture/videoFrames.ts`, `POST /live/{call_id}/video` |
| CNN on blurring / sharpness of the face edge | **Feasible and the strongest cue — measured: our CPU-trained version is beaten by a published one, which now ships** | A CNN trained on a fixed list of deepfake methods learns those methods and collapses on new ones (FF++→Celeb-DF AUC for Xception is about 0.65 in the literature). The principled version of exactly this idea is *Face X-ray* (Li et al., CVPR 2020) and *Self-Blended Images* (Shiohara & Yamasaki, CVPR 2022): synthesise the blending boundary — colour mismatch, sharpness mismatch (blur or over-sharpen), soft deformed mask — from **real** faces, so the CNN can only learn the boundary itself. **Measured** (§6): our SBI EfficientNet-B0 (CPU, 224 px) reaches video AUC 0.79 on FF++ test and 0.63 on DFDC. GenD (CLIP ViT-L/14 with only its LayerNorms tuned on FF++, WACV 2026, MIT) beat it on the pre-registered val comparison by +0.18 AUC on call-quality video, so GenD is Satya's face CNN and ours is the automatic fallback. | GenD exported to ONNX (`research/video/export_gend.py`); our SBI CNN (`sbi.py`, `train_sbi.py`, real videos only) as fallback and reference |
| Lighting and reflection inconsistencies | **Partly feasible** | Corneal highlights (Hu, Li & Lyu, ICASSP 2021) were shown on 1024 px GAN portraits; on a call the iris is 5–10 px wide, so highlights are usually unmeasurable (we report how often). Region colour/shading consistency between the swapped inner face and the untouched forehead is cheap and explainable but weak alone. **Measured**: 0.57 AUC alone on FF++ test (0.79 on Deepfakes, ≈ 0.5 on the others); the pre-registered 1-SE rule did not add it to the CNN. | `lighting.py`: cheek-vs-forehead chroma gap, left/right shading direction gap, frame-to-frame flicker, specular-highlight gap |
| Heartbeat colour (rPPG) | **Weak in calls; kept as one feature, measured honestly** | FakeCatcher (Ciftci et al., TPAMI 2020) and DeepFakesON-Phys (Hernandez-Ortega et al., 2021) separate older deepfakes in high-quality video. But the pulse is ~0.1–0.5 % of skin intensity and call codecs at 0.3–1.5 Mbit/s remove much of it (McDuff et al., 2017), and modern swaps inherit the *driver's* pulse ("High-quality deepfakes have a heart!", Seibold et al., 2025). So "no pulse = fake" is not safe; spatial pulse *coherence* is the more robust form. **Measured**: 0.45–0.58 AUC on FF++ c23 (chance): YouTube-grade compression has already removed it, before any call codec. Not used by the shipped fusion. | `rppg.py`: POS (Wang et al., 2017) per patch; SNR, cross-patch coherence, heart-rate agreement |
| Lip-sync | **Feasible for one attack, blind to another** | Catches *real footage + someone else's or a cloned voice* (the common "CEO video" cheapfake) and poorly synced talking heads. It cannot catch a live face swap where the attacker speaks (the lips match by construction) or lip-sync generators trained against a sync expert (Wav2Lip). FF++ has no audio and DFDC fakes keep the real voice, so we built a controlled mismatch test. **Measured** (zero parameters, DFDC reals): swapped voice 0.62 [0.59, 0.66], TTS voice-over 0.66 [0.63, 0.70], 1 s delay 0.67 [0.63, 0.71] AUC — a weak but real signal for the "real face + cloned voice" scam. | `lipsync.py`: mouth opening vs. speech envelope, best correlation within ±0.4 s; `research/video/lipsync_eval.py` |

**What we added beyond the brief.**
1. *Measure before trusting*: our own CNN trained on real faces only (SBI) **and** five
   off-the-shelf detectors from Hugging Face went through one protocol; a rule fixed in advance
   picked the one that ships (GenD), on validation data only (§5b, `results/video_selection.json`).
2. *Fusion with abstention*: four cues → one calibrated score per 6 s window; no usable face →
   the window abstains instead of guessing.
3. *Raise-only policy integration*: two consecutive windows above a threshold fitted at **1 %
   false-positive rate on validation reals** → `VIDEO_LIKELY_SYNTHETIC` (one band above the
   floor; never HOLD on its own). The face check can never clear a payment.
4. *The call channel as a test condition*: every test video is re-encoded through VP8 (WebRTC's
   default codec) at 1.2 and 0.4 Mbit/s, then JPEG-compressed like the capture hop, and
   re-measured.
5. A practical live counter-measure for the alert card (not scored): ask the caller to **turn
   their head to the side or pass a hand across their face** — real-time face swaps break on
   profile views and occlusion. The decision still comes from OOB-Confirm.

## 3. Threats in a video call and which cue can see them

| Attack | Blend CNN | Pulse | Lighting | Lip-sync |
|---|---|---|---|---|
| Live face swap (DeepFaceLive-style), attacker speaks | yes (boundary) | weak (inherits driver pulse) | sometimes | no (lips are the attacker's) |
| Pre-rendered talking head from one photo | sometimes (no boundary if fully generated) | yes (pulse comes from a still photo) | sometimes | yes if poorly synced |
| Real footage of the executive + cloned voice | no (the face is real) | no | no | **yes** |
| Fully synthetic face (GAN/diffusion video) | partly | partly | highlights at high res | depends |

No single cue covers every row — which is why the band is set by the payment floor and the
asks, and the face check only adds evidence.

## 4. Pipeline (what ships)

```
capture window (Electron, after a yes)                     local engine (127.0.0.1:8000)
  screen track ─ ImageCapture ─ 15 fps ─ ≤1280 px JPEG ─▶  POST /live/{call}/video
                                                            │ decode (Pillow), RAM only
                                                            ▼
          FaceTracker: YuNet finds the largest face (≤640 px copy) → MediaPipe 478 landmarks
          on a face-centred crop that follows the face (small grid/1080p faces stay trackable)
                                                            ▼
                         FrameRecord: 5 skin patches, iris highlights, mouth opening,
                         face size/brightness, a 224 px face crop every 2.25 s
                                                            ▼
                  window 6 s / hop 3 s ─ coverage gate (face ≥ 64 px, ≥ 70 % frames, light)
          face CNN: GenD ONNX (SBI CNN fallback) · pulse · lighting · lip-sync (if audio)
                                                            ▼
                     fusion (logistic, config/video_fusion.json) → score in [0, 1]
                                                            ▼
          rule: ≥ 2 consecutive windows ≥ τ_hi → VIDEO_LIKELY_SYNTHETIC (PLUS_ONE, ML, media)
                any ≥ τ_lo or nothing usable → VIDEO_INCONCLUSIVE (info) · else VIDEO_NO_SIGNS
                                                            ▼
                        policy engine decides the band · VideoEvent (label, never a score)
```

The same `satyapan.video` functions produce every number in the benchmark, so the benchmark
measures exactly what ships (frames → records → window features → fusion → rule).

## 5. Data and protocol (fixed before the test run)

| Role | Data | Used for | Leakage controls |
|---|---|---|---|
| `sbi_train` | FF++ c23 train, reals of 240 pairs (480 videos × 16 frames) | blend CNN (real + self-blends) | no fake video read; disjoint from fusion pairs |
| model selection (CNN) | FF++ val reals (140 videos × 8 frames) vs. their seeded self-blends | pick the best epoch | no deepfake involved |
| `fusion_train` | FF++ c23 train, 60 other pairs: 120 reals + 480 fakes (DF, F2F, FS, NT) | 5-fold identity-grouped CV over C, then the fusion fit | `StratifiedGroupKFold` on the source/target pair, so a face never sits on both sides |
| thresholds | FF++ c23 val, 140 reals (2 windows each) | τ_hi = 1 % window FPR, τ_lo = 5 % | fitted before any test number existed |
| `test` | FF++ c23 official test: 140 reals + 140 each of DF, F2F, FS, NT, **FaceShifter** | in-domain + unseen-method (FaceShifter never seen by anything) | official split; identity-disjoint from all of the above |
| `xtest` | DFDC parts 0–2: 424 reals + 250 seeded fakes (consenting actors) | cross-dataset | never trained, tuned or thresholded on |
| conditions | `orig`, `call720` (VP8 1.2 Mbit/s ≤1280×720 + JPEG q85), `call360` (VP8 0.4 Mbit/s ≤640×360 + JPEG q85) | robustness | same videos, same frozen models |

Every video is analysed for its first 9 s (two 6 s windows at 15 fps) — the same for every set.
Metrics are **video-level** (mean of usable window scores): AUC and EER with a 95 % bootstrap
over identity clusters (2,000 resamples; a person's real and fake videos move together), plus the
product rule's alert rates on reals (false alarms) and fakes (detections) with Wilson intervals.
`results/video_eval_manifest.json` lists every file with its sha256. All randomness is seeded
(`SEED = 20261024`); `tests/harness/test_results_provenance.py` checks that nothing writing to
`results/` uses an unseeded RNG.

### 5b. Off-the-shelf detectors from Hugging Face (rule fixed 24 Oct 2026, before scoring)

"Why not just download a model?" We did, and put every candidate through the protocol above
(`research/video/hf_baselines.py`, revisions pinned, licences recorded):

| Model (Hub id @ pinned rev) | Licence | Params | Trained on | Our FF++ val/test unseen by it? |
|---|---|---|---|---|
| GenD CLIP ViT-L/14 (`yermandy/GenD_CLIP_L_14`, WACV 2026) | MIT | 304 M | FF++ c23 **official** train: 720 reals + 4 × 720 fakes (paper §4) | **yes** (official split) |
| MS-EffGCViT-b0 (`KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus`) | MIT | 8.7 M | FF++ c23, the authors' own unpublished lists | unknown: FF++ rows flagged |
| ViT-B/16 (`dima806/deepfake_vs_real_image_detection`) | Apache-2.0 | 86 M | undocumented face images | unknown |
| ViT-B/16 (`prithivMLmods/Deep-Fake-Detector-v2-Model`) | Apache-2.0 | 86 M | undocumented | unknown |
| ViT-S/16 (`buildborderless/CommunityForensics-DeepfakeDet-ViT`, CVPR 2025) | MIT | 22 M | 2.7 M AI-generated images, 4,803 generators, no face swaps | n/a |

DFDC is unseen by all of them. Not evaluated: the VideoMAE "deepfake" checkpoints on the Hub
(CC-BY-NC, or an undocumented FF++ subset with 16-frame clips we do not store; best
self-reported AUC 0.84 in-distribution).

**Matched protocol.** Every model, and our SBI CNN, sees the same stored crops: K = 4 evenly
spaced 224 px crops per 9.2 s clip (one about every 2.25–3 s, which is what a ViT-L can
afford live on a laptop CPU; the overlapping 6 s windows hold about 3 each — wording corrected
on 24 Oct, the rule is unchanged); a video's score is the mean fake-logit; same videos, identity clusters,
bootstrap and conditions as §5; τ = 1 % FPR on the val reals of the same condition. All models
are scored on `orig`; the call conditions are scored for every model whose `orig` val AUC is
≥ 0.70.

**Selection rule for the product's CNN slot.** Eligible: a licence that allows redistribution, a
documented training split disjoint from our val/test, and an ONNX export that matches the
reference model to 1e-3 (today: GenD only; int8 quantisation was rejected because its logits
correlated only r = 0.92 with fp32). GenD replaces the SBI CNN **only if** its FF++ val AUC under
`call360` exceeds the SBI CNN's by more than one bootstrap SE of the paired difference (the
cheaper model wins ties). If it does, the product pipeline is re-fitted with GenD logits exactly
as in §5 (τ on val reals; the product samples one crop every 2.25 s for it and scores each crop
once) and the frozen benchmark runs once. GenD trained on the FF++ train split, so
`fusion_train` cannot fit anything for it: its fusion is the identity on the mean crop logit,
which gives the same alerts as any monotone 1-D fit at thresholds set on val reals. Both rows are reported whatever happens; test sets never select anything.

## 6. Results

Full tables: `results/video_benchmark.md` (shipped GenD check), `results/video_benchmark__blend.md`
(our SBI fallback), `results/video_external.md` (all six models, matched crops),
`results/image_face_benchmark.md` (one crop = one photo). Selection, made on val before any
test number existed: GenD − SBI on call360 val = +0.183 (SE 0.023) → GenD ships
(`results/video_selection.json`, decided 14:04 UTC 24 Oct).

What the product does per video, held-out sets scored once (Wilson 95 % in the result files):

| Set | Condition | AUC [95 % CI] | Fakes flagged (VERIFY or above) | Real videos flagged | Real videos called LIKELY_SYNTHETIC |
|---|---|---|---|---|---|
| FF++ test, 4 seen methods | orig | 0.975 [0.963, 0.985] | 85.4 % (475/556) | 2.9 % (4/139) | 0 / 139 |
| FF++ test, FaceShifter (method unseen) | orig | 0.832 [0.791, 0.870] | 31.7 % (44/139) | 2.9 % | 0 / 139 |
| DFDC (dataset unseen) | orig | 0.778 [0.734, 0.823] | 24.8 % (62/250) | 0.7 % (3/424) | 0 / 424 |
| FF++ test, all 5 methods | call360 (VP8 0.4 Mbit/s + JPEG) | 0.877 [0.854, 0.900] | 50.6 % (352/695) | 5.0 % (7/139) | 0 / 139 |
| DFDC | call360 | 0.728 [0.653, 0.805]\* | 4.4 % (11/250) | 0.5 % (2/424) | 0 / 424 |

\* only 78 real / 47 fake DFDC videos keep a ≥ 64 px face at 360p; the other 82 % are "couldn't
check" (no band effect).

Same sets with our SBI CNN (fallback): FF++ test 0.786, DFDC 0.633, FF++ call360 0.714; it
flags 15 % of FF++ fakes. Generic Hugging Face "deepfake" image classifiers score 0.46–0.65
AUC on the same crops (`results/video_external.md`): popular is not the same as tested.

**Named failure cases** (each one is in the tables above):
1. *New methods.* FaceShifter (not in GenD's training) is flagged 32 % of the time vs 85 % for
   the four seen methods; NeuralTextures (expression-only edits) drops to 24 % at 360p.
2. *Small faces.* At 360p most DFDC faces are under 64 px: Satya says "couldn't check — pin or
   enlarge the caller" instead of guessing. In a 3×3 grid this is the common case.
3. *Real face, cloned voice.* The face check is blind by construction; lip-sync is weak
   (0.62–0.67 AUC) and the voice check and the asks carry this scam.
4. *Strict alerts are rare on unseen data.* LIKELY_SYNTHETIC fires on 7 % of DFDC fakes; most
   catches there are SUSPICIOUS (VERIFY: "call back first"), never HOLD on the face alone.
5. *Codec cost.* 360p call quality costs 0.05–0.16 AUC (DFDC; NeuralTextures worst); thresholds stay fixed, so
   the false-alarm rate on reals rises to 5 % (all VERIFY, none LIKELY).

**A bug the benchmark caught.** The first extraction used MediaPipe's landmarker alone. Its
built-in detector is the short-range BlazeFace (128 px input, selfie framing): it found **no
face at all in 361 of 674 DFDC videos** (people at 1–2 m in a 1080p frame) — exactly the small
faces of a Meet grid. We replaced it with a two-stage tracker (YuNet detection + landmarks on a
face-centred crop) and re-ran every extraction, so the numbers describe the shipped tracker.
(The CNN's training crops came from FF++ close-ups, where both trackers agree.)

## 7. What we do not claim

- A face check never proves who is on the call. "No signs" is not approval; it never lowers a band.
- Thresholds are calibrated on FF++ (YouTube/broadcast) reals, not on webcam calls:
  `config/video_thresholds.json` says `calibrated: false`. Before a real deployment, re-fit τ on
  consented team webcam calls (same rule as the voice detector's Meet calibration, T18).
- Beauty filters, virtual backgrounds and background blur in Meet/Teams/Zoom also blend a face
  edge; expect more false alarms with them on (not measured: no consented data yet).
- The benchmark faces are FF++/DFDC (2019–2020 generators). Newer real-time swappers and
  diffusion talking heads are not in any public, licensed test set we could reach today.
- The blend CNN was trained on CPU (EfficientNet-B0, 224 px, early layers frozen); the published
  SBI result uses EfficientNet-B4 at 380 px on a GPU. Our numbers are for our model.

## 8. Headline numbers

- **Shipped face check (GenD):** FF++ test AUC 0.946 [0.932, 0.960] (all 5 methods), DFDC
  (never seen) 0.778 [0.734, 0.823]; flags 74.7 % of FF++ fakes and 24.8 % of DFDC fakes for a
  call-back; **0 of 563 real test videos** called LIKELY_SYNTHETIC, 7 of 563 flagged for a
  call-back (1.2 %).
- **Photo check (one crop):** FF++ test AUC 0.923, DFDC 0.747; 0.4 % / 0.0 % of real crops
  over τ_hi (`results/image_face_benchmark.md`).
- **Selection was honest:** GenD beat our SBI CNN by +0.183 val AUC (SE 0.023) under call
  quality before any test number existed; our CNN stays as the automatic fallback.
- **Latency:** ≈ 1.3 s per GenD crop on 2 CPU threads while other jobs ran (benchmark logs);
  the product scores one crop per 2.25 s of call, so a 4-core laptop keeps up.
- 720p (`call720`) GenD scoring was stopped at 141 of 980 videos to free the CPU for the voice
  benchmark; reports leave partial splits out rather than print them.

## 9. Laptops (any OS, any CPU)

| Laptop | Satya app | Face check | Notes |
|---|---|---|---|
| macOS Apple Silicon (arm64) | `npm run dist:mac` (dmg, arm64) | yes | grant Screen Recording; system audio needs macOS 14.2+ |
| macOS Intel (x64) | `npm run dist:mac` (dmg, x64) | yes, Python 3.11/3.12 | last mediapipe/onnxruntime builds for Intel Macs are pinned in `pyproject.toml` |
| Windows x64 | `npm run dist:win` (NSIS, x64) | yes | loopback system audio is native on Windows |
| Windows on ARM (Snapdragon) | `npm run dist:win` (NSIS, arm64) | yes, with **x64 Python** | OpenCV/CTranslate2 ship no win_arm64 wheels; Windows 11 runs x64 Python transparently: `uv python install cpython-3.12-windows-x86_64` |
| Linux x64 / arm64 | `npm run dist:linux` (AppImage + deb) | yes | needs `libegl1 libgles2` (mesa); Screen Guard OCR needs `tesseract-ocr`; Wayland asks via the portal |

Backend on any of them: `uv run python scripts/satya.py video` (or `make video`) installs the
face check and verifies the model hashes in `config/video_models.json`. GenD is one 1.2 GB fp32
ONNX file that ONNX Runtime runs on every CPU above (x64 AVX2 / arm64 NEON, no GPU); it is
built once with `python -m research.video.export_gend` (or fetched from a team release via
`SATYAPAN_GEND_MODEL_URL`). Satya scores one face crop every 2.25 s with it, each crop once,
so a call costs roughly one ViT-L forward pass per 2 s of call. A laptop without the file
falls back to our 16 MB SBI CNN and its own thresholds automatically (health shows which).

## 10. Reproduce

```bash
export SATYAPAN_VIDEO_DATA=../satyapan-data/video     # media stays outside the repo
python -m research.video.data ffpp dfdc               # download (HF mirrors), seeded subsets
python -m research.video.sbi_prep                     # landmarks + loose crops of real videos
python -m research.video.train_sbi                    # blend CNN -> models/video/blend_b0.onnx
python -m research.video.extract --sets ffpp dfdc --splits fusion_train val test xtest
python -m research.video.extract --sets ffpp dfdc --splits val test xtest --val-reals-only --condition call360
python -m research.video.extract --sets ffpp --splits val test --val-reals-only --condition call720
python -m research.video.tables --condition orig      # (and call720, call360)
python -m research.video.fit_fusion                   # CV + fusion + frozen thresholds (no test)
python -m research.video.run_benchmark                # the one test run -> results/
python -m research.video.lipsync_eval                 # AV-mismatch test -> results/
python -m research.video.manifest                     # sha256 of every file used
```
