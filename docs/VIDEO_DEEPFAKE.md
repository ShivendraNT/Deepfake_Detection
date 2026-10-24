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
| CNN on blurring / sharpness of the face edge | **Feasible, our strongest cue — if trained the right way** | A CNN trained on a fixed list of deepfake methods learns those methods and collapses on new ones (FF++→Celeb-DF AUC for Xception is about 0.65 in the literature). The principled version of exactly this idea is *Face X-ray* (Li et al., CVPR 2020) and *Self-Blended Images* (Shiohara & Yamasaki, CVPR 2022): synthesise the blending boundary — colour mismatch, sharpness mismatch (blur or over-sharpen), soft deformed mask — from **real** faces, so the CNN can only learn the boundary itself. | EfficientNet-B0 trained on FF++ **real** videos only (`research/video/sbi.py`, `train_sbi.py`); no deepfake is ever read in training or model selection |
| Lighting and reflection inconsistencies | **Partly feasible** | Corneal highlights (Hu, Li & Lyu, ICASSP 2021) were shown on 1024 px GAN portraits; on a call the iris is 5–10 px wide, so highlights are usually unmeasurable (we report how often). Region colour/shading consistency between the swapped inner face and the untouched forehead is cheap and explainable but weak alone; the SBI CNN already sees most of it. | `lighting.py`: cheek-vs-forehead chroma gap, left/right shading direction gap, frame-to-frame flicker, specular-highlight gap |
| Heartbeat colour (rPPG) | **Weak in calls; kept as one feature, measured honestly** | FakeCatcher (Ciftci et al., TPAMI 2020) and DeepFakesON-Phys (Hernandez-Ortega et al., 2021) separate older deepfakes in high-quality video. But the pulse is ~0.1–0.5 % of skin intensity and call codecs at 0.3–1.5 Mbit/s remove much of it (McDuff et al., 2017), and modern swaps inherit the *driver's* pulse ("High-quality deepfakes have a heart!", Seibold et al., 2025). So "no pulse = fake" is not safe; spatial pulse *coherence* is the more robust form. | `rppg.py`: POS (Wang et al., 2017) per patch; SNR, cross-patch coherence, heart-rate agreement |
| Lip-sync | **Feasible for one attack, blind to another** | Catches *real footage + someone else's or a cloned voice* (the common "CEO video" cheapfake) and poorly synced talking heads. It cannot catch a live face swap where the attacker speaks (the lips match by construction) or lip-sync generators trained against a sync expert (Wav2Lip). FF++ has no audio and DFDC fakes keep the real voice, so we built a controlled mismatch test. | `lipsync.py`: mouth opening vs. speech envelope, best correlation within ±0.4 s; `research/video/lipsync_eval.py` |

**What we added beyond the brief.**
1. *Train on real faces only* (SBI) — the defensible route to "works on methods we never saw".
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
                         face size/brightness, a 224 px face crop every 0.75 s
                                                            ▼
                  window 6 s / hop 3 s ─ coverage gate (face ≥ 64 px, ≥ 70 % frames, light)
                    blend CNN (ONNX) · pulse (POS) · lighting · lip-sync (if call audio)
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

## 6. Results

See §8 (filled from `results/video_benchmark.md` by the benchmark run).

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

(Filled in from `results/video_benchmark.md` after the frozen run.)

## 9. Laptops (any OS, any CPU)

| Laptop | Satya app | Face check | Notes |
|---|---|---|---|
| macOS Apple Silicon (arm64) | `npm run dist:mac` (dmg, arm64) | yes | grant Screen Recording; system audio needs macOS 14.2+ |
| macOS Intel (x64) | `npm run dist:mac` (dmg, x64) | yes, Python 3.11/3.12 | last mediapipe/onnxruntime builds for Intel Macs are pinned in `pyproject.toml` |
| Windows x64 | `npm run dist:win` (NSIS, x64) | yes | loopback system audio is native on Windows |
| Windows on ARM (Snapdragon) | `npm run dist:win` (NSIS, arm64) | yes, with **x64 Python** | OpenCV/CTranslate2 ship no win_arm64 wheels; Windows 11 runs x64 Python transparently: `uv python install cpython-3.12-windows-x86_64` |
| Linux x64 / arm64 | `npm run dist:linux` (AppImage + deb) | yes | needs `libegl1 libgles2` (mesa); Screen Guard OCR needs `tesseract-ocr`; Wayland asks via the portal |

Backend on any of them: `uv run python scripts/satya.py video` (or `make video`) installs the
face check and verifies the model hashes in `config/video_models.json`.

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
