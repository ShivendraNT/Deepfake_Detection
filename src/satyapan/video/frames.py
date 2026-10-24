"""Decode the JPEG frames the capture window posts. Pillow only (always installed)."""

from __future__ import annotations

import io

import numpy as np

MAX_FRAME_BYTES = 3 * 1024 * 1024
MAX_FRAMES_PER_POST = 64
MAX_SIDE = 1920


def decode_jpeg(data: bytes) -> np.ndarray:
    """RGB uint8 array from JPEG/PNG bytes. Raises ValueError on anything else."""
    if not data or len(data) > MAX_FRAME_BYTES:
        raise ValueError("frame missing or too large")
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError(f"unsupported frame format {img.format}")
            if max(img.size) > MAX_SIDE:
                img.thumbnail((MAX_SIDE, MAX_SIDE))
            return np.asarray(img.convert("RGB"), dtype=np.uint8).copy()
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - PIL raises many types for corrupt input
        raise ValueError(f"cannot decode frame: {exc}") from exc
