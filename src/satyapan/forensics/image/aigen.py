"""AI-generated image classifier (ONNX Runtime, CPU).

Which model runs, how its input is prepared and its operating thresholds are all in
config/aigen_model.json, written by research/forensics/aigen_select.py after comparing the
candidates on a validation split (selection and thresholds on validation only; the test
split is scored once). The ONNX file itself is built by `make forensics-models`.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np


class AiImageModel:
    def __init__(self, path: Path, spec: dict[str, Any]) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 3
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        self.spec = spec
        self.size = int(spec.get("size", 224))
        self.mean = np.array(spec.get("mean", [0.5, 0.5, 0.5]), np.float32)
        self.std = np.array(spec.get("std", [0.5, 0.5, 0.5]), np.float32)
        self.fake_index = int(spec.get("fake_index", 1))
        self.resize = str(spec.get("resize", "squash"))  # squash | shortest_crop
        self._lock = threading.Lock()

    def _prep(self, img: Any) -> np.ndarray:
        from PIL import Image

        img = img.convert("RGB")
        s = self.size
        if self.resize == "shortest_crop":
            w, h = img.size
            k = int(self.spec.get("pre_resize", s)) / min(w, h)
            img = img.resize((max(s, round(w * k)), max(s, round(h * k))), Image.BICUBIC)  # fmt: skip
            w, h = img.size
            left, top = (w - s) // 2, (h - s) // 2
            img = img.crop((left, top, left + s, top + s))
        else:
            img = img.resize((s, s), Image.BICUBIC)
        x = np.asarray(img, dtype=np.float32) / 255.0
        return ((x - self.mean) / self.std).transpose(2, 0, 1)

    def views(self, img: Any) -> list[Any]:
        """The whole picture plus, for large images, a centre crop at native scale (the
        resolution where generator fingerprints live)."""
        out = [img]
        w, h = img.size
        if min(w, h) >= 2 * self.size:
            side = min(w, h) // 2
            left, top = (w - side) // 2, (h - side) // 2
            out.append(img.crop((left, top, left + side, top + side)))
        return out

    def logit(self, img: Any) -> tuple[float, list[float]]:
        """Fake-logit (log-odds of AI-generated) averaged over views, and per-view values."""
        batch = np.stack([self._prep(v) for v in self.views(img)])
        with self._lock:
            out = self.session.run(None, {self.input: np.ascontiguousarray(batch)})[0]
        out = np.asarray(out, dtype=np.float64)
        if out.ndim == 2 and out.shape[1] >= 2:
            lse = np.log(np.exp(out - out.max(axis=1, keepdims=True)).sum(axis=1)) + out.max(axis=1)
            logp_fake = out[:, self.fake_index] - lse
            p = np.exp(logp_fake)
            lg = np.log(np.clip(p, 1e-9, 1 - 1e-9)) - np.log(np.clip(1 - p, 1e-9, 1))
        else:
            lg = out.reshape(-1)
        vals = [float(v) for v in lg]
        return float(np.mean(vals)), vals
