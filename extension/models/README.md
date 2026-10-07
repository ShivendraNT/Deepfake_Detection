# Voice model files (not committed)

The on-device detector uses the XLS-R layer-7 ONNX model + logistic-regression head from
Pascu et al., "Audio deepfake detection in the browser" (arXiv 2606.30780), repo
`OctavianPascu97/Audio-Deepfakes-Browser-Plugin`.

- That repo has **no license file** (checked 4 Oct 2026). We email the authors on Day 1 and
  do NOT redistribute the files. Download them yourself into this folder:
  `extension/models/model.onnx` and `extension/models/logreg.onnx`.
- `*.onnx` is git-ignored.
- Backup if the license is refused: server-side scoring with a permissively licensed SSL
  detector (verify its license first) — see docs/DECISIONS.md ADR-009.
- After downloading, run once: `uv run --with onnx python scripts/prepare_ext_models.py`.
  It writes `logreg_prob.onnx` (same model without the ZipMap output, which onnxruntime-web
  cannot read). The extension loads `model.onnx` + `logreg_prob.onnx`.
