# Third-party models, code and data

Everything in Satya that the team did not write, with its licence and where it comes from.
The full data table (what we may and may not do with each set) is in
[`docs/DATA_POLICY.md`](docs/DATA_POLICY.md); pinned revisions and sha256 are in `config/*.json`
and `results/*_manifest.json`.

## Models the product runs

None of these is committed. They are downloaded or built on the laptop, and their sha256 is
checked before use (`scripts/video_models.py`, `research/voice/export.py`).

| Model | Used for | Licence | Source, and how it gets onto a laptop |
|---|---|---|---|
| GenD CLIP ViT-L/14 (Yermakov et al., WACV 2026) | face swap in photos and video | MIT (backbone OpenAI CLIP, MIT) | `yermandy/GenD_CLIP_L_14`, exported to ONNX by `research/video/export_gend.py` |
| `Gustking/wav2vec2-large-xlsr-deepfake-audio-classification` @ `f7050b5` | voice clone | Apache-2.0 | exported to ONNX by `research/voice/export.py` (`make voice`) |
| YuNet `face_detection_yunet_2023mar` | finding small faces | MIT (OpenCV Zoo) | `make video` |
| MediaPipe Face Landmarker | face landmarks | Apache-2.0 | `make video` |
| PaddleOCR `en_PP-OCRv3` recogniser (ONNX by RapidOCR) | text in screenshots | Apache-2.0 | `make video` |
| Whisper (faster-whisper, mlx-whisper on Apple Silicon) | speech to text, on the device | MIT | `make asr` |

Which external model ships was decided by rules fixed before testing, and our own models are
compared under the same rules. Our voice model lost to Gustking; GenD beat our face CNN.
See `docs/VIDEO_DEEPFAKE.md` and `docs/VOICE_DEEPFAKE.md`.

**Trained by us:**
- the scam-text model `config/text_model.*`, a hashed TF-IDF with logistic regression, trained on
  the open sets listed in that file;
- the fallback face CNN `blend_b0.onnx`, trained on FaceForensics++ real videos only; under
  the FF++ terms it is not hosted here;
- our XLS-R voice head, a candidate that was not shipped.

## Code copied into this repo

| Files | What | Licence |
|---|---|---|
| `extension/vendor/*`, `desktop/renderer/src/capture/vendor/ort.wasm.min.mjs` | onnxruntime-web 1.20.1 (Microsoft) | MIT, with a `LICENSE` file next to the copy |

Nothing else is copied. Libraries are installed from PyPI and npm, pinned in `uv.lock`,
`desktop/package-lock.json` and `console/package-lock.json`.

## Methods from papers (their idea, our code)

| Our module | Paper |
|---|---|
| `research/video/sbi.py`, `research/video/train_sbi.py` | Self-Blended Images (Shiohara & Yamasaki, CVPR 2022), adapted |
| `src/satyapan/video/rppg.py` | POS remote photoplethysmography (Wang et al. 2017) |
| `src/satyapan/video/lighting.py` | corneal specular highlights (Hu et al. 2021) |
| `research/voice/models.py` (`satya_xlsr_l7`) | XLS-R mid-layer features + logistic regression (Pascu et al.), re-trained on licensed data; their unlicensed ONNX files are not used |

## Data

Data is used only for training and benchmarks. None of it is committed (`docs/DATA_POLICY.md`).
- Video: FaceForensics++ c23, DFDC.
- Voice: In-the-Wild, ASVspoof 2019 LA.
- Text: seven open sets (phishing e-mail, fraud e-mail, SMS spam, Indian SMS, Hinglish scam
  calls, scam dialogue, 14-language scam/ham).

The demo data in `data/demo/` is synthetic: IFSC `FAK…`, accounts `9999…`, domains `*.example`.

## AI coding assistants

The team wrote this code with AI coding assistants, under the rules in `AGENTS.md`. Commits
made with an assistant carry a `Co-Authored-By` trailer. Every change is gated by the tests in
`make check`.
