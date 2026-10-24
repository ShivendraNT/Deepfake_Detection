"""Per-frame measurements. Pure numpy (plus OpenCV for one resize), no model calls.

A `FrameRecord` keeps only what the window features need: patch colour means, the corneal
highlight offsets, mouth openness, face size and (for a few frames) a face crop for the CNN.
The frame itself is dropped right after this step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from satyapan.video import regions as R

CROP_SIZE = 224
CROP_MARGIN = 1.3  # square crop side = margin x max(face box width, height)
NAN4 = (float("nan"),) * 4


@dataclass
class FrameRecord:
    t: float
    found: bool
    face_w: float = float("nan")
    luma: float = float("nan")  # mean luminance of the face box (0-255)
    patches: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    spec: tuple[float, float, float, float] = NAN4  # highlight offsets (dx, dy) per eye / r
    iris_r: float = float("nan")
    mouth: float = float("nan")
    jaw_open: float = float("nan")
    crop: np.ndarray | None = None  # (CROP_SIZE, CROP_SIZE, 3) uint8 RGB, only some frames


def _luma(rgb: np.ndarray) -> np.ndarray:
    rgb = rgb.astype(np.float32)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _clip_box(box: tuple[int, int, int, int], w: int, h: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def patch_means(frame: np.ndarray, pts: np.ndarray) -> dict[str, tuple[float, float, float]]:
    h, w = frame.shape[:2]
    out: dict[str, tuple[float, float, float]] = {}
    for name, box in R.patch_boxes(pts).items():
        x0, y0, x1, y1 = _clip_box(box, w, h)
        if x1 - x0 < 2 or y1 - y0 < 2:
            out[name] = (float("nan"),) * 3
            continue
        m = frame[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32).mean(axis=0)
        out[name] = (float(m[0]), float(m[1]), float(m[2]))
    return out


def _eye_highlight(
    frame: np.ndarray, centre: np.ndarray, ring: np.ndarray
) -> tuple[float, float, float] | None:
    """(dx, dy, r): centroid offset of the brightest specular blob inside the iris / r."""
    r = float(np.mean(np.linalg.norm(ring - centre, axis=1)))
    if not np.isfinite(r) or r < 3.0:
        return None
    h, w = frame.shape[:2]
    x0, y0 = int(np.floor(centre[0] - r)), int(np.floor(centre[1] - r))
    x1, y1 = int(np.ceil(centre[0] + r)) + 1, int(np.ceil(centre[1] + r)) + 1
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    y = _luma(frame[y0:y1, x0:x1])
    yy, xx = np.mgrid[y0:y1, x0:x1]
    disk = (xx - centre[0]) ** 2 + (yy - centre[1]) ** 2 <= r * r
    vals = y[disk]
    if vals.size < 8:
        return None
    peak = float(vals.max())
    # A corneal reflection is a small near-saturated blob, clearly brighter than the iris.
    if peak < 150.0 or peak - float(np.median(vals)) < 60.0:
        return None
    blob = disk & (y >= peak - 25.0)
    cx = float(xx[blob].mean())
    cy = float(yy[blob].mean())
    return (cx - float(centre[0])) / r, (cy - float(centre[1])) / r, r


def specular(frame: np.ndarray, pts: np.ndarray) -> tuple[tuple[float, ...], float]:
    a = _eye_highlight(frame, pts[R.IRIS_A_CENTER], pts[list(R.IRIS_A_RING)])
    b = _eye_highlight(frame, pts[R.IRIS_B_CENTER], pts[list(R.IRIS_B_RING)])
    radii = [e[2] for e in (a, b) if e is not None]
    r = float(np.mean(radii)) if radii else float("nan")
    if a is None or b is None:
        return NAN4, r
    return (a[0], a[1], b[0], b[1]), r


def face_crop(
    frame: np.ndarray, pts: np.ndarray, size: int = CROP_SIZE, margin: float = CROP_MARGIN
) -> np.ndarray:
    """Square crop around the face oval (includes the face edge and some background)."""
    import cv2

    x0, y0, x1, y1 = R.face_box(pts)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    side = max(x1 - x0, y1 - y0) * margin
    half = side / 2.0
    # Affine map from the crop square to the output; replicate borders off-frame.
    scale = size / max(side, 1.0)
    m = np.array(
        [[scale, 0.0, -(cx - half) * scale], [0.0, scale, -(cy - half) * scale]], dtype=np.float32
    )
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.warpAffine(frame, m, (size, size), flags=interp, borderMode=cv2.BORDER_REPLICATE)


def observe(
    frame: np.ndarray,
    t: float,
    face_pts: np.ndarray | None,
    jaw_open: float = 0.0,
    want_crop: bool = False,
) -> FrameRecord:
    """Measure one RGB uint8 frame given the tracked landmarks (or None)."""
    if face_pts is None:
        return FrameRecord(t=t, found=False)
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in R.face_box(face_pts))
    bx0, by0, bx1, by1 = _clip_box((x0, y0, x1, y1), w, h)
    luma = float(_luma(frame[by0:by1:4, bx0:bx1:4]).mean()) if bx1 > bx0 and by1 > by0 else 0.0
    spec, iris_r = specular(frame, face_pts)
    return FrameRecord(
        t=t,
        found=True,
        face_w=R.face_width(face_pts),
        luma=luma,
        patches=patch_means(frame, face_pts),
        spec=spec,
        iris_r=iris_r,
        mouth=R.mouth_openness(face_pts),
        jaw_open=float(jaw_open),
        crop=face_crop(frame, face_pts) if want_crop else None,
    )
