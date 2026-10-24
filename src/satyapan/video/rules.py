"""Video window rule: scores -> label -> Signal. Mirrors satyapan.voice.rules.

- LIKELY_SYNTHETIC if >= 2 CONSECUTIVE usable windows have a fused score >= tau_hi
  (tau_hi = 1% window false-positive rate on validation reals, config/video_thresholds.json)
- INCONCLUSIVE if any usable window is >= tau_lo (5% FPR), or no window had a usable face
- NO_SIGNS otherwise
A window without a usable face (camera off, face too small or dark) abstains and breaks a run.
It is never a finding on its own: no grey flag, no band change (a camera can just be off).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from satyapan.contracts.enums import ReasonCode, SignalSource, VideoLabel
from satyapan.contracts.evidence import Signal

MIN_CONSECUTIVE = 2
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "video_thresholds.json"


@dataclass(frozen=True)
class VideoThresholds:
    tau_hi: float  # fused score at 1% window FPR on validation reals
    tau_lo: float  # at 5%
    model_version: str
    calibrated: bool = False  # True only after calibration on consented webcam calls
    calibration_set: str = ""
    cue_flag_logit: float = 0.75  # a cue "looked unusual" if it adds >= this to the logit
    extra: dict[str, object] = field(default_factory=dict)


def load_thresholds(path: Path = DEFAULT_PATH) -> VideoThresholds:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return VideoThresholds(
        tau_hi=float(raw["tau_hi"]),
        tau_lo=float(raw["tau_lo"]),
        model_version=str(raw["model_version"]),
        calibrated=bool(raw.get("calibrated", False)),
        calibration_set=str(raw.get("calibration_set", "")),
        cue_flag_logit=float(raw.get("cue_flag_logit", 0.75)),
    )


@dataclass(frozen=True)
class VideoVerdict:
    label: VideoLabel
    max_consecutive_over_hi: int
    windows: int
    usable_windows: int
    max_score: float
    problem: str | None = None


def classify_windows(
    scores: Sequence[float | None],
    thresholds: VideoThresholds,
    problems: Sequence[str | None] = (),
    min_consecutive: int = MIN_CONSECUTIVE,
) -> VideoVerdict:
    """scores[i] is None when window i abstained (no usable face)."""
    if not 0.0 <= thresholds.tau_lo <= thresholds.tau_hi <= 1.0:
        raise ValueError("need 0 <= tau_lo <= tau_hi <= 1")
    run = best = 0
    usable = [s for s in scores if s is not None]
    for s in scores:
        run = run + 1 if s is not None and s >= thresholds.tau_hi else 0
        best = max(best, run)
    problem = None
    if not usable:
        known = [p for p in problems if p]
        problem = max(set(known), key=known.count) if known else "no_face"
    if best >= min_consecutive:
        label = VideoLabel.LIKELY_SYNTHETIC
    elif not usable or any(s >= thresholds.tau_lo for s in usable):
        label = VideoLabel.INCONCLUSIVE
    else:
        label = VideoLabel.NO_SIGNS
    return VideoVerdict(
        label=label,
        max_consecutive_over_hi=best,
        windows=len(scores),
        usable_windows=len(usable),
        max_score=max(usable, default=0.0),
        problem=problem,
    )


_LABEL_TO_CODE = {
    VideoLabel.LIKELY_SYNTHETIC: ReasonCode.VIDEO_LIKELY_SYNTHETIC,
    VideoLabel.INCONCLUSIVE: ReasonCode.VIDEO_INCONCLUSIVE,
    VideoLabel.NO_SIGNS: ReasonCode.VIDEO_NO_SIGNS,
}
VIDEO_CODES = frozenset(_LABEL_TO_CODE.values())


def video_signal(
    verdict: VideoVerdict,
    thresholds: VideoThresholds,
    evidence_ids: list[str],
    cues: Sequence[str] = (),
    detector: str = "video_fusion",
) -> Signal:
    return Signal.make(
        _LABEL_TO_CODE[verdict.label],
        source=SignalSource.ML,
        evidence_ids=evidence_ids,
        detector=f"{detector}@{thresholds.model_version}",
        score=verdict.max_score,
        detail={
            "windows": verdict.windows,
            "usable_windows": verdict.usable_windows,
            "consecutive_over_hi": verdict.max_consecutive_over_hi,
            "calibrated": thresholds.calibrated,
            "cues": ",".join(cues),
            "problem": verdict.problem,
        },
    )
