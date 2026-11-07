"""Pixel-level tampering techniques for still images.

All of them work on the image in its stored orientation and at its stored resolution where
compression traces matter (ELA, JPEG grid, noise), because resampling destroys exactly the
traces they measure. Maps are rotated to display orientation only for the overlay artifacts.
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np

from satyapan.forensics.base import NotApplicable, Technique, finding, info, make_result
from satyapan.forensics.context import (
    AnalysisContext,
    block_reduce,
    colormap,
    overlay,
    regions_from_mask,
    robust_z,
)
from satyapan.forensics.models import (
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Region,
    Status,
    Strength,
    TechniqueResult,
)

IMG = (MediaKind.IMAGE,)
MAX_FULL_PIXELS = 30_000_000
LOSSY = ("jpeg",)
LOSSLESS = ("png", "bmp", "tiff", "gif")


def _orientation(ctx: AnalysisContext) -> int:
    try:
        return int(ctx.pil_raw().getexif().get(0x0112, 1) or 1)
    except Exception:  # noqa: BLE001
        return 1


def to_display(ctx: AnalysisContext, arr: np.ndarray) -> np.ndarray:
    """Apply the EXIF orientation to a map computed in stored orientation."""
    o = _orientation(ctx)
    ops = {2: lambda a: a[:, ::-1], 3: lambda a: a[::-1, ::-1], 4: lambda a: a[::-1],
           5: lambda a: np.swapaxes(a, 0, 1), 6: lambda a: np.rot90(a, -1),
           7: lambda a: np.rot90(a, 1)[::-1], 8: lambda a: np.rot90(a, 1)}  # fmt: skip
    f = ops.get(o)
    return np.ascontiguousarray(f(arr)) if f else arr


def _region_to_display(
    ctx: AnalysisContext, r: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    x, y, w, h = r
    o = _orientation(ctx)
    if o == 6:  # rotate 90 CW: (x, y) -> (1 - y - h, x)
        return (1 - y - h, x, h, w)
    if o == 8:  # rotate 90 CCW
        return (y, 1 - x - w, h, w)
    if o == 3:
        return (1 - x - w, 1 - y - h, w, h)
    return r


def stored_rgb(ctx: AnalysisContext) -> np.ndarray:
    """Full-resolution RGB in stored orientation (no EXIF rotation, no downscale)."""
    if "stored_rgb" not in ctx.cache:
        raw = ctx.pil_raw()
        if raw.size[0] * raw.size[1] > MAX_FULL_PIXELS:
            raise NotApplicable(f"image too large for pixel analysis ({raw.size[0]}×{raw.size[1]})")
        img = raw.convert("RGB") if raw.mode != "RGB" else raw
        ctx.cache["stored_rgb"] = np.asarray(img, dtype=np.uint8)
    return ctx.cache["stored_rgb"]  # type: ignore[no-any-return]


def stored_gray(ctx: AnalysisContext) -> np.ndarray:
    if "stored_gray" not in ctx.cache:
        rgb = stored_rgb(ctx).astype(np.float32)
        ctx.cache["stored_gray"] = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return ctx.cache["stored_gray"]  # type: ignore[no-any-return]


def _display_rgb(ctx: AnalysisContext) -> np.ndarray:
    return ctx.rgb(1600)


def _boxes(ctx: AnalysisContext, mask: np.ndarray, label: str, scores: np.ndarray | None = None,
           min_frac: float = 0.004) -> list[Region]:  # fmt: skip
    out = []
    for x, y, w, h, _frac in regions_from_mask(mask, min_frac=min_frac):
        dx, dy, dw, dh = _region_to_display(ctx, (x, y, w, h))
        sc = None
        if scores is not None:
            H, W = mask.shape
            sub = scores[int(y * H) : int((y + h) * H) + 1, int(x * W) : int((x + w) * W) + 1]
            sc = float(np.nanmax(sub)) if sub.size else None
        out.append(Region(x=round(dx, 4), y=round(dy, 4), w=round(dw, 4), h=round(dh, 4),
                          label=label, score=None if sc is None else round(sc, 2)))  # fmt: skip
    return out


def _clean_mask(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    import cv2

    k = np.ones((3, 3), np.uint8)
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k, iterations=iterations)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=iterations)
    return m.astype(bool)


_THRESHOLDS: dict[str, Any] | None = None
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "ela": {"weak": 9.0, "moderate": 14.0, "strong": 30.0},
    "noise": {"weak": 6.0, "moderate": 9.0, "strong": 15.0},
    "copymove": {"weak": 10.0, "moderate": 14.0, "strong": 25.0},
    "grid_shift": {"weak": 0.25, "moderate": 0.35, "strong": 1e9},
    "grid_second": {"weak": 0.8, "moderate": 1.2, "strong": 1e9},
}


def thresholds() -> dict[str, Any]:
    """Calibrated operating points (config/forensic_thresholds.json, written by
    research/forensics/classical_calib.py: weak / moderate / strong = 2% / 0.5% / 0.1% false
    alarms on genuine photographs), falling back to conservative defaults."""
    global _THRESHOLDS
    if _THRESHOLDS is None:
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parents[4] / "config" / "forensic_thresholds.json"
        merged = {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            for k, v in raw.get("thresholds", {}).items():
                merged.setdefault(k, {}).update(v)
            merged["_fpr"] = raw.get("fpr", {})
        _THRESHOLDS = merged
    return _THRESHOLDS


def level(score: float, thr: dict[str, float]) -> Strength:
    if score >= thr.get("strong", 1e9):
        return Strength.STRONG
    if score >= thr["moderate"]:
        return Strength.MODERATE
    if score >= thr["weak"]:
        return Strength.WEAK
    return Strength.NONE


def fpr_text(score: float, thr: dict[str, float]) -> str:
    if score >= thr.get("strong", 1e9):
        return "exceeded by fewer than 0.1% of genuine photographs in calibration"
    if score >= thr["moderate"]:
        return "exceeded by about 0.5% of genuine photographs in calibration"
    return "exceeded by about 2% of genuine photographs in calibration"


# ---------------------------------------------------------------------------------------------
# Error Level Analysis
# ---------------------------------------------------------------------------------------------

ELA_QUALITY = 90
ELA_BLOCK = 16


def component_scores(
    mask: np.ndarray, z: np.ndarray, lo: float, hi: float
) -> tuple[float, np.ndarray]:
    """Score each connected component of `mask` (area fraction in [lo, hi]) by the mean of its
    five largest |z|; return the best score and the mask of components kept."""
    import cv2

    m = mask.astype(np.uint8)
    keep = np.zeros_like(m, dtype=bool)
    if m.sum() == 0:
        return 0.0, keep
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    best = 0.0
    total = float(m.size)
    for i in range(1, n):
        frac = stats[i][4] / total
        if not lo <= frac <= hi:
            continue
        vals = np.sort(np.abs(z[lab == i]))[-5:]
        sc = float(vals.mean()) if len(vals) else 0.0
        keep |= lab == i
        best = max(best, sc)
    return best, keep


def ela_stats(rgb: np.ndarray, gray: np.ndarray, quality: int = ELA_QUALITY) -> dict[str, Any]:
    """Texture-normalised error level per 16x16 block, its robust z-map and the best anomalous
    component score (the calibrated statistic)."""
    import cv2
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    re = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), dtype=np.float32)
    err = np.abs(rgb.astype(np.float32) - re).max(axis=2)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    tex = np.sqrt(gx * gx + gy * gy)
    eb = block_reduce(err, ELA_BLOCK)
    tb = block_reduce(tex, ELA_BLOCK)
    z = robust_z(eb / (np.sqrt(tb) + 2.0))
    hot = _clean_mask((z > 3.0) & (eb > max(2.0, float(np.percentile(eb, 75)))))
    score, keep = component_scores(hot, z, 0.002, 0.35)
    return {"err": err, "z": z, "score": score, "mask": keep}


def run_ela(ctx: AnalysisContext) -> TechniqueResult:
    t = ELA
    if ctx.sniffed.format not in LOSSY:
        return make_result(t, summary="applies to JPEG-compressed images only",
                           status=Status.SKIPPED)  # fmt: skip
    thr = thresholds()["ela"]
    st = ela_stats(stored_rgb(ctx), stored_gray(ctx))
    err, z, score = st["err"], st["z"], st["score"]
    flagged = st["mask"] & (np.abs(z) >= min(thr["moderate"], thr["weak"]))
    regions = _boxes(ctx, flagged, "high error level", z, min_frac=0.002)
    vis = np.clip(err / max(1.0, float(np.percentile(err, 99.5))), 0, 1)
    art_ela = ctx.save_jpeg("ela", to_display(ctx, colormap(vis, "inferno")), "heatmap",
                            f"Error Level Analysis (q={ELA_QUALITY})",
                            "Bright = large change on re-compression. Edges and texture are "
                            "always bright; look for flat areas that glow unlike their "
                            "surroundings.")  # fmt: skip
    zmap = np.clip((z - 1.5) / 6.0, 0, 1)
    ov = overlay(_display_rgb(ctx), to_display(ctx, zmap), alpha=0.6)
    art_ov = ctx.save_jpeg("ela_overlay", ov, "overlay", "ELA anomaly overlay",
                           "Blocks whose error level is unusually high for their texture.")  # fmt: skip
    findings: list[Finding] = []
    data: dict[str, Any] = {"quality": ELA_QUALITY, "score": round(score, 2),
                            "thresholds": thr, "mean_error": round(float(err.mean()), 3)}  # fmt: skip
    strength = level(score, thr)
    if strength > Strength.NONE and regions:
        findings.append(
            finding(
                "ELA_ANOMALY",
                f"Compression error level differs in {len(regions)} region(s)",
                f"After re-compression at quality 90 these regions change far more than areas "
                f"of similar texture (anomaly score {score:.1f}; {fpr_text(score, thr)}). "
                "Content pasted from another file or retouched and re-saved behaves this "
                "way. ELA alone is not conclusive: compare with the noise and copy-move maps.",
                Hypothesis.MANIPULATED,
                strength,
                Category.TAMPERING,
                score=round(score, 2),
                regions=regions,
                artifacts=[art_ov.name, art_ela.name],
            )  # fmt: skip
        )
    summary = (f"{len(regions)} anomalous region(s), score {score:.1f}" if findings
               else f"error level consistent with texture (score {score:.1f})")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data,
                       artifacts=[art_ela, art_ov])  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Noise-level inconsistency
# ---------------------------------------------------------------------------------------------

NOISE_BLOCK = 32


def noise_map(gray: np.ndarray, block: int = NOISE_BLOCK) -> tuple[np.ndarray, np.ndarray]:
    """Per-block noise sigma from the finest Haar diagonal band (Donoho's MAD estimator) and a
    validity mask (flat, clipped blocks carry no noise information)."""
    h, w = gray.shape
    h2, w2 = h - h % 2, w - w % 2
    g = gray[:h2, :w2]
    a, b, c, d = g[0::2, 0::2], g[0::2, 1::2], g[1::2, 0::2], g[1::2, 1::2]
    hh = (a - b - c + d) / 2.0
    half = block // 2
    hb, wb = hh.shape[0] // half, hh.shape[1] // half
    if hb < 2 or wb < 2:
        raise NotApplicable("image too small for a noise map")
    v = np.abs(hh[: hb * half, : wb * half]).reshape(hb, half, wb, half)
    sigma = np.median(v, axis=(1, 3)) / 0.6745
    mean = block_reduce(gray, block)[:hb, :wb]
    valid = (mean > 12) & (mean < 243)
    return sigma.astype(np.float32), valid


def noise_stats(gray: np.ndarray) -> dict[str, Any] | None:
    sigma, valid = noise_map(gray)
    s_ = np.where(valid, sigma, np.nan)
    if np.isfinite(s_).sum() < 16:
        return None
    logs = np.log(np.maximum(s_, 0.05))
    z = robust_z(np.where(np.isfinite(logs), logs, np.nanmedian(logs)))
    z = np.where(valid, z, 0.0)
    mask = _clean_mask(np.abs(z) > 2.5)
    score, keep = component_scores(mask, z, 0.01, 0.4)
    return {"z": z, "sigma": s_, "score": score, "mask": keep}


def run_noise(ctx: AnalysisContext) -> TechniqueResult:
    t = NOISE
    gray = stored_gray(ctx)
    st = noise_stats(gray)
    if st is None:
        return make_result(t, summary="too few textured blocks to estimate noise",
                           status=Status.SKIPPED)  # fmt: skip
    thr = thresholds()["noise"]
    z, score = st["z"], st["score"]
    flagged = st["mask"]
    regions = _boxes(ctx, flagged & (z < 0), "lower noise", -z, min_frac=0.01) + _boxes(
        ctx, flagged & (z > 0), "higher noise", z, min_frac=0.01
    )
    vis = np.clip(np.abs(z) / 6.0, 0, 1)
    import cv2

    H, W = gray.shape
    heat_full = cv2.resize(colormap(vis, "turbo"), (W, H), interpolation=cv2.INTER_NEAREST)
    art_map = ctx.save_jpeg("noise_map", to_display(ctx, heat_full), "heatmap",
                            "Local noise level deviation",
                            "Each block's sensor/compression noise compared with the image's "
                            "typical level. Blue = typical, red = unusually low or high.")  # fmt: skip
    ov = overlay(_display_rgb(ctx), to_display(ctx, vis), alpha=0.55)
    art_ov = ctx.save_jpeg("noise_overlay", ov, "overlay", "Noise inconsistency overlay")
    data = {"median_sigma": round(float(np.nanmedian(st["sigma"])), 3), "score": round(score, 2),
            "thresholds": thr, "blocks": int(np.isfinite(st["sigma"]).sum())}  # fmt: skip
    findings: list[Finding] = []
    strength = level(score, thr)
    if strength > Strength.NONE and regions:
        findings.append(
            finding(
                "NOISE_INCONSISTENCY",
                f"Noise level inconsistent in {len(regions)} region(s)",
                "A photograph carries roughly uniform sensor and compression noise. These "
                f"regions are much smoother or noisier than the rest (score {score:.1f}; "
                f"{fpr_text(score, thr)}), which happens when content from another source "
                "is pasted in, or an area is painted over or regenerated (AI inpainting, "
                "retouching). Flat sky, blur and shadows can also differ, so read this "
                "together with the other maps.",
                Hypothesis.MANIPULATED,
                strength,
                Category.TAMPERING,
                score=round(score, 2),
                regions=regions,
                artifacts=[art_ov.name, art_map.name],
            )  # fmt: skip
        )
    summary = (f"{len(regions)} region(s) with inconsistent noise (score {score:.1f})" if findings
               else f"noise level consistent across the image (score {score:.1f})")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data,
                       artifacts=[art_map, art_ov])  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Copy-move (cloning) detection
# ---------------------------------------------------------------------------------------------

CM_MAX_SIDE = 1600


def copy_move_clusters(gray_u8: np.ndarray, max_clusters: int = 3) -> list[dict[str, Any]]:
    """SIFT self-matching with the g2NN ratio test, then RANSAC similarity transforms.
    Returns clusters of point pairs that move together (cloned regions)."""
    import cv2

    sift = cv2.SIFT_create(nfeatures=6000, contrastThreshold=0.02)
    kp, des = sift.detectAndCompute(gray_u8, None)
    if des is None or len(kp) < 30:
        return []
    pts = np.array([k.pt for k in kp], dtype=np.float32)
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    knn = matcher.knnMatch(des, des, k=4)
    min_dist = max(20.0, 0.02 * max(gray_u8.shape))
    pairs = set()
    for i, ms in enumerate(knn):
        ms = [m for m in ms if m.trainIdx != i]
        for a, b in zip(ms, ms[1:], strict=False):
            if a.distance < 0.5 * b.distance:
                j = a.trainIdx
                if np.linalg.norm(pts[i] - pts[j]) > min_dist:
                    pairs.add((min(i, j), max(i, j)))
                break
            break
    if len(pairs) < 8:
        return []
    pl = np.array(sorted(pairs))
    src, dst = pts[pl[:, 0]], pts[pl[:, 1]]
    clusters = []
    remaining = np.ones(len(pl), dtype=bool)
    for _ in range(max_clusters):
        idx = np.where(remaining)[0]
        if len(idx) < 8:
            break
        M, inl = cv2.estimateAffinePartial2D(src[idx], dst[idx], method=cv2.RANSAC,
                                             ransacReprojThreshold=4.0, maxIters=4000,
                                             confidence=0.995)  # fmt: skip
        if M is None or inl is None:
            break
        inl = inl.ravel().astype(bool)
        members = idx[inl]
        if len(members) < 8:
            break
        shift = float(np.hypot(M[0, 2], M[1, 2]))
        scale = float(np.hypot(M[0, 0], M[1, 0]))
        angle = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
        s_pts, d_pts = src[members], dst[members]
        spread = float(np.mean(np.std(s_pts, axis=0)))
        clusters.append({"pairs": len(members), "src": s_pts, "dst": d_pts, "shift": shift,
                         "scale": scale, "angle": angle, "spread": spread})  # fmt: skip
        remaining[members] = False
    return clusters


def run_copy_move(ctx: AnalysisContext) -> TechniqueResult:
    t = COPY_MOVE
    import cv2

    rgb = ctx.rgb(CM_MAX_SIDE)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clusters = copy_move_clusters(gray)
    H, W = gray.shape
    findings: list[Finding] = []
    vis = rgb.copy()
    good = []
    thr = thresholds()["copymove"]
    sizes = sorted((c["pairs"] for c in clusters), reverse=True)
    for c in clusters:
        dominant = (
            len(sizes) < 2 or c["pairs"] >= 2 * sizes[1] or c is clusters[0] and c["pairs"] >= 40
        )
        compact = c["spread"] < 0.25 * max(H, W)
        if c["pairs"] >= thr["weak"] and compact and (dominant or c["pairs"] >= 30):
            good.append(c)
    regions: list[Region] = []
    for k, c in enumerate(good):
        col_s, col_d = (60, 255, 120), (255, 70, 70)
        for (x1, y1), (x2, y2) in zip(c["src"], c["dst"], strict=True):
            cv2.line(vis, (int(x1), int(y1)), (int(x2), int(y2)), (255, 230, 0), 1, cv2.LINE_AA)
            cv2.circle(vis, (int(x1), int(y1)), 3, col_s, -1, cv2.LINE_AA)
            cv2.circle(vis, (int(x2), int(y2)), 3, col_d, -1, cv2.LINE_AA)
        for pts, lab in ((c["src"], f"clone {k + 1} source"), (c["dst"], f"clone {k + 1} copy")):
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
            pad = 12
            x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
            x1, y1 = min(W - 1, x1 + pad), min(H - 1, y1 + pad)
            cv2.rectangle(vis, (int(x0), int(y0)), (int(x1), int(y1)), (255, 230, 0), 2)
            regions.append(Region(x=round(x0 / W, 4), y=round(y0 / H, 4),
                                  w=round((x1 - x0) / W, 4), h=round((y1 - y0) / H, 4),
                                  label=lab, score=float(c["pairs"])))  # fmt: skip
    art = ctx.save_jpeg("copy_move", vis, "overlay", "Copy-move keypoint matches",
                        "Yellow lines join keypoints whose surroundings are identical: green = "
                        "where the content came from, red = where it was pasted.")  # fmt: skip
    data = {"clusters": [{"pairs": c["pairs"], "shift_px": round(c["shift"], 1),
                          "scale": round(c["scale"], 3), "rotation_deg": round(c["angle"], 1)}
                         for c in clusters], "thresholds": thr,
            "score": float(good[0]["pairs"]) if good else 0.0}  # fmt: skip
    if good:
        best = good[0]
        strength = level(float(best["pairs"]), thr)
        findings.append(
            finding(
                "COPY_MOVE",
                f"Cloned region: {best['pairs']} matching keypoints move together",
                f"{best['pairs']} distinctive keypoints in one area reappear "
                f"{best['shift']:.0f} px away"
                + (f", rotated {best['angle']:.0f}°" if abs(best["angle"]) > 2 else "")
                + (f", scaled ×{best['scale']:.2f}" if abs(best["scale"] - 1) > 0.03 else "")
                + ". A camera cannot produce the same texture twice; part of the image was "
                "copied and pasted (for example to hide or duplicate an object, a stamp or "
                "a signature). Repetitive patterns (tiles, text) are excluded by requiring "
                "one compact, dominant group.",
                Hypothesis.MANIPULATED,
                strength,
                Category.TAMPERING,
                score=float(best["pairs"]),
                regions=regions,
                artifacts=[art.name],
                clones=len(good),
            )  # fmt: skip
        )
        summary = f"{len(good)} cloned region(s); strongest {best['pairs']} keypoint pairs"
    else:
        summary = "no cloned regions found"
    return make_result(t, summary=summary, findings=findings, data=data, artifacts=[art])


# ---------------------------------------------------------------------------------------------
# JPEG block grid / double compression
# ---------------------------------------------------------------------------------------------


def blocking_profile(gray: np.ndarray) -> dict[str, Any]:
    """Blockiness of the 8x8 grid at each of the 8 phases, horizontally and vertically.
    Phase 7 = boundary between pixel 7 and 8 = the grid of a JPEG aligned with this file."""
    g = gray.astype(np.float32)
    dh = np.abs(np.diff(g, axis=1))
    dv = np.abs(np.diff(g, axis=0))

    def prof(d: np.ndarray, axis: int) -> np.ndarray:
        n = d.shape[axis]
        m = d.mean(axis=1 - axis)
        p = np.array([m[np.arange(n) % 8 == k].mean() for k in range(8)])
        return p

    ph, pv = prof(dh, 1), prof(dv, 0)

    def contrast(p: np.ndarray) -> np.ndarray:
        return (p - (np.roll(p, 1) + np.roll(p, -1)) / 2.0) / (p.mean() + 1e-6)

    ch, cv = contrast(ph), contrast(pv)
    return {"h": ch, "v": cv, "phase_h": int(np.argmax(ch)), "phase_v": int(np.argmax(cv)),
            "strength_h": float(ch.max()), "strength_v": float(cv.max())}  # fmt: skip


def grid_scores(p: dict[str, Any]) -> tuple[float, float]:
    """(shift score, secondary-grid score). Shift: blockiness at the dominant offset when it is
    not the file's own grid (both axes). Secondary: the strongest non-zero-offset blockiness
    relative to the aligned one, when the aligned grid dominates."""
    aligned = p["phase_h"] == 7 and p["phase_v"] == 7
    sh, sv = p["strength_h"], p["strength_v"]
    if not aligned:
        return float(min(sh, sv)), 0.0
    second = min(
        max(v for k, v in enumerate(p["h"]) if k != 7),
        max(v for k, v in enumerate(p["v"]) if k != 7),
    )
    return 0.0, float(max(0.0, second) / (min(sh, sv) + 1e-6))


def run_jpeg_grid(ctx: AnalysisContext) -> TechniqueResult:
    t = JPEG_GRID
    gray = stored_gray(ctx)
    if min(gray.shape) < 64:
        return make_result(t, summary="image too small", status=Status.SKIPPED)
    p = blocking_profile(gray)
    sh, sv = p["strength_h"], p["strength_v"]
    strength = min(sh, sv)
    findings: list[Finding] = []
    data = {"phase": [p["phase_h"], p["phase_v"]], "grid_strength": [round(sh, 3), round(sv, 3)],
            "profile_h": [round(float(x), 4) for x in p["h"]],
            "profile_v": [round(float(x), 4) for x in p["v"]]}  # fmt: skip
    fmt = ctx.sniffed.format
    if fmt in LOSSLESS or fmt == "webp":
        if strength > 0.08:
            findings.append(
                info(
                    "PRIOR_JPEG_COMPRESSION",
                    f"Lossless {fmt.upper()} carries JPEG 8×8 block traces",
                    "The pixels show the 8×8 blocking that JPEG compression leaves behind, but "
                    f"the file is a {fmt.upper()}: it was JPEG-compressed earlier and then "
                    "converted or screenshotted. A camera-original lossless file has no grid.",
                    Category.PROVENANCE,
                    grid_strength=round(strength, 3),
                )  # fmt: skip
            )
            summary = f"earlier JPEG compression detected (grid strength {strength:.2f})"
        else:
            summary = "no JPEG block grid (never JPEG-compressed, or heavily resampled)"
        return make_result(t, summary=summary, findings=findings, data=data)
    if fmt != "jpeg":
        return make_result(t, summary="not applicable to this format", status=Status.SKIPPED)
    shift_score, second_score = grid_scores(p)
    data.update({"shift_score": round(shift_score, 3), "second_score": round(second_score, 3)})
    ts, t2 = thresholds()["grid_shift"], thresholds()["grid_second"]
    if strength < 0.04:
        summary = "block grid too weak to analyse (very high quality)"
    elif level(shift_score, ts) > Strength.NONE:
        findings.append(
            finding(
                "SHIFTED_JPEG_GRID",
                "JPEG grid is shifted from the file's own grid",
                f"The dominant 8×8 blocking sits at offset ({(p['phase_h'] + 1) % 8}, "
                f"{(p['phase_v'] + 1) % 8}) instead of (0, 0): the visible compression "
                "comes from an earlier save, and the image was cropped before its last save "
                f"(score {shift_score:.2f}; {fpr_text(shift_score, ts)}).",
                Hypothesis.MANIPULATED,
                level(shift_score, ts),
                Category.TAMPERING,
                score=round(shift_score, 3),
            )  # fmt: skip
        )
        summary = "dominant JPEG grid shifted: cropped after an earlier compression"
    elif level(second_score, t2) > Strength.NONE:
        findings.append(
            finding(
                "MISALIGNED_DOUBLE_JPEG",
                "Traces of an earlier, shifted JPEG grid",
                "Besides the grid of the last compression, a second 8×8 grid at a "
                "different offset is visible: the image was compressed, cropped or shifted, "
                f"then compressed again (score {second_score:.2f}; "
                f"{fpr_text(second_score, t2)}).",
                Hypothesis.MANIPULATED,
                level(second_score, t2),
                Category.TAMPERING,
                score=round(second_score, 3),
            )  # fmt: skip
        )
        summary = "two JPEG grids: re-compressed after cropping"
    else:
        summary = "single JPEG grid aligned with the file"
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Spectral residual (periodic artefacts)
# ---------------------------------------------------------------------------------------------


def run_spectrum(ctx: AnalysisContext) -> TechniqueResult:
    t = SPECTRUM
    import cv2

    gray = ctx.gray(1024)
    n = min(512, (min(gray.shape) // 2) * 2)
    if n < 128:
        return make_result(t, summary="image too small", status=Status.SKIPPED)
    y0, x0 = (gray.shape[0] - n) // 2, (gray.shape[1] - n) // 2
    patch = gray[y0 : y0 + n, x0 : x0 + n].astype(np.float32)
    resid = patch - cv2.GaussianBlur(patch, (0, 0), 1.5)
    win = np.outer(np.hanning(n), np.hanning(n)).astype(np.float32)
    spec = np.fft.fftshift(np.abs(np.fft.fft2(resid * win)))
    logs = np.log1p(spec)
    med = cv2.medianBlur(((logs / logs.max()) * 255).astype(np.uint8), 15).astype(np.float32)
    ratio = (logs / logs.max()) * 255 - med
    c = n // 2
    yy, xx = np.mgrid[0:n, 0:n]
    mask = (np.hypot(yy - c, xx - c) > n * 0.06) & (np.abs(yy - c) > 2) & (np.abs(xx - c) > 2)
    peaks = np.argwhere((ratio > 38) & mask)
    grid8 = 0
    other = []
    for py, px in peaks:
        fy, fx = (py - c) / n, (px - c) / n
        on8 = all(abs(f * 8 - round(f * 8)) < 0.02 for f in (fy, fx))
        if on8:
            grid8 += 1
        else:
            other.append((round(float(fx), 3), round(float(fy), 3)))
    vis = colormap((logs - logs.min()) / (np.ptp(logs) + 1e-6), "magma")
    art = ctx.save_png("spectrum", vis, "figure", "Noise-residual spectrum (log magnitude)",
                       "Centre = low frequencies. Isolated bright dots are periodic patterns: "
                       "on the 1/8 lattice they come from JPEG blocks; elsewhere from "
                       "resampling or generative up-sampling.")  # fmt: skip
    findings: list[Finding] = []
    data = {"peaks_on_jpeg_lattice": grid8, "other_peaks": len(other), "other": other[:20]}
    if len(other) >= 4:
        findings.append(
            info(
                "PERIODIC_ARTEFACTS",
                f"{len(other)} periodic spectral peaks off the JPEG lattice",
                "The noise residual has regularly spaced energy peaks that JPEG blocking does "
                "not explain. Up-sampling layers in GANs and diffusion decoders and image "
                "resizing leave such patterns. Indicative only; see the AI-image model result.",
                Category.SYNTHETIC,
                peaks=len(other),
            )  # fmt: skip
        )
    summary = f"{grid8} JPEG-lattice peaks, {len(other)} other periodic peaks"
    return make_result(t, summary=summary, findings=findings, data=data, artifacts=[art])


ELA = Technique(
    "image.ela", "Error Level Analysis", Category.TAMPERING, IMG, run_ela,
    "The image is re-compressed at JPEG quality 90 and the per-pixel difference is measured. "
    "Areas with a different compression history (pasted from another file, retouched and "
    "re-saved) re-compress differently. To limit false alarms on edges, the error is "
    "normalised by local texture (Sobel gradient) and blocks are flagged only when they are "
    "robust outliers (z > 4 against the image's own median/MAD).",
    "Krawetz, 'A Picture's Worth', Black Hat 2007",
    "Indicative only; resizing, heavy compression or a lossless format remove the signal.",
    order=20,
)  # fmt: skip
NOISE = Technique(
    "image.noise", "Noise-level inconsistency", Category.TAMPERING, IMG, run_noise,
    "Local noise (sensor + compression) is estimated per 32×32 block from the finest Haar "
    "wavelet diagonal band with the median-absolute-deviation estimator. Blocks whose noise is "
    "a robust outlier (|z| > 3 on the log scale) and form connected regions are reported.",
    "Mahdian & Saic, 'Using noise inconsistencies for blind image forensics' (IVC 2009); "
    "Donoho & Johnstone 1994",
    "Smooth, saturated or blurred regions naturally differ; read with other maps.", order=21,
)  # fmt: skip
COPY_MOVE = Technique(
    "image.copymove", "Copy-move (clone) detection", Category.TAMPERING, IMG, run_copy_move,
    "SIFT keypoints are matched against the same image with the generalised 2-nearest-"
    "neighbour ratio test; pairs closer than 2% of the image are ignored. RANSAC then fits "
    "similarity transforms; a compact, dominant group of at least 12 pairs that move together "
    "is reported as a cloned region.",
    "Amerini et al., 'A SIFT-based forensic method for copy-move attack detection' (TIFS 2011)",
    "Flat regions without keypoints cannot be matched; strongly repetitive textures are "
    "suppressed and may hide small clones.", order=22,
)  # fmt: skip
JPEG_GRID = Technique(
    "image.jpeg_grid", "JPEG grid & double compression", Category.TAMPERING, IMG, run_jpeg_grid,
    "The strength of 8×8 blocking is measured at each of the 8 horizontal and vertical "
    "offsets. A JPEG's own grid sits at offset 0; a dominant or secondary grid elsewhere "
    "means the image was cropped between two compressions. A lossless file with a grid was "
    "JPEG-compressed before.",
    "Bianchi & Piva, 'Detection of non-aligned double JPEG compression' (TIFS 2012); "
    "Fan & de Queiroz, 'Identification of bitmap compression history' (TIP 2003)",
    order=23,
)  # fmt: skip
SPECTRUM = Technique(
    "image.spectrum", "Spectral residual analysis", Category.SYNTHETIC, IMG, run_spectrum,
    "The high-pass residual of the central 512×512 crop is windowed and Fourier transformed. "
    "Isolated periodic peaks are located; peaks on the 1/8 lattice are attributed to JPEG "
    "blocks, others to resampling or generative up-sampling.",
    "Durall et al., 'Watch your up-convolution' (CVPR 2020); Corvi et al., 'On the detection "
    "of synthetic images generated by diffusion models' (ICASSP 2023)",
    "Visual aid; carries no weight in the verdict by itself.", order=40,
)  # fmt: skip
