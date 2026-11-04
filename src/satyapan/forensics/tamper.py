"""M3 — Multimedia Tampering & Manipulation Detection (`src/satyapan/forensics/tamper.py`).

Implements:
1. Image tampering suite:
   - Error Level Analysis (ELA) with edge-normalized block Z-scores + heatmap (`ela_heatmap.png`);
   - Double-JPEG & quantization-table / 8x8 DCT AC histogram periodicity + grid analysis;
   - Copy-move forgery detection via overlapping block descriptor matching & displacement-vector
     clustering + heatmap (`copy_move_heatmap.png`);
   - Noise-residual inconsistency via edge-suppressed Laplacian local variance clustering +
     heatmap (`noise_residual_heatmap.png`) + 4-panel composite (`tamper_composite.png`).
2. Video tampering suite:
   - Duplicated / frozen frame detection;
   - Dropped frame / temporal splice jump detection;
   - Re-encoding & 8x8 macroblock grid signs + timeline chart (`video_tamper_timeline.png`).
3. Audio tampering suite:
   - Cut-and-paste splice transient detection (spectral flux + waveform 2nd-difference spikes);
   - Acoustic environment / background noise-floor step-shift detection + spectrogram with splice
     markers (`audio_splice_spectrogram.png`).

All outputs obey Hard Rule 6: non-absolutist forensic phrasing ("consistent with" /
"inconsistent with"), confidence in [0, 1], and explicit methodological limitations.
"""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from satyapan.forensics.locker import ForensicLocker


@dataclass
class TamperAnalysisResult:
    """Standardized forensic output for M3 multimedia tampering checks."""

    modality: str  # "image" | "video" | "audio"
    finding: str  # "consistent_with_tampering" | "anomalies_detected_verify" | ...
    confidence: float  # in [0.0, 1.0]
    tamper_probability: float  # in [0.0, 1.0]
    statement: str
    why: list[str]
    subchecks: dict[str, Any] = field(default_factory=dict)
    localized_regions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tamper_finding_and_statement(
    prob: float,
    modality: str,
    tau_hi: float = 0.62,
    tau_lo: float = 0.42,
) -> tuple[str, float, str]:
    if prob >= tau_hi:
        conf = round(min(0.97, 0.70 + 0.27 * ((prob - tau_hi) / max(1e-6, 1.0 - tau_hi))), 3)
        stmt = (
            f"Forensic residuals are consistent with localized tampering or post-capture editing "
            f"in this {modality} (tamper likelihood {prob:.2f}, confidence {conf:.2f}). "
            "Findings assist the human examiner and do not by themselves prove intent."
        )
        return "consistent_with_tampering", conf, stmt

    if prob >= tau_lo:
        conf = round(0.50 + 0.20 * ((prob - tau_lo) / max(1e-6, tau_hi - tau_lo)), 3)
        stmt = (
            f"Localized compression or signal anomalies detected in {modality} that are partially "
            f"consistent with editing or re-encoding (tamper likelihood {prob:.2f}, confidence "
            f"{conf:.2f}). Manual verification is recommended."
        )
        return "anomalies_detected_verify", conf, stmt

    conf = round(min(0.95, 0.65 + 0.30 * ((tau_lo - prob) / max(1e-6, tau_lo))), 3)
    stmt = (
        f"Signal and compression characteristics are consistent with an untampered {modality} "
        f"within detector limits (tamper likelihood {prob:.2f}, confidence {conf:.2f}). "
        "Absence of detected anomalies does not guarantee authenticity."
    )
    return "consistent_with_untampered", conf, stmt


def _dct8_matrix() -> np.ndarray:
    """Orthonormal 8x8 DCT-II transform matrix."""
    c = np.zeros((8, 8), dtype=np.float32)
    for k in range(8):
        alpha = np.sqrt(1.0 / 8.0) if k == 0 else np.sqrt(2.0 / 8.0)
        for n in range(8):
            c[k, n] = alpha * np.cos(np.pi * (2 * n + 1) * k / 16.0)
    return c


_DCT8 = _dct8_matrix()


def _edge_magnitude(gray: np.ndarray) -> np.ndarray:
    """Fast finite-difference gradient magnitude on float32 grayscale."""
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, :-1] = np.abs(gray[:, 1:] - gray[:, :-1])
    gy[:-1, :] = np.abs(gray[1:, :] - gray[:-1, :])
    return np.asarray(0.5 * (gx + gy), dtype=np.float32)


def _colorize_heatmap(
    norm_map: np.ndarray, base_rgb: np.ndarray, alpha: float = 0.55
) -> Image.Image:
    """Blend a [0, 1] float anomaly map (warm colormap) over `base_rgb` at matching size."""
    h, w, _ = base_rgb.shape
    pil_map = Image.fromarray((np.clip(norm_map, 0.0, 1.0) * 255.0).astype(np.uint8)).resize(
        (w, h), Image.Resampling.BILINEAR
    )
    v = np.asarray(pil_map, dtype=np.float32) / 255.0
    # Warm forensic colormap: low=dark blue, mid=amber, high=bright red/yellow
    heat_r = np.clip(v * 2.0, 0.0, 1.0) * 255.0
    heat_g = np.clip((v - 0.35) * 1.8, 0.0, 1.0) * 255.0
    heat_b = np.clip((0.5 - v) * 1.6, 0.0, 1.0) * 180.0
    heat_rgb = np.stack([heat_r, heat_g, heat_b], axis=-1)

    weight = alpha * (0.25 + 0.75 * v[:, :, None])
    blended = (1.0 - weight) * base_rgb.astype(np.float32) + weight * heat_rgb
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------------------
# 1. Image Tampering Sub-Detectors
# ---------------------------------------------------------------------------


def ela_analysis(rgb: np.ndarray, quality: int = 90) -> tuple[dict[str, Any], np.ndarray]:
    """Error Level Analysis with edge-normalized 16x16 block Z-score localization."""
    pil_orig = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil_orig.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    resaved = np.asarray(Image.open(buf).convert("RGB"), dtype=np.float32)
    orig_f = rgb.astype(np.float32)

    diff = np.abs(orig_f - resaved).mean(axis=2)
    gray = 0.299 * orig_f[:, :, 0] + 0.587 * orig_f[:, :, 1] + 0.114 * orig_f[:, :, 2]
    edge = _edge_magnitude(gray)

    h, w = diff.shape
    bh, bw = max(1, h // 16), max(1, w // 16)
    d_blocks = diff[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16).mean(axis=(1, 3))
    e_blocks = edge[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16).mean(axis=(1, 3))

    # Edge-normalized block ELA ratio
    norm_ela = d_blocks / (0.40 * e_blocks + 1.2)
    med = float(np.median(norm_ela))
    mad = float(np.median(np.abs(norm_ela - med)))
    z_map = np.abs(norm_ela - med) / (1.4826 * mad + 0.12)

    # Suppress isolated 1-block spikes by requiring 2x2 neighborhood coherence
    if bh >= 2 and bw >= 2:
        p_z = np.pad(z_map, 1, mode="edge")
        smooth_z = 0.5 * z_map + 0.125 * (
            p_z[:-2, 1:-1] + p_z[2:, 1:-1] + p_z[1:-1, :-2] + p_z[1:-1, 2:]
        )
    else:
        smooth_z = z_map

    max_z = float(np.max(smooth_z))
    top_k = max(1, min(6, smooth_z.size // 10))
    top_mean_z = float(np.mean(np.sort(smooth_z.ravel())[::-1][:top_k]))
    outlier_blocks = int(np.sum(smooth_z >= 3.2))
    outlier_ratio = outlier_blocks / max(1, smooth_z.size)
    mean_diff = float(np.mean(diff))

    # Relative z-scores alone fire on smooth, heavily quantised images (little residual to
    # normalise against). Require absolute compression-residual energy before believing them.
    absolute_gate = float(np.clip(mean_diff / 1.6, 0.0, 1.0))
    score = float(np.clip((top_mean_z - 2.8) / 3.2, 0.0, 1.0) * absolute_gate)
    heat = np.clip(smooth_z / max(4.5, max_z), 0.0, 1.0)

    return (
        {
            "score": round(score, 4),
            "max_block_z": round(max_z, 3),
            "top_blocks_mean_z": round(top_mean_z, 3),
            "outlier_blocks": outlier_blocks,
            "outlier_ratio": round(outlier_ratio, 4),
            "mean_ela_diff": round(float(np.mean(diff)), 3),
        },
        heat,
    )


def double_jpeg_analysis(raw_bytes: bytes, rgb: np.ndarray) -> dict[str, Any]:
    """Analyze JPEG quantization tables, 8x8 DCT AC histogram comb periodicity, and block-grid
    consistency to detect double-JPEG compression or spliced non-aligned regions."""
    q_table_present = False
    estimated_q = None
    non_standard_q = False
    img_format = "UNKNOWN"
    luma_q_grid = np.ones((8, 8), dtype=np.float32)
    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            img_format = im.format or "UNKNOWN"
            qtables = getattr(im, "quantization", None)
            if qtables and 0 in qtables:
                q_table_present = True
                luma_q = list(qtables[0])
                if len(luma_q) == 64:
                    luma_q_grid = np.array(luma_q, dtype=np.float32).reshape(8, 8)
                mean_q = float(np.mean(luma_q[:16]))
                # Approximate IJG quality from low-frequency quantization step
                if mean_q <= 1.05:
                    estimated_q = 100
                elif mean_q < 50.0:
                    estimated_q = int(round(max(1, min(99, 100.0 - mean_q * 1.4))))
                else:
                    estimated_q = int(round(max(1, 5000.0 / (mean_q * 2.0))))
                # Check if DC step > AC(0,1) step (unusual in standard camera/IJG tables)
                if len(luma_q) >= 8 and luma_q[0] > luma_q[1] * 2.5:
                    non_standard_q = True
    except Exception:  # noqa: BLE001
        pass

    orig_f = rgb.astype(np.float32)
    gray = 0.299 * orig_f[:, :, 0] + 0.587 * orig_f[:, :, 1] + 0.114 * orig_f[:, :, 2]
    h, w = gray.shape
    bh, bw = h // 8, w // 8
    if bh < 4 or bw < 4:
        return {
            "score": 0.0,
            "format": img_format,
            "q_table_present": q_table_present,
            "estimated_jpeg_quality": estimated_q,
            "dct_comb_periodicity": 0.0,
            "block_grid_mismatch": 0.0,
        }

    # 1. 8x8 2D DCT AC coefficient histogram periodicity (Lukas & Fridrich comb valley check
    # normalized by the current JPEG's quantization step so single-JPEG has consecutive bins)
    blocks = gray[: bh * 8, : bw * 8].reshape(bh, 8, bw, 8).transpose(0, 2, 1, 3) - 128.0
    dct_blocks = np.einsum("ij,abjk,lk->abil", _DCT8, blocks, _DCT8)

    comb_valleys = 0
    for u, v in [(0, 1), (1, 0), (1, 1), (0, 2), (2, 0)]:
        q_step = max(1.0, float(luma_q_grid[u, v]))
        coeffs = np.round(dct_blocks[:, :, u, v] / q_step).ravel()
        coeffs = coeffs[(coeffs >= -20) & (coeffs <= 20) & (coeffs != 0)]
        if len(coeffs) < 120:
            continue
        hist, _ = np.histogram(coeffs, bins=np.arange(-20.5, 21.5, 1.0))
        # Double quantization is symmetric around 0: require symmetric comb dips at +k and -k
        for k in range(2, 11):
            pos_i = 20 + k
            neg_i = 20 - k
            pos_ok = (
                hist[pos_i - 1] >= 14
                and hist[pos_i + 1] >= 14
                and hist[pos_i] <= 0.15 * min(hist[pos_i - 1], hist[pos_i + 1])
            )
            neg_ok = (
                hist[neg_i - 1] >= 14
                and hist[neg_i + 1] >= 14
                and hist[neg_i] <= 0.15 * min(hist[neg_i - 1], hist[neg_i + 1])
            )
            if pos_ok and neg_ok:
                comb_valleys += 1
    dct_comb = float(np.clip(comb_valleys / 3.0, 0.0, 1.0))

    # 2. 2D (horiz + vert) 8x8 block boundary vs interior gradient ratio across 32x32 patches
    horiz_diff = np.abs(gray[:, 1:] - gray[:, :-1])
    vert_diff = np.abs(gray[1:, :] - gray[:-1, :])
    mh, mw = (h - 1) // 32, (w - 1) // 32
    grid_mismatch = 0.0
    if mh >= 2 and mw >= 2:
        ratios = []
        for iy in range(mh):
            for ix in range(mw):
                ph = horiz_diff[iy * 32 : (iy + 1) * 32, ix * 32 : (ix + 1) * 32]
                pv = vert_diff[iy * 32 : (iy + 1) * 32, ix * 32 : (ix + 1) * 32]
                bh_c = float(np.mean(ph[:, 7::8]))
                nbh_c = float(np.mean(np.delete(ph, np.arange(7, ph.shape[1], 8), axis=1)))
                bv_c = float(np.mean(pv[7::8, :]))
                nbv_c = float(np.mean(np.delete(pv, np.arange(7, pv.shape[0], 8), axis=0)))
                r_2d = (bh_c + bv_c) / (nbh_c + nbv_c + 0.8)
                ratios.append(r_2d)
        r_arr = np.array(ratios, dtype=np.float32)
        global_grid = float(np.median(r_arr))
        # A genuine 8x8 JPEG grid must be visible across most of the frame, and one region must
        # have lost it. Small images (few patches) are too noisy to make this call at all.
        if r_arr.size >= 12 and global_grid >= 1.30:
            min_r = float(np.min(r_arr))
            if min_r <= 0.55 * global_grid:
                grid_mismatch = float(
                    np.clip((0.55 * global_grid - min_r) / (0.35 * global_grid), 0.0, 1.0)
                )

    score = float(
        np.clip(
            max(dct_comb, grid_mismatch, 0.45 if non_standard_q else 0.0),
            0.0,
            1.0,
        )
    )
    return {
        "score": round(score, 4),
        "format": img_format,
        "q_table_present": q_table_present,
        "estimated_jpeg_quality": estimated_q,
        "non_standard_q_table": non_standard_q,
        "dct_comb_periodicity": round(dct_comb, 4),
        "block_grid_mismatch": round(grid_mismatch, 4),
    }


def copy_move_analysis(rgb: np.ndarray) -> tuple[dict[str, Any], np.ndarray]:
    """Detect cloned (copy-move) regions within the same image via overlapping block descriptor
    lexicographic matching and displacement-vector clustering."""
    h_orig, w_orig, _ = rgb.shape
    scale = min(1.0, 256.0 / max(h_orig, w_orig))
    if scale < 1.0:
        w = max(32, int(round(w_orig * scale)))
        h = max(32, int(round(h_orig * scale)))
        work_rgb = np.asarray(
            Image.fromarray(rgb).resize((w, h), Image.Resampling.BILINEAR), dtype=np.float32
        )
    else:
        h, w = h_orig, w_orig
        work_rgb = rgb.astype(np.float32)

    gray = 0.299 * work_rgb[:, :, 0] + 0.587 * work_rgb[:, :, 1] + 0.114 * work_rgb[:, :, 2]
    p_gray = np.pad(gray, 1, mode="reflect")
    lap_full = p_gray[1:-1, 1:-1] - 0.25 * (
        p_gray[:-2, 1:-1] + p_gray[2:, 1:-1] + p_gray[1:-1, :-2] + p_gray[1:-1, 2:]
    )
    bsize = 16
    stride = 4
    ys = list(range(0, h - bsize + 1, stride))
    xs = list(range(0, w - bsize + 1, stride))

    coords: list[tuple[int, int]] = []
    feats: list[np.ndarray] = []

    for y in ys:
        for x in xs:
            blk = gray[y : y + bsize, x : x + bsize]
            std = float(np.std(blk))
            hp = lap_full[y : y + bsize, x : x + bsize]
            hp_std = float(np.std(hp))
            if std < 12.0 or hp_std < 4.2:
                # Skip smooth gradients and background sensor noise; match textured objects
                continue
            sub_2d = blk.reshape(4, 4, 4, 4).mean(axis=(1, 3))
            sub = sub_2d.ravel()
            sub_norm = (sub - np.mean(sub)) / (std + 1e-5)
            rgb_mean = work_rgb[y : y + bsize, x : x + bsize].mean(axis=(0, 1)) / 24.0
            # Quantize softly so blocks shifted by 1-2 px still land in adjacent sort buckets
            desc = np.concatenate([np.round(sub_norm * 1.5), np.round(rgb_mean)])
            coords.append((y, x))
            feats.append(desc)

    mask = np.zeros((h, w), dtype=np.float32)
    if len(feats) < 10:
        return (
            {
                "score": 0.0,
                "cloned_block_pairs": 0,
                "dominant_shift_px": None,
                "textured_blocks_checked": len(feats),
            },
            mask,
        )

    feat_mat = np.stack(feats, axis=0)
    # Lexicographic sort of block descriptors
    order = np.lexsort(feat_mat.T[::-1])
    shift_clusters: dict[tuple[int, int], list[tuple[tuple[int, int], tuple[int, int]]]] = {}

    window = 24
    for i in range(len(order)):
        idx1 = int(order[i])
        y1, x1 = coords[idx1]
        p1 = work_rgb[y1 : y1 + bsize, x1 : x1 + bsize]
        hp1 = lap_full[y1 : y1 + bsize, x1 : x1 + bsize].ravel()
        hp1 = hp1 - float(np.mean(hp1))
        n1 = float(np.linalg.norm(hp1))
        if n1 < 1e-4:
            continue
        for j in range(i + 1, min(len(order), i + 1 + window)):
            idx2 = int(order[j])
            y2_base, x2_base = coords[idx2]
            if float(np.hypot(y2_base - y1, x2_base - x1)) < 24.0:
                continue
            # Search +-2 px around (y2_base, x2_base) for sub-stride shifts
            # JPEG re-compression shifts pixel values by several levels inside textured regions,
            # so allow more absolute difference when the block carries strong texture energy
            # (high-pass correlation must stay high, which smooth gradients cannot fake).
            mad_allow = 3.0 + 0.16 * (n1 / max(1.0, float(bsize)))
            matched_pos: tuple[int, int] | None = None
            for oy in (-2, -1, 0, 1, 2):
                yy2 = y2_base + oy
                if yy2 < 0 or yy2 + bsize > h:
                    continue
                for ox in (-2, -1, 0, 1, 2):
                    xx2 = x2_base + ox
                    if xx2 < 0 or xx2 + bsize > w:
                        continue
                    p2 = work_rgb[yy2 : yy2 + bsize, xx2 : xx2 + bsize]
                    if float(np.mean(np.abs(p1 - p2))) > mad_allow:
                        continue
                    hp2 = lap_full[yy2 : yy2 + bsize, xx2 : xx2 + bsize].ravel()
                    hp2 = hp2 - float(np.mean(hp2))
                    denom = n1 * float(np.linalg.norm(hp2))
                    if denom > 1e-4 and float(np.sum(hp1 * hp2)) / denom >= 0.88:
                        matched_pos = (yy2, xx2)
                        break
                if matched_pos is not None:
                    break
            if matched_pos is None:
                continue
            y2, x2 = matched_pos
            # Canonicalize shift vector direction so (y1->y2) and (y2->y1) map to same shift
            if (y1, x1) < (y2, x2):
                dy, dx = y2 - y1, x2 - x1
                pair = ((y1, x1), (y2, x2))
            else:
                dy, dx = y1 - y2, x1 - x2
                pair = ((y2, x2), (y1, x1))
            key = (int(round(dy / 4.0)) * 4, int(round(dx / 4.0)) * 4)
            shift_clusters.setdefault(key, []).append(pair)

    best_shift: tuple[int, int] | None = None
    best_pairs: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for k, pairs in shift_clusters.items():
        # Deduplicate source block coordinates within the cluster
        unique_srcs = {p[0] for p in pairs}
        if len(unique_srcs) > len({p[0] for p in best_pairs}):
            best_shift = k
            best_pairs = pairs

    unique_count = len({p[0] for p in best_pairs})
    if unique_count >= 5 and best_shift is not None:
        for (y1, x1), (y2, x2) in best_pairs:
            mask[y1 : y1 + bsize, x1 : x1 + bsize] = 1.0
            mask[y2 : y2 + bsize, x2 : x2 + bsize] = 0.85
        score = float(np.clip((unique_count - 4.0) / 10.0, 0.0, 1.0))
    else:
        score = 0.0

    return (
        {
            "score": round(score, 4),
            "cloned_block_pairs": unique_count,
            "dominant_shift_px": list(best_shift) if (best_shift and unique_count >= 5) else None,
            "textured_blocks_checked": len(feats),
        },
        mask,
    )


def noise_residual_analysis(rgb: np.ndarray) -> tuple[dict[str, Any], np.ndarray]:
    """Detect localized sensor-noise inconsistencies (foreign spliced noise or airbrushed/inpainted
    regions) using edge-suppressed high-pass residual block variance Z-scores."""
    orig_f = rgb.astype(np.float32)
    gray = 0.299 * orig_f[:, :, 0] + 0.587 * orig_f[:, :, 1] + 0.114 * orig_f[:, :, 2]

    p = np.pad(gray, 1, mode="reflect")
    lap = p[1:-1, 1:-1] - 0.25 * (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
    edge = _edge_magnitude(gray)
    # Suppress structural edges so high-contrast boundaries don't masquerade as sensor noise
    norm_res = lap / (1.0 + 0.45 * edge)

    h, w = gray.shape
    bh, bw = max(1, h // 16), max(1, w // 16)
    blocks = norm_res[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16)
    block_std = np.sqrt(np.var(blocks, axis=(1, 3)) + 1e-6)
    log_std = np.log1p(block_std)

    med = float(np.median(log_std))
    mad = float(np.median(np.abs(log_std - med)))
    z_map = np.abs(log_std - med) / (1.4826 * mad + 0.08)

    # Require 2x2 spatial neighborhood consistency to suppress isolated texture patches
    if bh >= 2 and bw >= 2:
        pz = np.pad(z_map, 1, mode="edge")
        smooth_z = 0.5 * z_map + 0.125 * (
            pz[:-2, 1:-1] + pz[2:, 1:-1] + pz[1:-1, :-2] + pz[1:-1, 2:]
        )
    else:
        smooth_z = z_map

    max_z = float(np.max(smooth_z))
    top_k = max(1, min(6, smooth_z.size // 10))
    top_mean_z = float(np.mean(np.sort(smooth_z.ravel())[::-1][:top_k]))
    anomalous_blocks = int(np.sum(smooth_z >= 3.3))
    median_sigma = float(np.median(block_std))
    p95_sigma = float(np.percentile(block_std, 95))
    sigma_gap = max(0.0, p95_sigma - median_sigma)

    # Relative outliers are meaningless when the whole frame has one uniform (quantised) noise
    # floor. A genuine splice or airbrush leaves a measurable absolute gap between the noisiest
    # region and the frame's typical noise level, so gate on that gap, not on the median.
    absolute_gate = float(np.clip(sigma_gap / 1.0, 0.0, 1.0))
    score = float(np.clip((top_mean_z - 2.4) / 3.0, 0.0, 1.0) * absolute_gate)
    heat = np.clip(smooth_z / max(4.5, max_z), 0.0, 1.0)

    return (
        {
            "score": round(score, 4),
            "max_noise_z": round(max_z, 3),
            "top_blocks_noise_z": round(top_mean_z, 3),
            "anomalous_blocks": anomalous_blocks,
            "median_noise_sigma": round(median_sigma, 3),
            "noise_sigma_gap": round(sigma_gap, 3),
        },
        heat,
    )


def analyze_image_tampering(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
) -> TamperAnalysisResult:
    """Run all 4 image tampering detectors (ELA, Double-JPEG, Copy-Move, Noise-Residual) on
    `working_path` and generate visual heatmaps."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    from satyapan.imagecheck.face import decode_image

    raw_bytes = p.read_bytes()
    rgb = decode_image(raw_bytes)

    ela_info, ela_heat = ela_analysis(rgb)
    djpeg_info = double_jpeg_analysis(raw_bytes, rgb)
    cm_info, cm_heat = copy_move_analysis(rgb)
    noise_info, noise_heat = noise_residual_analysis(rgb)

    scores = [
        float(ela_info["score"]),
        float(djpeg_info["score"]),
        float(cm_info["score"]),
        float(noise_info["score"]),
    ]
    sorted_s = sorted(scores, reverse=True)
    # Strongest indicator + corroboration bonus when >=2 independent checks agree
    tamper_prob = round(min(1.0, sorted_s[0] + 0.18 * sorted_s[1]), 4)

    why: list[str] = []
    if ela_info["score"] >= 0.42:
        why.append(
            f"Error Level Analysis (ELA) detected localized compression-residual outliers "
            f"(top block Z={ela_info['top_blocks_mean_z']:.2f}, "
            f"{ela_info['outlier_blocks']} outlier blocks)."
        )
    if cm_info["score"] >= 0.42:
        why.append(
            f"Copy-move detector matched {cm_info['cloned_block_pairs']} spatially contiguous "
            f"cloned blocks at displacement vector {cm_info['dominant_shift_px']} px."
        )
    if noise_info["score"] >= 0.42:
        why.append(
            f"Noise-residual analysis found regional sensor-noise variance inconsistency "
            f"(top block Z={noise_info['top_blocks_noise_z']:.2f}, "
            f"{noise_info['anomalous_blocks']} blocks)."
        )
    if djpeg_info["score"] >= 0.42:
        why.append(
            f"Double-JPEG / DCT analysis detected periodic quantization comb or 8x8 grid mismatch "
            f"(comb={djpeg_info['dct_comb_periodicity']:.2f}, "
            f"grid_mismatch={djpeg_info['block_grid_mismatch']:.2f})."
        )
    if not why:
        why.append(
            "ELA, double-JPEG DCT histogram, copy-move block matching, and noise-residual variance "
            f"checks remained within expected uniform bounds (max score {tamper_prob:.2f})."
        )

    finding, conf, statement = _tamper_finding_and_statement(tamper_prob, modality="image")

    artifacts: dict[str, str] = {}
    if artifact_dir is not None:
        adir = Path(artifact_dir)
        adir.mkdir(parents=True, exist_ok=True)
        ela_img = _colorize_heatmap(ela_heat, rgb)
        cm_img = _colorize_heatmap(cm_heat, rgb, alpha=0.65)
        nr_img = _colorize_heatmap(noise_heat, rgb)

        ela_path = adir / "ela_heatmap.png"
        cm_path = adir / "copy_move_heatmap.png"
        nr_path = adir / "noise_residual_heatmap.png"
        comp_path = adir / "tamper_composite.png"

        ela_img.save(ela_path, format="PNG")
        cm_img.save(cm_path, format="PNG")
        nr_img.save(nr_path, format="PNG")

        # 4-panel composite for dashboard and PDF report
        panel = Image.new("RGB", (820, 235), (18, 22, 31))
        draw = ImageDraw.Draw(panel)
        titles = ["Original Working Copy", "ELA Heatmap", "Noise Residual Map", "Copy-Move Map"]
        imgs = [Image.fromarray(rgb), ela_img, nr_img, cm_img]
        for idx, (t_txt, im_p) in enumerate(zip(titles, imgs, strict=True)):
            x0 = 10 + idx * 202
            panel.paste(im_p.resize((192, 192), Image.Resampling.BILINEAR), (x0, 30))
            draw.text((x0 + 4, 8), t_txt, fill=(220, 226, 236))
        panel.save(comp_path, format="PNG")

        artifacts = {
            "ela_heatmap": str(ela_path),
            "copy_move_heatmap": str(cm_path),
            "noise_residual_heatmap": str(nr_path),
            "tamper_composite": str(comp_path),
        }

    return TamperAnalysisResult(
        modality="image",
        finding=finding,
        confidence=conf,
        tamper_probability=tamper_prob,
        statement=statement,
        why=why,
        subchecks={
            "ela": ela_info,
            "double_jpeg": djpeg_info,
            "copy_move": cm_info,
            "noise_residual": noise_info,
        },
        artifacts=artifacts,
        limitations=[
            (
                "ELA and double-JPEG checks are designed for JPEG-compressed imagery and have "
                "reduced sensitivity on lossless PNGs or heavily downscaled messaging copies."
            ),
            (
                "Copy-move detection requires textured source regions; cloning of flat uniform "
                "backgrounds (e.g., solid white paper) may not produce distinct block matches."
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 2. Video Tampering Detector (Duplicated/Dropped Frames & Re-encoding Signs)
# ---------------------------------------------------------------------------


def _render_video_tamper_timeline(
    times: list[float],
    diffs: list[float],
    dup_indices: list[int],
    drop_indices: list[int],
    out_path: Path,
) -> None:
    w, h = 560, 220
    img = Image.new("RGB", (w, h), (18, 22, 31))
    draw = ImageDraw.Draw(img)
    pad_l, pad_r, pad_t, pad_b = 46, 20, 28, 32
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    draw.rectangle([pad_l, pad_t, pad_l + pw, pad_t + ph], outline=(55, 65, 81), width=1)
    draw.text(
        (12, 6),
        "Inter-Frame Motion Difference & Temporal Discontinuity Timeline",
        fill=(220, 226, 236),
    )

    if diffs:
        max_d = max(float(np.max(diffs)) * 1.15, 1.0)
        n = len(diffs)
        pts = []
        for i, d in enumerate(diffs):
            x = pad_l + int((i / max(1, n - 1)) * pw) if n > 1 else pad_l + pw // 2
            y = pad_t + int((1.0 - min(1.0, d / max_d)) * ph)
            pts.append((x, y))
        if len(pts) >= 2:
            draw.line(pts, fill=(56, 189, 248), width=2)
        for di in drop_indices:
            if 0 <= di < len(pts):
                x, y = pts[di]
                draw.line([(x, pad_t), (x, pad_t + ph)], fill=(239, 68, 68), width=2)
                draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(239, 68, 68))
        for du in dup_indices:
            if 0 <= du < len(pts):
                x, y = pts[du]
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(250, 204, 21))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def analyze_video_tampering(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
    max_frames: int = 180,
) -> TamperAnalysisResult:
    """Inspect a video working copy for duplicated/frozen frames, dropped frames / temporal splices,
    and re-encoding macroblock signs."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    try:
        import cv2
    except ImportError as exc:  # video extra not installed (slim offline container)
        return TamperAnalysisResult(
            modality="video",
            finding="inconclusive_abstain",
            confidence=0.0,
            tamper_probability=0.0,
            statement=(
                "Video decoding dependencies are not installed here, so temporal tampering "
                "checks abstained instead of guessing."
            ),
            why=[f"OpenCV/FFmpeg bindings unavailable ({exc})."],
            limitations=["Install the `video` extra to run video tampering checks."],
        )

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        raise ValueError(f"Cannot decode video file: {p}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    if not 1.0 <= fps <= 240.0:
        fps = 25.0

    grays: list[np.ndarray] = []
    times: list[float] = []
    block_ratios: list[float] = []

    idx = 0
    try:
        while idx < max_frames:
            ok, bgr = cap.read()
            if not ok:
                break
            g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
            # Downscale to <=256 width for fast inter-frame comparison
            if g.shape[1] > 256:
                scale = 256.0 / g.shape[1]
                g = np.asarray(
                    cv2.resize(g, (256, max(16, int(round(g.shape[0] * scale))))),
                    dtype=np.float32,
                )
            grays.append(g)
            times.append(idx / fps)
            # 8x8 macroblock boundary strength
            h_diff = np.abs(g[:, 1:] - g[:, :-1])
            if h_diff.shape[1] >= 16:
                b_col = float(np.mean(h_diff[:, 7::8]))
                nb_col = float(np.mean(np.delete(h_diff, np.arange(7, h_diff.shape[1], 8), axis=1)))
                block_ratios.append(b_col / (nb_col + 0.5))
            idx += 1
    finally:
        cap.release()

    if len(grays) < 4:
        return TamperAnalysisResult(
            modality="video",
            finding="inconclusive_abstain",
            confidence=0.0,
            tamper_probability=0.0,
            statement="Video stream has fewer than 4 frames; temporal tampering checks abstained.",
            why=["Insufficient frame count for inter-frame analysis."],
        )

    diffs: list[float] = []
    for i in range(1, len(grays)):
        diffs.append(float(np.mean(np.abs(grays[i] - grays[i - 1]))))

    d_arr = np.array(diffs, dtype=np.float32)
    med_d = float(np.median(d_arr))
    mad_d = float(np.median(np.abs(d_arr - med_d)))

    # 1. Duplicated frames: near-zero difference (<0.08) during active scene motion (med_d > 0.8)
    dup_indices = [i for i, d in enumerate(diffs) if d < 0.08] if med_d > 0.8 else []
    dup_ratio = len(dup_indices) / max(1, len(diffs))

    # 2. Dropped frames / splice jumps: robust outlier spikes
    z_diffs = (d_arr - med_d) / (1.4826 * mad_d + 0.25)
    drop_indices = [
        i for i, (d, z) in enumerate(zip(diffs, z_diffs, strict=True)) if z >= 5.2 and d >= 5.0
    ]

    # 3. Re-encoding / macroblock grid variation across frames
    grid_std = float(np.std(block_ratios)) if block_ratios else 0.0
    grid_mean = float(np.mean(block_ratios)) if block_ratios else 1.0
    reencode_score = float(
        np.clip(max((grid_mean - 1.22) / 0.35, (grid_std - 0.08) / 0.12), 0.0, 1.0)
    )

    dup_score = float(np.clip(len(dup_indices) / 3.0, 0.0, 1.0))
    drop_score = float(np.clip(len(drop_indices) / 1.5, 0.0, 1.0))
    tamper_prob = round(max(dup_score, drop_score, 0.75 * reencode_score), 4)

    why: list[str] = []
    localized: list[dict[str, Any]] = []
    if dup_indices:
        dup_times = [round(times[i + 1], 2) for i in dup_indices[:6]]
        why.append(
            f"Detected {len(dup_indices)} duplicated/frozen frame intervals "
            f"({dup_ratio:.1%} of stream) at timestamps {dup_times}s during active scene motion "
            f"(median diff {med_d:.2f})."
        )
        localized.append({"type": "duplicated_frames", "timestamps_s": dup_times})
    if drop_indices:
        drop_times = [round(times[i + 1], 2) for i in drop_indices[:6]]
        max_jump_z = float(np.max(z_diffs[drop_indices]))
        why.append(
            f"Detected {len(drop_indices)} abrupt inter-frame discontinuity spike(s) at "
            f"{drop_times}s (max Z={max_jump_z:.1f}), consistent with dropped/spliced frames."
        )
        localized.append({"type": "dropped_or_spliced_frames", "timestamps_s": drop_times})
    if reencode_score >= 0.45:
        why.append(
            f"Macroblock 8x8 boundary energy (mean={grid_mean:.2f}, std={grid_std:.3f}) indicates "
            "heavy quantization or multi-generation re-encoding."
        )
    if not why:
        why.append(
            f"Inter-frame motion progression across {len(grays)} frames showed no duplicated runs "
            f"or temporal splice discontinuities (median frame diff {med_d:.2f})."
        )

    finding, conf, statement = _tamper_finding_and_statement(tamper_prob, modality="video")

    artifacts: dict[str, str] = {}
    if artifact_dir is not None:
        chart_path = Path(artifact_dir) / "video_tamper_timeline.png"
        _render_video_tamper_timeline(times[1:], diffs, dup_indices, drop_indices, chart_path)
        artifacts["video_tamper_timeline"] = str(chart_path)

    return TamperAnalysisResult(
        modality="video",
        finding=finding,
        confidence=conf,
        tamper_probability=tamper_prob,
        statement=statement,
        why=why,
        subchecks={
            "frames_inspected": len(grays),
            "fps": round(fps, 2),
            "median_frame_diff": round(med_d, 3),
            "duplicated_frame_count": len(dup_indices),
            "dropped_frame_spikes": len(drop_indices),
            "macroblock_grid_mean": round(grid_mean, 3),
            "macroblock_grid_std": round(grid_std, 4),
            "reencode_score": round(reencode_score, 4),
        },
        localized_regions=localized,
        artifacts=artifacts,
        limitations=[
            (
                "Static talking-head or slide videos naturally exhibit low inter-frame "
                "differences; duplicated-frame detection gates on active median scene motion."
            ),
            (
                "Hard camera scene cuts in edited broadcasts produce inter-frame spikes similar to "
                "frame drops and require examiner visual inspection at the flagged timestamp."
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 3. Audio Tampering Detector (Splice Transients & Noise-Floor Discontinuities)
# ---------------------------------------------------------------------------


def _render_audio_spectrogram(
    spec_db: np.ndarray,
    duration_s: float,
    splice_times: list[float],
    out_path: Path,
) -> None:
    """Render a log-power spectrogram with vertical red markers at detected splice points."""
    w, h = 560, 220
    img = Image.new("RGB", (w, h), (18, 22, 31))
    draw = ImageDraw.Draw(img)
    pad_l, pad_r, pad_t, pad_b = 42, 18, 28, 28
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    # spec_db is (n_frames, n_freq); transpose to (n_freq, n_frames) with low freq at bottom
    s_flip = spec_db.T[::-1, :]
    s_norm = (s_flip - np.min(s_flip)) / max(1e-6, float(np.max(s_flip) - np.min(s_flip)))
    s_u8 = (s_norm * 255.0).astype(np.uint8)
    spec_rgb = np.stack(
        [
            s_u8,
            ((s_norm**1.5) * 210.0).astype(np.uint8),
            ((1.0 - s_norm) * 150.0).astype(np.uint8),
        ],
        axis=-1,
    )
    pil_spec = Image.fromarray(spec_rgb).resize((pw, ph), Image.Resampling.BILINEAR)
    img.paste(pil_spec, (pad_l, pad_t))
    draw.rectangle([pad_l, pad_t, pad_l + pw, pad_t + ph], outline=(55, 65, 81), width=1)
    draw.text((12, 6), "Audio Log-Spectrogram & Splice Discontinuity Markers", fill=(220, 226, 236))

    for st in splice_times:
        if duration_s > 0:
            x = pad_l + int(np.clip(st / duration_s, 0.0, 1.0) * pw)
            draw.line([(x, pad_t), (x, pad_t + ph)], fill=(239, 68, 68), width=2)
            draw.text((max(pad_l + 2, x - 16), pad_t + 4), f"{st:.2f}s", fill=(254, 202, 202))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def analyze_audio_tampering(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
) -> TamperAnalysisResult:
    """Inspect an audio working copy for cut-and-paste splice transients and background noise-floor
    discontinuities."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    from satyapan.voice.audio_io import decode_to_16k_mono

    raw_bytes = p.read_bytes()
    ext = p.suffix.lower().lstrip(".")
    mime_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "opus": "audio/opus",
        "m4a": "audio/mp4",
        "flac": "audio/flac",
        "webm": "audio/webm",
    }
    try:
        samples = np.asarray(
            decode_to_16k_mono(raw_bytes, mime_map.get(ext, "audio/wav")), np.float32
        )
    except ValueError as exc:
        return TamperAnalysisResult(
            modality="audio",
            finding="inconclusive_abstain",
            confidence=0.0,
            tamper_probability=0.0,
            statement="Audio could not be decoded here, so splice checks abstained.",
            why=[f"Decoder error: {exc}"],
            limitations=["Install ffmpeg to run audio tampering checks."],
        )
    sr = 16000
    duration_s = len(samples) / float(sr)
    if duration_s < 1.0:
        return TamperAnalysisResult(
            modality="audio",
            finding="inconclusive_abstain",
            confidence=0.0,
            tamper_probability=0.0,
            statement="Audio clip is shorter than 1.0s; splice and noise-floor checks abstained.",
            why=["Recording too short for multi-segment comparison."],
        )

    # 1. Short-time spectrogram (32ms window = 512, 16ms hop = 256)
    win_len, hop = 512, 256
    n_frames = max(2, (len(samples) - win_len) // hop)
    hann = np.hanning(win_len).astype(np.float32)
    specs = []
    rms_list = []
    for i in range(n_frames):
        seg = samples[i * hop : i * hop + win_len] * hann
        rms_list.append(float(np.sqrt(np.mean(seg**2) + 1e-12)))
        specs.append(np.abs(np.fft.rfft(seg)) + 1e-7)
    spec_mat = np.stack(specs, axis=0)
    spec_db = 20.0 * np.log10(spec_mat)

    # 2. High-pass waveform 2nd-difference transient detector (sample-level phase/amplitude cuts)
    d2 = np.abs(samples[2:] - 2.0 * samples[1:-1] + samples[:-2])
    block_len = 320  # 20ms blocks
    n_b = len(d2) // block_len
    d2_blocks = d2[: n_b * block_len].reshape(n_b, block_len)
    # Ratio of single-sample peak to block RMS of d2 (a clean cut has a sharp 1-2 sample transient!)
    peak_to_rms = np.max(d2_blocks, axis=1) / (np.sqrt(np.mean(d2_blocks**2, axis=1)) + 1e-5)
    # Ignore near-silent blocks
    block_amp = np.max(np.abs(samples[: n_b * block_len].reshape(n_b, block_len)), axis=1)
    active_mask = block_amp > 0.02
    if int(np.sum(active_mask)) >= 5:
        med_pr = float(np.median(peak_to_rms[active_mask]))
        mad_pr = float(np.median(np.abs(peak_to_rms[active_mask] - med_pr)))
        pr_z = (peak_to_rms - med_pr) / (1.4826 * mad_pr + 0.35)
        pr_z[~active_mask] = 0.0
    else:
        pr_z = np.zeros_like(peak_to_rms)

    # Exclude first and last 60ms boundary
    if len(pr_z) > 6:
        pr_z[:3] = 0.0
        pr_z[-3:] = 0.0
    transient_indices = [int(i) for i, z in enumerate(pr_z) if z >= 7.5]
    transient_times = [round((i * block_len) / float(sr), 2) for i in transient_indices]

    # 3. Inter-segment acoustic environment / noise-floor step shift (0.5s segments)
    seg_frames = max(4, int(round(0.5 * sr / hop)))
    n_segs = n_frames // seg_frames
    floor_db: list[float] = []
    hf_ratios: list[float] = []
    for s_idx in range(n_segs):
        s_rms = rms_list[s_idx * seg_frames : (s_idx + 1) * seg_frames]
        s_spec = spec_db[s_idx * seg_frames : (s_idx + 1) * seg_frames]
        # 25th percentile RMS represents background floor in that 0.5s window
        p25 = float(np.percentile(s_rms, 25))
        floor_db.append(20.0 * float(np.log10(max(p25, 1e-6))))
        # High-frequency vs low-frequency spectral balance
        mid = s_spec.shape[1] // 2
        hf_ratios.append(float(np.mean(s_spec[:, mid:]) - np.mean(s_spec[:, :mid])))

    floor_jumps: list[tuple[float, float]] = []
    for s_idx in range(1, len(floor_db)):
        jump = abs(floor_db[s_idx] - floor_db[s_idx - 1])
        hf_jump = abs(hf_ratios[s_idx] - hf_ratios[s_idx - 1])
        if jump >= 8.5 or hf_jump >= 9.0:
            t_jump = round(s_idx * seg_frames * hop / float(sr), 2)
            floor_jumps.append((t_jump, round(max(jump, hf_jump), 2)))

    splice_times = sorted({*transient_times[:4], *(t for t, _ in floor_jumps[:4])})
    max_pr_z = float(np.max(pr_z)) if len(pr_z) else 0.0
    max_floor_jump = max((j for _, j in floor_jumps), default=0.0)

    transient_score = float(np.clip((max_pr_z - 5.5) / 5.0, 0.0, 1.0))
    floor_score = float(np.clip((max_floor_jump - 6.5) / 7.0, 0.0, 1.0))
    tamper_prob = round(max(transient_score, floor_score), 4)

    why: list[str] = []
    localized: list[dict[str, Any]] = []
    if transient_times:
        why.append(
            f"Detected waveform/phase discontinuity transient(s) at {transient_times[:4]}s "
            f"(peak-to-RMS Z={max_pr_z:.1f}), consistent with an unsmoothed audio cut/splice."
        )
        localized.append({"type": "waveform_splice_transient", "timestamps_s": transient_times[:4]})
    if floor_jumps:
        why.append(
            f"Detected abrupt acoustic background/spectral step change of {max_floor_jump:.1f} dB "
            f"at {[t for t, _ in floor_jumps[:4]]}s, consistent with splicing distinct rooms."
        )
        localized.append(
            {"type": "noise_floor_discontinuity", "timestamps_s": [t for t, _ in floor_jumps[:4]]}
        )
    if not why:
        why.append(
            f"Waveform continuity and 0.5s background noise-floor profile across {duration_s:.1f}s "
            f"showed no splice transients or environment shifts (max transient Z={max_pr_z:.1f})."
        )

    finding, conf, statement = _tamper_finding_and_statement(tamper_prob, modality="audio")

    artifacts: dict[str, str] = {}
    if artifact_dir is not None:
        spec_path = Path(artifact_dir) / "audio_splice_spectrogram.png"
        _render_audio_spectrogram(spec_db, duration_s, splice_times, spec_path)
        artifacts["audio_splice_spectrogram"] = str(spec_path)

    return TamperAnalysisResult(
        modality="audio",
        finding=finding,
        confidence=conf,
        tamper_probability=tamper_prob,
        statement=statement,
        why=why,
        subchecks={
            "duration_seconds": round(duration_s, 2),
            "max_transient_z": round(max_pr_z, 3),
            "transient_Timestamps_s": transient_times[:6],
            "max_noise_floor_jump_db": round(max_floor_jump, 2),
            "noise_floor_jumps": [{"time_s": t, "jump_db": j} for t, j in floor_jumps[:6]],
        },
        localized_regions=localized,
        artifacts=artifacts,
        limitations=[
            (
                "Cross-faded splices performed in a DAW with matched room tone attenuate "
                "sample-level transients and require semantic/prosodic analysis."
            ),
            (
                "Sudden impulsive background sounds (e.g., mic tap or door slam) can trigger "
                "transient spikes and should be verified by listening to the marked timestamp."
            ),
        ],
    )
