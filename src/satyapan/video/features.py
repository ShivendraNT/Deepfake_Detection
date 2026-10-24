"""Window features from per-frame records. Pure functions (no models, no I/O).

A window is WINDOW_S seconds of frames; consecutive windows overlap by WINDOW_S - HOP_S.
The same code runs in the benchmark (research/video/) and in Satya, so measured numbers
describe exactly what ships.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from satyapan.video.lighting import lighting_features
from satyapan.video.lipsync import lipsync_features
from satyapan.video.observe import FrameRecord
from satyapan.video.regions import PATCHES
from satyapan.video.rppg import pulse_features

WINDOW_S = 6.0
HOP_S = 3.0
ANALYSIS_FPS = 15.0
CROP_EVERY_S = 0.75

# Feature order used by the fusion model. Coverage numbers are NOT features (they describe
# capture quality, not the face, and would let a model learn dataset shortcuts).
FEATURES = (
    "blend",
    "pulse_snr",
    "pulse_coherence",
    "pulse_hr_spread",
    "light_chroma_gap",
    "light_shade_gap",
    "light_flicker",
    "light_spec_gap",
    "av_corr",
    "av_lag",
)
CUES = {
    "blend": ("blend",),
    "pulse": ("pulse_snr", "pulse_coherence", "pulse_hr_spread"),
    "light": ("light_chroma_gap", "light_shade_gap", "light_flicker", "light_spec_gap"),
    "lipsync": ("av_corr", "av_lag"),
}

# Coverage gate: below these the window abstains (no conclusion either way).
MIN_FACE_FRACTION = 0.7
MIN_FACE_PX = 64.0
MIN_SECONDS = 4.0
LUMA_RANGE = (35.0, 235.0)


@dataclass(frozen=True)
class Coverage:
    seconds: float
    frames: int
    face_fraction: float
    face_px: float
    luma: float

    @property
    def usable(self) -> bool:
        return (
            self.seconds >= MIN_SECONDS
            and self.face_fraction >= MIN_FACE_FRACTION
            and self.face_px >= MIN_FACE_PX
            and LUMA_RANGE[0] <= self.luma <= LUMA_RANGE[1]
        )

    def problem(self) -> str | None:
        if self.seconds < MIN_SECONDS:
            return "too_short"
        if self.face_fraction < MIN_FACE_FRACTION:
            return "no_face"
        if self.face_px < MIN_FACE_PX:
            return "face_too_small"
        if not LUMA_RANGE[0] <= self.luma <= LUMA_RANGE[1]:
            return "bad_lighting"
        return None


def windows(t_start: float, t_end: float) -> list[tuple[float, float]]:
    """[(start, end)] of full windows inside [t_start, t_end]."""
    out = []
    s = t_start
    while s + WINDOW_S <= t_end + 1e-6:
        out.append((s, s + WINDOW_S))
        s += HOP_S
    return out


def coverage(records: Sequence[FrameRecord]) -> Coverage:
    if not records:
        return Coverage(0.0, 0, 0.0, 0.0, 0.0)
    found = [r for r in records if r.found]
    return Coverage(
        seconds=float(records[-1].t - records[0].t) if len(records) > 1 else 0.0,
        frames=len(records),
        face_fraction=len(found) / len(records),
        face_px=float(np.median([r.face_w for r in found])) if found else 0.0,
        luma=float(np.median([r.luma for r in found])) if found else 0.0,
    )


def traces_of(records: Sequence[FrameRecord]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    t = np.array([r.t for r in records], dtype=float)
    nan3 = (float("nan"),) * 3
    traces = {
        p: np.array([r.patches.get(p, nan3) if r.found else nan3 for r in records], dtype=float)
        for p in PATCHES
    }
    return t, traces


def window_features(
    records: Sequence[FrameRecord],
    audio: np.ndarray | None = None,
    sr: int = 16000,
    audio_t0: float = 0.0,
    crop_logits: Sequence[float] | None = None,
) -> dict[str, float]:
    """All FEATURES for one window (NaN where a cue abstains)."""
    t, traces = traces_of(records)
    feats: dict[str, float] = {}
    blend = [float(x) for x in (crop_logits or []) if np.isfinite(x)]
    feats["blend"] = float(np.mean(blend)) if blend else float("nan")
    feats.update(pulse_features(t, traces, ANALYSIS_FPS))
    spec = np.array([r.spec for r in records if r.found], dtype=float).reshape(-1, 4)
    found_traces = {k: v[np.isfinite(v).all(axis=1)] for k, v in traces.items()}
    feats.update(lighting_features(found_traces, spec))
    mouth = np.array([r.mouth if r.found else np.nan for r in records], dtype=float)
    lip = lipsync_features(t - audio_t0, mouth, audio, sr, ANALYSIS_FPS)
    feats["av_corr"], feats["av_lag"] = lip["av_corr"], lip["av_lag"]
    feats["speech_frac"] = lip["speech_frac"]
    return feats


def vector(feats: dict[str, float]) -> np.ndarray:
    return np.array([feats.get(k, float("nan")) for k in FEATURES], dtype=float)
