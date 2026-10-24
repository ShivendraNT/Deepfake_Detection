"""The shipped scam-text classifier: hashed TF-IDF + logistic regression (numpy only).

Trained by research/text/train.py on open datasets (docs/TEXT_BENCHMARK.md) and stored as
config/text_model.npz (sparse IDF + weights, a few MB, no text inside) with its metadata and
frozen thresholds in config/text_model.json. Output: P(scam) in [0, 1] and, for the checker
view only, the n-grams that pushed the score up.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from satyapan.textrisk.features import N_FEATURES, hashed_tf, raw_counts

CONFIG = Path(__file__).resolve().parents[3] / "config"
MODEL_PATH = CONFIG / "text_model.npz"
META_PATH = CONFIG / "text_model.json"


@dataclass(frozen=True)
class TextRiskModel:
    idf: np.ndarray  # dense (N_FEATURES,) float32; 0 = bucket never seen in training
    coef: np.ndarray  # dense (N_FEATURES,) float32
    intercept: float
    tau_hi: float  # P(scam) at 1% FPR on validation legitimate texts
    tau_lo: float  # at 5%
    version: str
    normalise: bool = True

    @classmethod
    def load(cls, path: Path = MODEL_PATH, meta_path: Path = META_PATH) -> TextRiskModel:
        z = np.load(path)
        idf = np.zeros(N_FEATURES, np.float32)
        coef = np.zeros(N_FEATURES, np.float32)
        idf[z["idf_idx"]] = z["idf_val"]
        coef[z["coef_idx"]] = z["coef_val"]
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return cls(
            idf=idf,
            coef=coef,
            intercept=float(meta["intercept"]),
            tau_hi=float(meta["thresholds"]["tau_hi"]),
            tau_lo=float(meta["thresholds"]["tau_lo"]),
            version=str(meta["version"]),
            normalise=bool(meta.get("normalise", True)),
        )

    def _vector(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        tf = hashed_tf(text, self.normalise)
        if not tf:
            return np.zeros(0, np.int64), np.zeros(0, np.float32)
        idx = np.fromiter(tf.keys(), np.int64, len(tf))
        val = np.fromiter(tf.values(), np.float32, len(tf)) * self.idf[idx]
        norm = float(np.linalg.norm(val))
        return idx, (val / norm if norm > 0 else val)

    def score(self, text: str) -> float:
        idx, val = self._vector(text)
        logit = float(val @ self.coef[idx]) + self.intercept
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, logit))))

    def top_ngrams(self, text: str, k: int = 5) -> list[str]:
        """Feature strings that raised the score most (checker/security explanation only)."""
        idx, val = self._vector(text)
        contrib = dict(zip(idx.tolist(), (val * self.coef[idx]).tolist(), strict=True))
        best: dict[str, float] = {}
        for key in raw_counts(text, self.normalise):
            from zlib import crc32

            h = crc32(key.encode("utf-8"))
            c = contrib.get(h & (N_FEATURES - 1), 0.0)
            if c > 0 and key[0] in "wb":
                best[key[1:]] = max(best.get(key[1:], 0.0), c)
        return [w for w, _ in sorted(best.items(), key=lambda kv: -kv[1])[:k]]
