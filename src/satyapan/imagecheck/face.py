"""Face check on a still image (photo, profile picture, a frame of a call).

The face is found and cropped exactly as in the video check (YuNet + MediaPipe landmarks,
1.3x box, 224 px) and scored by the shipped face CNN (GenD, config/video_models.json). One
crop is not a 6 s window, so the operating point is its own: config/image_face_thresholds.json
(1% / 5% FPR over single crops of FF++ val real videos; research/video/image_eval.py).
Output is a label for the policy table; the logit goes to the checker view only.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.contracts.enums import ReasonCode, SignalSource
from satyapan.contracts.evidence import Signal

CONFIG = Path(__file__).resolve().parents[3] / "config" / "image_face_thresholds.json"
MIN_FACE_PX = 64.0  # the video check's coverage gate
MAX_SIDE = 1920  # larger photos are downscaled first (faster, same face size class)


@dataclass(frozen=True)
class ImageFaceThresholds:
    tau_hi: float  # logit at 1% FPR on single val real crops
    tau_lo: float  # 5%
    model_file: str
    calibrated: bool

    @classmethod
    def load(cls, path: Path = CONFIG) -> ImageFaceThresholds:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            tau_hi=float(raw["tau_hi_logit"]),
            tau_lo=float(raw["tau_lo_logit"]),
            model_file=str(raw["model"]),
            calibrated=bool(raw.get("calibrated", False)),
        )


@dataclass(frozen=True)
class ImageFaceVerdict:
    code: ReasonCode
    logit: float | None
    face_px: float | None
    problem: str | None


def decode_image(data: bytes) -> np.ndarray:
    """Any common image format -> RGB uint8. ValueError if it does not decode."""
    from PIL import Image, ImageOps

    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - PIL raises many types
        raise ValueError(f"not a readable image: {exc}") from exc
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    return np.asarray(img, dtype=np.uint8)


class ImageFaceChecker:
    def __init__(self, scorer: Any, thresholds: ImageFaceThresholds, tracker_factory: Any) -> None:
        self.scorer = scorer
        self.thresholds = thresholds
        self.tracker_factory = tracker_factory

    @classmethod
    def load(cls) -> ImageFaceChecker:
        """Needs the video extra and the selected face CNN file; VideoUnavailable otherwise."""
        from satyapan.video.cnn import BlendScorer
        from satyapan.video.landmarks import FaceTracker, VideoUnavailable, model_dir

        try:
            thr = ImageFaceThresholds.load()
        except FileNotFoundError as exc:
            raise VideoUnavailable(f"image thresholds missing: {exc.filename}") from exc
        path = model_dir() / thr.model_file
        if not path.exists():
            raise VideoUnavailable(f"{thr.model_file} missing in {model_dir()} (photo check off)")
        FaceTracker().close()
        return cls(BlendScorer(path), thr, FaceTracker)

    def check(self, rgb: np.ndarray) -> ImageFaceVerdict:
        from satyapan.video.observe import face_crop

        tracker = self.tracker_factory()
        try:
            obs = tracker.track(rgb, 0.0)
        finally:
            tracker.close()
        if obs is None:
            return ImageFaceVerdict(ReasonCode.IMAGE_FACE_INCONCLUSIVE, None, None, "no_face")
        pts = np.asarray(obs.pts)
        face_px = float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
        if face_px < MIN_FACE_PX:
            return ImageFaceVerdict(
                ReasonCode.IMAGE_FACE_INCONCLUSIVE, None, face_px, "face_too_small"
            )
        logit = float(self.scorer.logits(face_crop(rgb, pts)[None])[0])
        if logit >= self.thresholds.tau_hi:
            code = ReasonCode.IMAGE_FACE_LIKELY_SYNTHETIC
        elif logit >= self.thresholds.tau_lo:
            code = ReasonCode.IMAGE_FACE_INCONCLUSIVE
        else:
            code = ReasonCode.IMAGE_FACE_NO_SIGNS
        return ImageFaceVerdict(code, logit, face_px, None)


def image_face_signal(verdict: ImageFaceVerdict, checker: ImageFaceChecker, ev_id: str) -> Signal:
    return Signal.make(
        verdict.code,
        source=SignalSource.ML,
        evidence_ids=[ev_id],
        detector=f"image_face@{checker.thresholds.model_file}",
        score=verdict.logit,
        detail={
            "face_px": verdict.face_px,
            "problem": verdict.problem,
            "calibrated": checker.thresholds.calibrated,
        },
    )
