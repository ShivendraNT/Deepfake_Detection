"""Fusion: window features -> one calibrated score in [0, 1]. Numpy only.

The model is a standardised logistic regression whose weights are fitted by
research/video/fusion.py (identity-grouped cross-validation on FF++ train, never on test) and
stored as JSON in config/video_fusion.json. A missing cue (NaN) is imputed with the training
median and flagged by its own indicator, so "cue abstained" is never mistaken for "cue clean".
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "video_fusion.json"


@dataclass(frozen=True)
class FusionModel:
    features: tuple[str, ...]
    median: np.ndarray
    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray  # per feature
    missing_coef: np.ndarray  # per feature (weight of the "missing" indicator)
    intercept: float
    version: str

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> FusionModel:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            features=tuple(raw["features"]),
            median=np.array(raw["median"], float),
            mean=np.array(raw["mean"], float),
            scale=np.array(raw["scale"], float),
            coef=np.array(raw["coef"], float),
            missing_coef=np.array(raw["missing_coef"], float),
            intercept=float(raw["intercept"]),
            version=str(raw["version"]),
        )

    def design(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(x, float).reshape(-1, len(self.features))
        miss = ~np.isfinite(x)
        filled = np.where(miss, self.median, x)
        return (filled - self.mean) / self.scale, miss.astype(float)

    def score(self, x: np.ndarray) -> np.ndarray:
        z, miss = self.design(x)
        logit = z @ self.coef + miss @ self.missing_coef + self.intercept
        out: np.ndarray = 1.0 / (1.0 + np.exp(-np.clip(logit, -30, 30)))
        return out

    def contributions(self, x: np.ndarray) -> dict[str, float]:
        """Per-feature logit contribution for ONE window (checker/security view only)."""
        z, miss = self.design(x)
        parts = z[0] * self.coef + miss[0] * self.missing_coef
        return {f: float(v) for f, v in zip(self.features, parts, strict=True) if math.isfinite(v)}
