"""MediaPipe Face Landmarker (478 points) indices and the skin patches we measure.

Patches are squares centred on stable landmarks, sized relative to the face width, so they
stay on skin across poses and scale with the face. Index notes (canonical face mesh):
151 mid-forehead, 9 glabella, 50 / 280 cheeks under the eyes (image left / right),
234 / 454 face-oval extremes at cheek level, 13 / 14 inner lips, 61 / 291 mouth corners,
468 / 473 iris centres with rings 469-472 / 474-477.
"""

from __future__ import annotations

import numpy as np

FACE_OVAL = (
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
    152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
)  # fmt: skip
FOREHEAD = 151
GLABELLA = 9
CHEEK_IMG_LEFT = 50
CHEEK_IMG_RIGHT = 280
OVAL_IMG_LEFT = 234
OVAL_IMG_RIGHT = 454
LIP_UPPER_INNER = 13
LIP_LOWER_INNER = 14
MOUTH_LEFT = 61
MOUTH_RIGHT = 291
IRIS_A_CENTER = 468
IRIS_A_RING = (469, 470, 471, 472)
IRIS_B_CENTER = 473
IRIS_B_RING = (474, 475, 476, 477)

PATCHES = ("forehead", "forehead_l", "forehead_r", "cheek_l", "cheek_r")
PATCH_SIDE = 0.16  # fraction of the face width


def face_width(pts: np.ndarray) -> float:
    """Cheek-to-cheek width in pixels (pts: (478, 2) pixel coordinates)."""
    return float(np.linalg.norm(pts[OVAL_IMG_RIGHT] - pts[OVAL_IMG_LEFT]))


def face_box(pts: np.ndarray) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of the face oval."""
    oval = pts[list(FACE_OVAL)]
    return (
        float(oval[:, 0].min()),
        float(oval[:, 1].min()),
        float(oval[:, 0].max()),
        float(oval[:, 1].max()),
    )


def patch_boxes(pts: np.ndarray) -> dict[str, tuple[int, int, int, int]]:
    """Integer (x0, y0, x1, y1) boxes for every patch in PATCHES."""
    w = face_width(pts)
    side = max(2.0, PATCH_SIDE * w)
    half = side / 2.0
    # The forehead patch sits slightly above 151, away from the brows.
    fh = pts[FOREHEAD] + 0.35 * (pts[FOREHEAD] - pts[GLABELLA])
    centres = {
        "forehead": fh,
        "forehead_l": fh - np.array([half, 0.0]),
        "forehead_r": fh + np.array([half, 0.0]),
        "cheek_l": pts[CHEEK_IMG_LEFT],
        "cheek_r": pts[CHEEK_IMG_RIGHT],
    }
    out: dict[str, tuple[int, int, int, int]] = {}
    for name, c in centres.items():
        h = half / 2.0 if name in ("forehead_l", "forehead_r") else half
        out[name] = (
            int(round(c[0] - h)),
            int(round(c[1] - half)),
            int(round(c[0] + h)),
            int(round(c[1] + half)),
        )
    return out


def mouth_openness(pts: np.ndarray) -> float:
    """Inner-lip gap divided by mouth width (0 = closed, ~0.5 = wide open)."""
    width = float(np.linalg.norm(pts[MOUTH_RIGHT] - pts[MOUTH_LEFT]))
    gap = float(np.linalg.norm(pts[LIP_LOWER_INNER] - pts[LIP_UPPER_INNER]))
    return gap / width if width > 1e-6 else 0.0
