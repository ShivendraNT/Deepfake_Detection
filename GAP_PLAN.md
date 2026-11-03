# GAP_PLAN.md — Multimedia Evidence Authentication, Deepfake Detection and Provenance Analysis Framework

Problem Statement (`PS.md`): **"Multimedia Evidence Authentication, Deepfake Detection and Provenance Analysis Framework"**
Target Users: **Investigating agencies and digital forensic laboratories**.

This document maps each of the 5 Expected Deliverables in `PS.md` (and Milestones M1–M8) to:
1. **What already exists** in this repository (`Satyapan`) and the sibling forensic repository (`Pramaan`, `~/Desktop/igdtu`), citing exact files;
2. **What is missing** for a complete, court-aware, offline forensic laboratory workstation; and
3. **The measurable target** that will be verified by automated tests and recorded in `results/EVIDENCE_LEDGER.md`.

---

## Overview Table: 5 PS Deliverables → Milestones M1–M8

| PS Deliverable | Milestone(s) | Existing Foundation (Cited Files) | Key Gaps to Build | Measurable Target |
|---|---|---|---|---|
| **1. Deepfake & Synthetic Media Detection Engine** | **M2** | `src/satyapan/imagecheck/face.py` (GenD face-swap photo check), `src/satyapan/video/` (GenD + SBI CNN, rPPG, lighting, lip-sync, 6s window fusion), `src/satyapan/voice/` (XLS-R ONNX voice-clone check) | Add whole-image AI-generated (diffusion/GAN) detector (`src/satyapan/forensics/deepfake.py`), unify image + video (frame-level & aggregate) + audio synthetic detection with forensic non-absolutist framing, calibrate thresholds on validation split, run held-out + re-encode robustness benchmark | Held-out test AUC, TPR, FPR at calibrated thresholds (`tau_hi`, `tau_lo`) + JPEG re-encode robustness Delta-AUC in `results/EVIDENCE_LEDGER.md` |
| **2. Multimedia Authentication & Tampering Detection Framework** | **M1, M3** | `src/satyapan/vault/` (SHA-256 intake, SQLite hash chain), `~/Desktop/igdtu/pramaan/locker/` (`intake.py`, `signing.py`, `custody.py`, `merkle.py`, `anchor.py`), `pramaan/ai/image_model.py` (basic ELA), `src/satyapan/document/pdf.py` | **M1**: Case folders, read-only originals (`0o444`), working-copy isolation, Ed25519-signed hash-chained custody log + RFC 6962 Merkle tree. **M3**: Image (ELA + heatmap, double-JPEG/Q-table, copy-move + heatmap, noise-residual inconsistency + heatmap), Video (duplicated/dropped frames, re-encoding signs), Audio (splice/discontinuity cues + spectrogram) | M1: 100% analyses run on working copies; tamper simulator catches 1-bit flip. M3: Per-detector AUC / TPR / FPR on seeded tamper benchmark in `results/EVIDENCE_LEDGER.md` |
| **3. Multimedia Provenance & Source Attribution Tool** | **M4** | `~/Desktop/igdtu/pramaan/parsers/image_meta.py`, `pramaan/auditor/rules/image_check.py`, `src/satyapan/document/pdf.py`, `src/satyapan/email/parser.py` | Comprehensive EXIF/XMP/PNG/container metadata extractor & consistency engine (timestamps, software tags, GPS validity, embedded thumbnail vs main image mismatch), C2PA Content Credentials / JUMBF manifest verifier, compression-fingerprint source attribution (camera original vs WhatsApp/social re-encode vs editing software) | Metadata anomaly precision/recall on seeded test set; 3-class compression-fingerprint attribution accuracy & macro-F1 in `results/EVIDENCE_LEDGER.md` |
| **4. Explainable AI-based Multimedia Forensic Analysis Dashboard** | **M5** | `src/satyapan/api/routes_dashboard.py`, `~/Desktop/igdtu/pramaan/api.py`, `pramaan/ui/static/index.html` (offline D3 cockpit) | Build `/forensics` investigator workstation & `/api/forensics/*` API: case view, file inventory, per-check finding ("consistent with" / "inconsistent with") + confidence + plain/technical "why" + ELA/noise/copy-move heatmaps & audio spectrogram, chronological timeline, signed custody + Merkle proof viewer, live tamper test, and "Limits of This Analysis" panel | 100% offline dashboard (0 external requests); full FastAPI route & UI rendering test suite green |
| **5. Automated Multimedia Forensic Reporting System** | **M6** | `~/Desktop/igdtu/pramaan/report/section63.py` (BSA 2023 Section 63 Parts A & B draft), `pramaan/report/build.py`, `src/satyapan/report/pack.py` | Build reproducible one-click PDF + HTML + Markdown + JSON forensic report generator (`src/satyapan/forensics/report.py`) embedding case details, SHA-256 schedule, signed custody chain, Merkle root, methods, per-finding heatmaps, confidence, limitations, examiner sign-off block, and Section 63 BSA 2023 Parts A & B draft certificate | Reproducible report generation from case store; golden-file & PDF structure/image tests green |
| **Cross-cutting: Tests, Red-Team & Offline Deployment** | **M7, M8** | `tests/`, `scripts/redteam.py`, `Makefile`, `docs/JUDGES.md` | **M7**: Unit tests for every forensic module, golden-file report tests, E2E test on committed open demo kit (`demo_kit/`), adversarial robustness suite (re-encode, resize, crop, noise, metadata strip). **M8**: Offline `docker-compose.yml` + `Dockerfile`, `make demo`, updated `docs/JUDGES.md`, `docs/LIMITS.md`, `docs/explain/<module>.md` | `make check` 100% green, 0 untested modules, adversarial degradation table in `results/EVIDENCE_LEDGER.md`, `make demo` runs E2E offline |

---

## Detailed Gap Analysis by Milestone

### M1 — Evidence Intake & Cryptographic Integrity (`src/satyapan/forensics/locker.py`)
- **What exists**:
  - `src/satyapan/vault/hashing.py`, `src/satyapan/vault/custody.py`, `src/satyapan/vault/intake.py`: SHA-256 hashing before parsing and SQLite custody chain.
  - `~/Desktop/igdtu/pramaan/locker/` (`__init__.py`, `intake.py`, `signing.py`, `custody.py`, `merkle.py`, `anchor.py`): Ed25519 key generation and signing (`cryptography`), JSONL hash-chained custody log, RFC 6962 Certificate-Transparency-style Merkle tree with O(log N) inclusion proofs, QR/text paper-register anchors, and reversible 1-bit tamper simulation.
- **What is missing**:
  - A forensic case workspace manager that creates structured case directories (`cases/<case_id>/originals/`, `cases/<case_id>/working/`, `cases/<case_id>/artifacts/`, `cases/<case_id>/custody.jsonl`, `cases/<case_id>/evidence.json`, `cases/<case_id>/anchor.txt`), marks sealed originals read-only (`chmod 0o444`), and provides `checkout_working_copy(evidence_id)` so every downstream analysis (M2, M3, M4) runs exclusively on a verified working copy and logs a signed `"working_copy"` / `"analyze"` custody entry.
- **Measurable target**:
  - Unit & invariant tests verifying: (1) SHA-256 computed at intake before any parser runs; (2) `originals/` files are `0o444` read-only and untouched after full pipeline execution; (3) any 1-bit modification to a sealed copy or custody entry is caught by `verify_all()` and `audit_proof()`; (4) Ed25519 signatures and RFC 6962 Merkle inclusion proofs verify across all case items.

### M2 — Deepfake & Synthetic Media Detection Engine (`src/satyapan/forensics/deepfake.py`)
- **What exists**:
  - Face-swap image detector (`src/satyapan/imagecheck/face.py`) and video detector (`src/satyapan/video/analyzer.py`, `cnn.py`, `features.py`, `fusion.py`, `rules.py`, `rppg.py`, `lighting.py`, `lipsync.py`) using GenD CLIP ViT-L/14 ONNX (`models/video/gend_clip_l14.onnx`) and SBI CNN fallback.
  - Voice-clone detector (`src/satyapan/voice/detector.py`, `rules.py`, `upload.py`) using `Gustking/wav2vec2-large-xlsr-deepfake-audio-classification` ONNX (`extension/models/model.onnx` + `logreg_prob.onnx`).
- **What is missing**:
  - Whole-image AI-generated content detection (for diffusion/GAN images that may not contain a face swap, or full synthetic scenes) combining CLIP ViT-L/14 vision features (`models/video/gend_clip_l14.onnx` / spectral radial power & high-frequency residual statistics + chroma-spatial correlation) with a calibrated classifier head.
  - Unified forensic wrapper that runs:
    - Image: face-swap check (GenD) + whole-image synthetic check;
    - Video: per-frame / per-window trajectory + aggregate score + lip-sync / rPPG / lighting breakdown;
    - Audio: 5s window trajectory + aggregate voice-clone score;
  - All outputs expressed in forensic examiner language (`"consistent with synthetic generation"`, `"consistent with authentic capture"`, `"inconclusive"`) with calibrated confidence and explicit limitations.
- **Measurable target**:
  - Calibrate thresholds on a validation split; report held-out test AUC, TPR, and FPR (with 95% Wilson/bootstrap CIs) plus compression-robustness (re-encoded JPEG Q60) in `results/EVIDENCE_LEDGER.md`.

### M3 — Tampering & Manipulation Detection (`src/satyapan/forensics/tamper.py`)
- **What exists**:
  - `~/Desktop/igdtu/pramaan/ai/image_model.py`: basic 128×128 ELA image computation.
  - `src/satyapan/document/checker.py`, `pdf.py`: PDF incremental update / Producer-Creator / font & bank detail tampering checks.
- **What is missing**:
  - **Image Tampering Suite** (with PNG heatmap generation for the dashboard and PDF report):
    1. *Error Level Analysis (ELA)*: multi-scale JPEG re-compression residual grid, regional patch Z-score localization, and colorized heatmap overlay;
    2. *Double-JPEG / Quantization-Table & DCT Histogram Analysis*: JPEG quantization table inspection (standard vs non-standard/Noticeable re-save) and 8×8 DCT coefficient histogram periodicity / blocking artifact grid inconsistency;
    3. *Copy-Move Forgery Detection*: overlapping block DCT/PCA descriptor matching + ORB keypoint matching with RANSAC/spatial shift vector clustering to detect cloned regions within the same image, producing a displacement heatmap;
    4. *Noise-Residual Inconsistency*: high-pass / wavelet denoising residual local variance map across image blocks to spot spliced or AI-inpainted regions whose sensor noise floor differs from the background.
  - **Video Tampering Suite**:
    1. *Duplicated & Dropped Frame Detection*: inter-frame structural similarity / MSE & optical-flow velocity spikes to flag frozen/duplicated frames or abrupt frame deletions, plus PTS/DTS timestamp jitter check;
    2. *Re-encoding & GOP Consistency Signs*: bitrate/frame-size periodicity and macroblock boundary strength shifts indicative of segment splicing or re-encoding.
  - **Audio Tampering Suite**:
    1. *Splice & Discontinuity Detection*: short-time spectral flux spikes, phase/waveform discontinuity at cut points, and background noise-floor / crest-factor step changes across segments, with a rendered spectrogram & splice-marker image.
- **Measurable target**:
  - Evaluate each detector (Image ELA, Double-JPEG, Copy-Move, Noise-Residual, Combined Image Tamper; Video Frame-Drop/Dup; Audio Splice) on a reproducible, seeded tamper benchmark (`research/forensics/eval_tampering.py`) with AUC, TPR, FPR, and localization accuracy logged in `results/EVIDENCE_LEDGER.md`.

### M4 — Provenance & Source Attribution (`src/satyapan/forensics/provenance.py`)
- **What exists**:
  - Basic EXIF tag reading in `pramaan/parsers/image_meta.py` and PDF metadata reading in `src/satyapan/document/pdf.py`.
- **What is missing**:
  - Deep EXIF / XMP / PNG-chunk / container metadata parser and consistency verifier:
    - Timestamp chronology (`DateTimeOriginal`, `DateTimeDigitized`, `DateTime`, XMP `ModifyDate`/`CreateDate`);
    - Software/generator signature detection (editing tools + generative AI metadata in EXIF/XMP/PNG `tEXt`/`iTXt` parameters);
    - GPS coordinate sanity check (valid lat/lon bounds, null-island `0,0` flag, timestamp consistency);
    - Embedded EXIF APP1 thumbnail extraction and structural comparison against the main image (catches cropped/spliced images whose original thumbnail was not updated).
  - C2PA Content Credentials / JUMBF (`c2pa` box) parser and signature/manifest validator (checks `c2pa-python` installation; also implements a pure-Python ISO BMFF / JPEG APP11 JUMBF `c2pa` superbox detector and manifest inspector).
  - Compression-fingerprint source attribution classifier: uses JPEG quantization tables, chroma subsampling (`4:4:4` vs `4:2:0`), resolution clamping (e.g., 1600px/1280px long-edge), Huffman table structure, and metadata survival to attribute an image to `camera_original`, `messaging_reencode` (WhatsApp/Instagram-style), or `editing_software`.
- **Measurable target**:
  - Measure metadata consistency detection rate and 3-class compression-fingerprint attribution accuracy / confusion matrix on a seeded multi-source image benchmark (`research/forensics/eval_provenance.py`) and record in `results/EVIDENCE_LEDGER.md`.

### M5 — Explainable Forensic Dashboard (`src/satyapan/api/routes_forensics.py`)
- **What exists**:
  - FastAPI server (`src/satyapan/api/app.py`) and Pramaan's offline D3 workstation design (`pramaan/ui/static/index.html`).
- **What is missing**:
  - A dedicated, self-contained, offline **Multimedia Forensic Workstation** at `/forensics` (with REST endpoints under `/api/forensics/`):
    - Case creation, file upload / demo-case loader, and read-only locker status banner;
    - File list with SHA-256, source attribution badge, overall forensic assessment (`Consistent with Manipulation/Synthetic`, `Requires Examiner Verification`, `Consistent with Authentic Media`), and confidence;
    - Per-check explainability cards (Deepfake, ELA, Copy-Move, Noise Residual, Double-JPEG, Video Frame Analysis, Audio Splice, Metadata & C2PA, Compression Attribution) with visual heatmaps/spectrograms, confidence bars, plain-English + technical `"Why"` explanations;
    - Unified chronological timeline (EXIF creation, edits, intake, custody events, temporal frame/audio anomalies);
    - Signed Custody Chain & RFC 6962 Merkle Audit Path inspector + interactive **Tamper Simulator**;
    - Dedicated **"Limits of This Analysis"** panel and one-click PDF/HTML/JSON report download.
- **Measurable target**:
  - Automated API & UI tests verifying every panel, heatmap endpoint, custody verification, tamper simulation/restore, and strict offline operation.

### M6 — Automated Forensic Report & Section 63 Certificate (`src/satyapan/forensics/report.py`)
- **What exists**:
  - `~/Desktop/igdtu/pramaan/report/section63.py` (BSA 2023 Section 63 Parts A & B draft certificate) and `pramaan/report/build.py`.
- **What is missing**:
  - Pure-Python, zero-external-dependency PDF + HTML + Markdown + JSON forensic report generator (works with Pillow/internal PDF composer even when `reportlab` is not installed, and supports embedded heatmap images, tables, SHA-256 schedules, custody logs, methodology, per-finding visual evidence, limitations, examiner sign-off block, and Section 63 BSA 2023 Parts A & B certificate).
- **Measurable target**:
  - Byte-reproducible JSON/Markdown report when given a fixed timestamp, valid multi-page PDF with embedded heatmaps, verified by golden-file and structural tests.

### M7 — Comprehensive Tests & Adversarial Red-Team (`tests/forensics/`, `research/forensics/eval_adversarial.py`)
- **What is missing**:
  - Unit tests for every forensic module (`locker`, `deepfake`, `tamper`, `provenance`, `pipeline`, `report`, `api`);
  - Golden-file tests for the forensic report and Section 63 certificate;
  - End-to-end test (`intake -> working copy -> deepfake + tamper + provenance -> dashboard -> PDF/MD/JSON report`) on a committed demo kit (`demo_kit/`) of open/synthetic media;
  - Adversarial red-team benchmark measuring detector degradation under JPEG re-encode, resize, crop, Gaussian noise, and metadata stripping, recorded in `results/EVIDENCE_LEDGER.md`.

### M8 — Offline Packaging, One-Command Demo & Judge Handbooks
- **What is missing**:
  - `Dockerfile` and `docker-compose.yml` for one-command offline container deployment, plus native non-Docker `make demo` target;
  - Updated `docs/JUDGES.md` mapping every PS deliverable to exact files, endpoints, and measured numbers;
  - `docs/LIMITS.md` documenting all known failure modes honestly;
  - `docs/explain/<module>.md` for team handoff (simple English, core idea, 5 hardest judge Q&As, weaknesses).
