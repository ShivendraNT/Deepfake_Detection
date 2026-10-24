"""Face tracking: YuNet face detection + MediaPipe Face Landmarker (478 points), CPU only.

Wheels exist for Windows x64/arm64, Linux x64/arm64 and Apple Silicon (Intel Macs get an
older pinned release, see pyproject.toml). If the import or the model file is missing,
`VideoUnavailable` is raised and Satya reports the video check as unavailable; nothing else
changes.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

MODEL_DIR_ENV = "SATYAPAN_VIDEO_MODELS"
LANDMARKER_FILE = "face_landmarker.task"
DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
DETECT_SIDE = 640  # YuNet sees the frame at most this big (small faces stay >= ~10 px)
ROI_FROM_BOX = 2.0  # crop side / YuNet face box (the box is tight on the face)
ROI_FROM_LANDMARKS = 1.7  # crop side / landmark extent (forehead to chin)
CROP_MAX = 384.0  # the landmarker never needs more than this


class VideoUnavailable(RuntimeError):
    """The video check cannot run on this machine (missing package or model file)."""


def model_dir() -> Path:
    env = os.environ.get(MODEL_DIR_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "models" / "video"


@dataclass(frozen=True)
class FaceObs:
    """One tracked face in one frame. pts are pixel coordinates (x, y) of the 478 points."""

    pts: np.ndarray
    jaw_open: float


class FaceTracker:
    """Finds and follows the largest face through a stream of frames.

    Two stages, because MediaPipe's own detector is the short-range BlazeFace (128 px input,
    made for selfie framing) and misses the small faces of a call grid or a 1080p frame:

    1. YuNet (OpenCV, MIT; works on a <= 640 px copy of the frame) finds the largest face
       when we are not tracking one.
    2. The Face Landmarker runs on a square crop centred on that face (the face fills about
       half of it), and the crop follows the landmarks from frame to frame. If the face is
       lost, YuNet looks again on the same frame.
    """

    def __init__(
        self,
        model_path: Path | None = None,
        max_faces: int = 1,
        still_images: bool = False,
        detector_path: Path | None = None,
    ) -> None:
        del max_faces, still_images  # kept for callers; every crop is analysed on its own
        path = model_path or model_dir() / LANDMARKER_FILE
        det = detector_path or model_dir() / DETECTOR_FILE
        for f in (path, det):
            if not f.exists():
                raise VideoUnavailable(f"face model missing: {f} (run `make video-models`)")
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except Exception as exc:  # noqa: BLE001 - ImportError or a missing system library
            raise VideoUnavailable(f"mediapipe unavailable: {exc}") from exc
        self._mp = mp
        self._cv2 = cv2
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            output_face_blendshapes=True,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
        )
        self._landmarker: Any = vision.FaceLandmarker.create_from_options(options)
        self._yunet: Any = cv2.FaceDetectorYN.create(str(det), "", (320, 320), 0.6, 0.3, 50)
        self._roi: tuple[float, float, float] | None = None  # (cx, cy, side) in frame pixels

    def _detect(self, frame: np.ndarray) -> tuple[float, float, float] | None:
        """ROI (cx, cy, side) around the largest YuNet face, or None."""
        h, w = frame.shape[:2]
        scale = min(1.0, DETECT_SIDE / max(h, w))
        small = (
            frame
            if scale == 1.0
            else self._cv2.resize(
                frame,
                (max(1, round(w * scale)), max(1, round(h * scale))),
                interpolation=self._cv2.INTER_AREA,
            )
        )
        sh, sw = small.shape[:2]
        self._yunet.setInputSize((sw, sh))
        _, faces = self._yunet.detect(self._cv2.cvtColor(small, self._cv2.COLOR_RGB2BGR))
        if faces is None or len(faces) == 0:
            return None
        x, y, bw, bh = max(faces, key=lambda f: float(f[2] * f[3]))[:4] / scale
        return float(x + bw / 2), float(y + bh / 2), float(max(bw, bh) * ROI_FROM_BOX)

    def _landmarks(self, frame: np.ndarray, roi: tuple[float, float, float]) -> FaceObs | None:
        cx, cy, side = roi
        size = int(min(CROP_MAX, max(64.0, side)))
        k = size / side
        m = np.array(
            [[k, 0.0, -(cx - side / 2) * k], [0.0, k, -(cy - side / 2) * k]], dtype=np.float32
        )
        crop = self._cv2.warpAffine(
            frame,
            m,
            (size, size),
            flags=self._cv2.INTER_LINEAR,
            borderMode=self._cv2.BORDER_CONSTANT,
        )
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop)
        )
        result = self._landmarker.detect(image)
        if not result.face_landmarks:
            return None
        lms = result.face_landmarks[0]
        pts = np.array([(p.x * size, p.y * size) for p in lms], dtype=np.float32)
        pts = (pts - m[:, 2]) / k  # back to frame pixels
        jaw = 0.0
        if result.face_blendshapes:
            for cat in result.face_blendshapes[0]:
                if cat.category_name == "jawOpen":
                    jaw = float(cat.score)
                    break
        return FaceObs(pts=pts, jaw_open=jaw)

    def track(self, frame_rgb: np.ndarray, t_s: float) -> FaceObs | None:
        """Landmarks of the largest face in an RGB uint8 frame, or None."""
        del t_s  # every frame is analysed on its own crop; no internal clock
        obs = self._landmarks(frame_rgb, self._roi) if self._roi is not None else None
        if obs is None:
            self._roi = self._detect(frame_rgb)
            if self._roi is None:
                return None
            obs = self._landmarks(frame_rgb, self._roi)
            if obs is None:
                self._roi = None
                return None
        x0, y0 = obs.pts.min(axis=0)
        x1, y1 = obs.pts.max(axis=0)
        self._roi = (
            float(x0 + x1) / 2,
            float(y0 + y1) / 2,
            float(max(x1 - x0, y1 - y0) * ROI_FROM_LANDMARKS),
        )
        return obs

    def close(self) -> None:
        # Closing twice, or at interpreter exit, is harmless.
        with contextlib.suppress(Exception):
            self._landmarker.close()

    def __enter__(self) -> FaceTracker:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
