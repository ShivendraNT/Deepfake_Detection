"""Face tracking: MediaPipe Face Landmarker (478 points), CPU only, fully on-device.

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
    """Tracks the largest face through a stream of frames (timestamps must increase)."""

    def __init__(
        self, model_path: Path | None = None, max_faces: int = 3, still_images: bool = False
    ) -> None:
        path = model_path or model_dir() / LANDMARKER_FILE
        if not path.exists():
            raise VideoUnavailable(f"face model missing: {path} (run `make video-models`)")
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except Exception as exc:  # noqa: BLE001 - ImportError or a missing system library
            raise VideoUnavailable(f"mediapipe unavailable: {exc}") from exc
        self._mp = mp
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE if still_images else vision.RunningMode.VIDEO,
            num_faces=max_faces,
            output_face_blendshapes=True,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker: Any = vision.FaceLandmarker.create_from_options(options)
        self._still = still_images
        self._last_ms = -1

    def track(self, frame_rgb: np.ndarray, t_s: float) -> FaceObs | None:
        """Landmarks of the largest face in an RGB uint8 frame, or None."""
        t_ms = max(int(round(t_s * 1000)), self._last_ms + 1)
        self._last_ms = t_ms
        h, w = frame_rgb.shape[:2]
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb)
        )
        if self._still:
            result = self._landmarker.detect(image)
        else:
            result = self._landmarker.detect_for_video(image, t_ms)
        if not result.face_landmarks:
            return None
        best: tuple[float, int] | None = None
        all_pts = []
        for i, lms in enumerate(result.face_landmarks):
            pts = np.array([(p.x * w, p.y * h) for p in lms], dtype=np.float32)
            all_pts.append(pts)
            area = float(np.ptp(pts[:, 0]) * np.ptp(pts[:, 1]))
            if best is None or area > best[0]:
                best = (area, i)
        assert best is not None
        idx = best[1]
        jaw = 0.0
        if result.face_blendshapes and idx < len(result.face_blendshapes):
            for cat in result.face_blendshapes[idx]:
                if cat.category_name == "jawOpen":
                    jaw = float(cat.score)
                    break
        return FaceObs(pts=all_pts[idx], jaw_open=jaw)

    def close(self) -> None:
        # Closing twice, or at interpreter exit, is harmless.
        with contextlib.suppress(Exception):
            self._landmarker.close()

    def __enter__(self) -> FaceTracker:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
