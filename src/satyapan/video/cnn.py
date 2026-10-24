"""Blend-artifact CNN (ONNX Runtime, CPU). Trained by research/video/train_sbi.py on real
faces and self-blended pseudo-fakes only. Output: one logit per face crop (higher = more
likely a blended/swapped face)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from satyapan.video.landmarks import VideoUnavailable, model_dir

CNN_FILE = "blend_b0.onnx"
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


class BlendScorer:
    def __init__(self, path: Path | None = None, threads: int = 2) -> None:
        path = path or model_dir() / CNN_FILE
        if not path.exists():
            raise VideoUnavailable(f"blend model missing: {path} (run `make video-models`)")
        try:
            import onnxruntime as ort
        except Exception as exc:  # noqa: BLE001
            raise VideoUnavailable(f"onnxruntime unavailable: {exc}") from exc
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self._session: Any = ort.InferenceSession(
            str(path), opts, providers=["CPUExecutionProvider"]
        )
        self._input = self._session.get_inputs()[0].name
        self.path = path

    def logits(self, crops: np.ndarray, batch: int = 16) -> np.ndarray:
        """crops: (n, 224, 224, 3) RGB uint8 -> (n,) float logits."""
        if len(crops) == 0:
            return np.zeros(0, np.float32)
        out = []
        for i in range(0, len(crops), batch):
            x = crops[i : i + batch].astype(np.float32) / 255.0
            x = ((x - _MEAN) / _STD).transpose(0, 3, 1, 2)
            out.append(self._session.run(None, {self._input: np.ascontiguousarray(x)})[0])
        return np.concatenate(out).reshape(-1).astype(np.float32)
