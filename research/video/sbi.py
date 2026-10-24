"""Self-Blended Images (Shiohara & Yamasaki, CVPR 2022), adapted.

A pseudo-fake is made from ONE real face: a slightly altered copy of the face (colour shift,
sharpness/blur change, tiny warp) is blended back onto itself through a soft, randomly
deformed face mask. The result has exactly the artefacts a face swap leaves - a blending
boundary, a sharpness and colour mismatch between the inner face and its surroundings - and
nothing else (same identity, same pose, same background). A CNN trained to separate real from
self-blended faces must therefore learn those boundary cues, which is the user's "blurring /
sharpness of the face edges" idea done in a way that generalises to unseen face-swap methods.

All randomness comes from the `rng` passed in (seeded by the caller).
"""

from __future__ import annotations

import numpy as np

# Inner-face landmarks (brows, eyes, nose, mouth, no jaw line) for the smaller mask variant.
INNER = (
    70, 63, 105, 66, 107, 336, 296, 334, 293, 300, 33, 133, 362, 263, 1, 4, 98, 327, 61, 291,
    0, 17, 152, 148, 377, 176, 400, 205, 425, 50, 280, 117, 346,
)  # fmt: skip


def _hull_mask(shape: tuple[int, int], pts: np.ndarray) -> np.ndarray:
    import cv2

    mask = np.zeros(shape, np.float32)
    hull = cv2.convexHull(pts.astype(np.int32))
    cv2.fillConvexPoly(mask, hull, 1.0)
    return mask


def _deform(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Random anisotropic scaling about the centroid + smooth elastic jitter."""
    import cv2

    h, w = mask.shape
    ys, xs = np.nonzero(mask > 0.5)
    if len(xs) == 0:
        return mask
    cx, cy = xs.mean(), ys.mean()
    sx, sy = rng.uniform(0.9, 1.08), rng.uniform(0.9, 1.08)
    m = np.array([[sx, 0, cx - sx * cx], [0, sy, cy - sy * cy]], np.float32)
    mask = cv2.warpAffine(mask, m, (w, h))
    grid = rng.normal(0, 1, (2, 6, 6)).astype(np.float32) * rng.uniform(2, 8)
    dx = cv2.resize(grid[0], (w, h), interpolation=cv2.INTER_CUBIC)
    dy = cv2.resize(grid[1], (w, h), interpolation=cv2.INTER_CUBIC)
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(mask, xx + dx, yy + dy, cv2.INTER_LINEAR)


def _blur(mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    import cv2

    for _ in range(2):
        k = int(rng.integers(2, 13)) * 2 + 1
        mask = cv2.GaussianBlur(mask, (k, k), 0)
    peak = mask.max()
    return mask / peak if peak > 0 else mask


def blend_mask(shape: tuple[int, int], lms: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    pts = lms if rng.random() < 0.6 else lms[list(INNER)]
    mask = _blur(_deform(_hull_mask(shape, pts), rng), rng)
    ratio = float(rng.choice([0.25, 0.5, 0.75, 1.0, 1.0, 1.0]))
    return np.clip(mask * ratio, 0.0, 1.0)


def _color(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    import cv2

    out = img.astype(np.float32)
    if rng.random() < 0.6:
        out += rng.uniform(-20, 20, 3)
    if rng.random() < 0.6:
        hsv = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
        hsv = hsv.astype(np.float32)
        hsv[..., 0] = (hsv[..., 0] + rng.uniform(-6, 6)) % 180
        hsv[..., 1] = hsv[..., 1] * rng.uniform(0.8, 1.2)
        hsv[..., 2] = hsv[..., 2] * rng.uniform(0.85, 1.15)
        out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2RGB)
        out = out.astype(np.float32)
    if rng.random() < 0.6:
        out = (out - 128) * rng.uniform(0.85, 1.15) + 128 + rng.uniform(-15, 15)
    return np.clip(out, 0, 255).astype(np.uint8)


def _frequency(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sharpness mismatch: down-up-scale (blur) or unsharp-mask (over-sharpen)."""
    import cv2

    h, w = img.shape[:2]
    r = rng.random()
    if r < 0.45:
        f = rng.uniform(0.35, 0.8)
        small = cv2.resize(
            img, (max(8, int(w * f)), max(8, int(h * f))), interpolation=cv2.INTER_AREA
        )
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    if r < 0.7:
        blur = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.8, 2.0))
        amt = rng.uniform(0.5, 1.5)
        return np.clip(img.astype(np.float32) * (1 + amt) - blur * amt, 0, 255).astype(np.uint8)
    return img


def _warp(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    import cv2

    h, w = img.shape[:2]
    s = rng.uniform(0.95, 1.05)
    tx, ty = rng.uniform(-0.03, 0.03) * w, rng.uniform(-0.03, 0.03) * h
    cx, cy = w / 2, h / 2
    m = np.array([[s, 0, (1 - s) * cx + tx], [0, s, (1 - s) * cy + ty]], np.float32)
    return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)


def self_blend(img: np.ndarray, lms: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One pseudo-fake from a real RGB uint8 face image and its landmarks."""
    src, tgt = img.copy(), img.copy()
    if rng.random() < 0.5:
        src = _color(src, rng)
    else:
        tgt = _color(tgt, rng)
    src = _frequency(src, rng)
    src = _warp(src, rng)
    mask = blend_mask(img.shape[:2], lms, rng)[..., None]
    out = src.astype(np.float32) * mask + tgt.astype(np.float32) * (1 - mask)
    return np.clip(out, 0, 255).astype(np.uint8)


def common_augment(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Applied to real AND fake alike: call-like degradations, so they carry no label."""
    import cv2

    h, w = img.shape[:2]
    if rng.random() < 0.5:
        img = img[:, ::-1].copy()
    if rng.random() < 0.3:
        f = rng.uniform(0.45, 1.0)
        small = cv2.resize(
            img, (max(16, int(w * f)), max(16, int(h * f))), interpolation=cv2.INTER_AREA
        )
        img = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.3:
        img = np.clip(
            (img.astype(np.float32) - 128) * rng.uniform(0.9, 1.1) + 128 + rng.uniform(-10, 10),
            0,
            255,
        ).astype(np.uint8)
    if rng.random() < 0.7:
        q = int(rng.integers(45, 101))
        enc = cv2.imencode(".jpg", img[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, q])[1]
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)[..., ::-1].copy()
    return img
