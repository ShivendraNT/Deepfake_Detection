"""Shared fixtures for the Forensic Lab tests: synthetic media made in memory and a model
registry stub (no model files, no network). Tests that need the real models are marked
`lab_models` and skip when the files are not installed."""

from __future__ import annotations

import io
import math
import threading
import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from satyapan.forensics.base import Unavailable


class StubModels:
    """Every model is unavailable; analyses must still complete and say so."""

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}

    def get(self, name: str) -> Any:
        raise Unavailable(f"{name} not installed (test stub)")

    def lock(self, name: str) -> threading.Lock:
        return self._locks.setdefault(name, threading.Lock())

    def status(self) -> dict[str, dict[str, Any]]:
        return {"stub": {"available": False, "purpose": "tests"}}


@pytest.fixture
def stub_models() -> StubModels:
    return StubModels()


def textured(w: int = 640, h: int = 480, seed: int = 0) -> np.ndarray:
    """A natural-looking random image: smooth gradients + blobs + fine noise."""
    import cv2

    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, (h // 8, w // 8, 3)).astype(np.float32)
    base = cv2.resize(base, (w, h), interpolation=cv2.INTER_CUBIC)
    yy, xx = np.mgrid[0:h, 0:w]
    grad = np.stack([xx / w, yy / h, (xx + yy) / (w + h)], axis=2).astype(np.float32)
    detail = rng.normal(0, 1, (h, w, 3)).astype(np.float32)
    img = 110 + 60 * grad + 35 * base + 6 * detail
    for _ in range(25):
        cx, cy, r = rng.integers(0, w), rng.integers(0, h), rng.integers(8, 40)
        cv2.circle(
            img, (int(cx), int(cy)), int(r), [float(v) for v in rng.integers(20, 235, 3)], -1
        )
    return np.clip(img, 0, 255).astype(np.uint8)


def jpeg(arr: np.ndarray, q: int = 90, **kw: Any) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=q, **kw)
    return buf.getvalue()


def png(arr: np.ndarray, **kw: Any) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG", **kw)
    return buf.getvalue()


def wav(x: np.ndarray, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def tone_speechlike(seconds: float, sr: int = 16000, seed: int = 0) -> np.ndarray:
    """Amplitude-modulated harmonic signal with pauses (speech-like energy envelope)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    f0 = 140 + 20 * np.sin(2 * math.pi * 0.7 * t)
    ph = 2 * math.pi * np.cumsum(f0) / sr
    x = sum(np.sin(k * ph) / k for k in range(1, 8))
    env = (np.sin(2 * math.pi * 3 * t) > -0.2).astype(np.float32) * (
        np.sin(2 * math.pi * 0.25 * t) > -0.6
    )
    return (0.25 * x * env + 0.003 * rng.normal(0, 1, len(t))).astype(np.float32)


@pytest.fixture
def tmp_lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SATYAPAN_LAB_DIR", str(tmp_path / "lab"))
    return tmp_path / "lab"


def exif_with_thumbnail(thumb_jpeg: bytes, make: str = "Nikon") -> bytes:
    """A minimal little-endian EXIF block (IFD0: Make; IFD1: an embedded JPEG thumbnail), the
    way cameras write it. Pillow cannot write IFD1 thumbnails itself."""
    import struct

    s = make.encode() + b"\x00"
    ifd0_off, str_off = 8, 26
    ifd1_off = str_off + len(s)
    th_off = ifd1_off + 2 + 12 * 2 + 4
    t = bytearray(b"II*\x00" + struct.pack("<I", ifd0_off))
    t += struct.pack("<H", 1) + struct.pack("<HHII", 0x010F, 2, len(s), str_off)
    t += struct.pack("<I", ifd1_off) + s
    t += struct.pack("<H", 2) + struct.pack("<HHII", 0x0201, 4, 1, th_off)
    t += struct.pack("<HHII", 0x0202, 4, 1, len(thumb_jpeg)) + struct.pack("<I", 0)
    return b"Exif\x00\x00" + bytes(t + thumb_jpeg)
