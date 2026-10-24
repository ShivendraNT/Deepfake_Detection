"""Load extracted per-frame records back into FrameRecords (no crops) + crop mosaics."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from satyapan.video.observe import FrameRecord
from satyapan.video.regions import PATCHES


def load_records(npz_path: Path) -> tuple[list[FrameRecord], np.ndarray, np.ndarray | None]:
    """(records, crop_times, audio or None)."""
    z = np.load(npz_path)
    recs = []
    for i in range(len(z["t"])):
        found = bool(z["found"][i])
        recs.append(
            FrameRecord(
                t=float(z["t"][i]),
                found=found,
                face_w=float(z["face_w"][i]),
                luma=float(z["luma"][i]),
                patches={
                    p: tuple(float(v) for v in z["patches"][i, k]) for k, p in enumerate(PATCHES)
                }
                if found
                else {},
                spec=tuple(float(v) for v in z["spec"][i]),  # type: ignore[arg-type]
                iris_r=float(z["iris_r"][i]),
                mouth=float(z["mouth"][i]),
                jaw_open=float(z["jaw_open"][i]),
            )
        )
    audio = z["audio"] if z["audio"].size else None
    return recs, z["crop_t"], audio


def load_crops(jpg_path: Path, n: int, size: int = 224, cols: int = 4) -> np.ndarray:
    """(n, size, size, 3) RGB uint8 crops from a mosaic written by extract.py."""
    import cv2

    img = cv2.cvtColor(cv2.imread(str(jpg_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    out = np.zeros((n, size, size, 3), np.uint8)
    for k in range(n):
        r, c = divmod(k, cols)
        out[k] = img[r * size : (r + 1) * size, c * size : (c + 1) * size]
    return out
