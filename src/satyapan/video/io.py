"""Read frames (and, when possible, audio) from a video file handed to Satya.

OpenCV comes with mediapipe (the `video` extra) and decodes MP4/MOV/WebM/MKV on every
platform. Audio for lip-sync uses PyAV when installed; without it the lip-sync cue abstains.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from satyapan.video.features import ANALYSIS_FPS

MAX_FILE_SECONDS = 30.0  # 9 windows; keeps a dropped file to ~10-15 s of CPU


def iter_frames(path: Path, max_s: float = MAX_FILE_SECONDS) -> Iterator[tuple[float, np.ndarray]]:
    """(t seconds, RGB uint8) at ~ANALYSIS_FPS. Raises ValueError if nothing decodes."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("cannot open the video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if not 1.0 <= fps <= 240.0:
        fps = 25.0
    stride = max(1, int(round(fps / ANALYSIS_FPS)))
    i = 0
    got = 0
    try:
        while i / fps <= max_s:
            if i % stride == 0:
                ok, bgr = cap.read()
                if not ok:
                    break
                got += 1
                yield i / fps, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            elif not cap.grab():
                break
            i += 1
    finally:
        cap.release()
    if got == 0:
        raise ValueError("no video frames could be decoded")


def read_audio(path: Path, sr: int = 16000, max_s: float = MAX_FILE_SECONDS) -> np.ndarray | None:
    """Mono float32 audio, or None (no audio track, or PyAV not installed)."""
    try:
        import av
    except ImportError:
        return None
    try:
        with av.open(str(path)) as container:
            if not container.streams.audio:
                return None
            resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
            chunks = []
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
                if sum(len(c) for c in chunks) >= max_s * sr:
                    break
            return np.concatenate(chunks).astype(np.float32) if chunks else None
    except Exception:  # noqa: BLE001 - a broken audio track only disables lip-sync
        return None


class TempVideo:
    """The upload as a temp file (OpenCV/PyAV read paths). Deleted on exit."""

    def __init__(self, data: bytes, suffix: str = ".mp4") -> None:
        self._data = data
        self._suffix = suffix
        self.path = Path()

    def __enter__(self) -> Path:
        fd, name = tempfile.mkstemp(suffix=self._suffix, prefix="satya_video_")
        with os.fdopen(fd, "wb") as fh:
            fh.write(self._data)
        self.path = Path(name)
        return self.path

    def __exit__(self, *exc: object) -> None:
        with contextlib.suppress(OSError):
            self.path.unlink()
