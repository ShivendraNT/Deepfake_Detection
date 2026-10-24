"""Python ONNX voice detector, same model as the extension. TASK T17.

Model files (model.onnx + logreg.onnx from the Pascu et al. browser-plugin repo) are NOT
committed: the repo has no license file (docs/DATA_POLICY.md). Put them in
extension/models/ locally. Install: `uv sync --extra audio`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import numpy as np


class WindowScorer(Protocol):
    model_version: str

    def score_windows(self, windows: list[Any]) -> list[float]:
        """One score in [0, 1] per 5 s window; higher = more likely synthetic."""
        ...


MODEL_DIR = Path(__file__).resolve().parents[3] / "extension" / "models"
MODEL_FILE, HEAD_FILE = "model.onnx", "logreg_prob.onnx"


class OnnxVoiceDetector:
    def __init__(
        self, model_path: Path, logreg_path: Path, model_version: str, threads: int = 2
    ) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is required for OnnxVoiceDetector: uv sync --extra audio"
            ) from exc
        self.model_version = model_version
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        cpu = ["CPUExecutionProvider"]
        self.model_session = ort.InferenceSession(str(model_path), opts, providers=cpu)
        self.logreg_session = ort.InferenceSession(str(logreg_path), opts, providers=cpu)

    def score_windows(self, windows: list[Any]) -> list[float]:
        """Score each 5-second audio window (float32 array).
        Returns probability of synthetic voice in [0.0, 1.0]."""
        scores: list[float] = []
        for w in windows:
            arr = np.asarray(w, dtype=np.float32)
            if arr.ndim == 1:
                arr = arr[np.newaxis, :]  # shape [1, N]
            input_name = self.model_session.get_inputs()[0].name
            model_out = self.model_session.run(None, {input_name: arr})[0]
            # model_out shape is [1, T, feat_dim]; mean pool over time dimension T
            pooled = np.mean(model_out, axis=1, keepdims=False)
            if pooled.ndim == 1:
                pooled = pooled[np.newaxis, :]
            logreg_input_name = self.logreg_session.get_inputs()[0].name
            logreg_out = self.logreg_session.run(
                None, {logreg_input_name: pooled.astype(np.float32)}
            )
            prob = 0.0
            found = False
            for item in logreg_out:
                if isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                    prob = float(item[0].get(1, 0.0))
                    found = True
                    break
                elif isinstance(item, np.ndarray) and item.shape[-1] == 2:
                    prob = float(item[0, 1])
                    found = True
                    break
            if not found and len(logreg_out) > 0:
                item = logreg_out[-1]
                if isinstance(item, np.ndarray):
                    prob = float(item.flatten()[-1])
                elif isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                    prob = float(item[0].get(1, 0.0))
            scores.append(float(np.clip(prob, 0.0, 1.0)))
        return scores


def load_default_detector(model_version: str, model_dir: Path = MODEL_DIR) -> OnnxVoiceDetector:
    """Satya's voice-clone model (docs/VOICE_DEEPFAKE.md): our XLS-R layer-7 + logistic
    regression re-training, in the plug-in's two-file format. FileNotFoundError if absent."""
    model, head = model_dir / MODEL_FILE, model_dir / HEAD_FILE
    for f in (model, head):
        if not f.exists():
            raise FileNotFoundError(f"voice model missing: {f} (run `make voice-models`)")
    return OnnxVoiceDetector(model, head, model_version)
