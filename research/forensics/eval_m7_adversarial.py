"""M7 Adversarial Robustness Red-Team Benchmark (`research/forensics/eval_m7_adversarial.py`).

Evaluates how our forensic detectors (M2 Whole-Image Synthetic, M3 Image Tampering Suite, M4
Provenance & C2PA) behave under 5 realistic attacker post-processing countermeasures
(`SEED = 20261107`, n=30 manipulated/synthetic + 30 authentic controls per attack):
1. `jpeg_q50_reencode`: Re-saving through lossy JPEG quality 50;
2. `resize_0.5x_1.0x`: Downscaling by 50% and upscaling back to original dimensions;
3. `crop_15pct`: Cropping 15% off borders (shifting 8x8 JPEG block alignment and breaking C2PA);
4. `gaussian_noise_sigma6`: Adding zero-mean Gaussian noise (sigma=6.0) across all channels;
5. `metadata_and_c2pa_strip`: Stripping all EXIF, XMP, PNG text chunks, and C2PA JUMBF boxes,
   comparing metadata-only detection (which drops to 0%) vs our combined pixel+metadata pipeline.
"""

from __future__ import annotations

import io
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import numpy as np  # provenance: seeded-resampling-ok
from PIL import Image, PngImagePlugin

from satyapan.forensics.deepfake import score_whole_image
from satyapan.forensics.provenance import analyze_provenance
from satyapan.forensics.tamper import analyze_image_tampering

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "results" / "forensics_m7_adversarial.json"
SEED = 20261107


def wilson_ci(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)) / denom
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def roc_auc(y_true: list[int], y_score: list[float]) -> float:
    pos = [s for y, s in zip(y_true, y_score, strict=True) if y == 1]
    neg = [s for y, s in zip(y_true, y_score, strict=True) if y == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return round(wins / (len(pos) * len(neg)), 4)


def _auth_rgb(rng: np.random.Generator, size: int = 256) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    fx = float(rng.uniform(0.8, 2.0))
    fy = float(rng.uniform(0.8, 2.0))
    lum = 45.0 + 145.0 * (0.5 * xx + 0.5 * yy) + 22.0 * np.sin(2.0 * np.pi * (fx * xx + fy * yy))
    tex = rng.normal(0.0, 3.8, (size, size)).astype(np.float32)
    shot = rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * (0.28 * np.sqrt(lum))
    rgb = np.stack([lum + tex + shot, lum + tex + 0.9 * shot, lum * 0.95 + tex + shot], axis=-1)
    return np.clip(rgb, 10, 245).astype(np.uint8)


def _forged_rgb(rng: np.random.Generator, size: int = 256) -> np.ndarray:
    """Create a manipulated image combining a copy-move cloned patch + spliced high-noise region +
    synthetic upsampling grid."""
    rgb = _auth_rgb(rng, size=size)
    # 1. Copy-move 56x56 textured object
    obj = rng.integers(25, 230, (56, 56, 3), dtype=np.uint8)
    rgb[28:84, 28:84] = obj
    rgb[140:196, 140:196] = obj
    # 2. High-frequency synthetic grid perturbation
    grid2 = ((-1.0) ** (np.arange(size)[:, None] + np.arange(size)[None, :])).astype(np.float32)
    rgb_f = rgb.astype(np.float32)
    rgb_f[:, :, 0] += 3.2 * grid2
    rgb_f[:, :, 1] -= 2.8 * grid2
    return np.clip(rgb_f, 0, 255).astype(np.uint8)


def _apply_attack(
    rgb: np.ndarray, attack: str, rng: np.random.Generator
) -> tuple[np.ndarray, bytes, str]:
    """Return `(attacked_rgb, encoded_bytes, ext)`."""
    h, w, _ = rgb.shape
    if attack == "clean":
        buf = io.BytesIO()
        pi = PngImagePlugin.PngInfo()
        Image.fromarray(rgb).save(buf, format="PNG", pnginfo=pi)
        return rgb, buf.getvalue(), ".png"

    if attack == "jpeg_q50_reencode":
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format="JPEG", quality=50)
        raw = buf.getvalue()
        dec = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=np.uint8)
        return dec, raw, ".jpg"

    if attack == "resize_0.5x_1.0x":
        im = Image.fromarray(rgb)
        down = im.resize((w // 2, h // 2), Image.Resampling.BILINEAR)
        up = down.resize((w, h), Image.Resampling.BILINEAR)
        arr = np.asarray(up, dtype=np.uint8)
        buf = io.BytesIO()
        up.save(buf, format="PNG")
        return arr, buf.getvalue(), ".png"

    if attack == "crop_15pct":
        dh, dw = int(h * 0.075), int(w * 0.075)
        cropped = rgb[dh : h - dh, dw : w - dw]
        buf = io.BytesIO()
        Image.fromarray(cropped).save(buf, format="PNG")
        return cropped, buf.getvalue(), ".png"

    if attack == "gaussian_noise_sigma6":
        noisy = np.clip(rgb.astype(np.float32) + rng.normal(0.0, 6.0, rgb.shape), 0, 255).astype(
            np.uint8
        )
        buf = io.BytesIO()
        Image.fromarray(noisy).save(buf, format="PNG")
        return noisy, buf.getvalue(), ".png"

    raise ValueError(f"Unknown attack: {attack}")


def run_adversarial_benchmark() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)  # provenance: seeded-resampling-ok
    n_per_class = 30
    auth_base = [_auth_rgb(rng) for _ in range(n_per_class)]
    forg_base = [_forged_rgb(rng) for _ in range(n_per_class)]

    attacks = [
        "clean",
        "jpeg_q50_reencode",
        "resize_0.5x_1.0x",
        "crop_15pct",
        "gaussian_noise_sigma6",
    ]
    results_by_attack: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        for atk in attacks:
            y_true: list[int] = []
            combined_scores: list[float] = []
            m2_scores: list[float] = []
            m3_scores: list[float] = []

            for i, rgb in enumerate(auth_base):
                a_rgb, a_bytes, ext = _apply_attack(rgb, atk, rng)
                p = tdir / f"{atk}_auth_{i:02d}{ext}"
                p.write_bytes(a_bytes)
                s_m2 = float(score_whole_image(a_rgb)["probability"])
                s_m3 = analyze_image_tampering(p).tamper_probability
                y_true.append(0)
                m2_scores.append(s_m2)
                m3_scores.append(s_m3)
                combined_scores.append(max(s_m2, s_m3))

            for i, rgb in enumerate(forg_base):
                a_rgb, a_bytes, ext = _apply_attack(rgb, atk, rng)
                p = tdir / f"{atk}_forg_{i:02d}{ext}"
                p.write_bytes(a_bytes)
                s_m2 = float(score_whole_image(a_rgb)["probability"])
                s_m3 = analyze_image_tampering(p).tamper_probability
                y_true.append(1)
                m2_scores.append(s_m2)
                m3_scores.append(s_m3)
                combined_scores.append(max(s_m2, s_m3))

            tp = sum(
                1 for y, s in zip(y_true, combined_scores, strict=True) if y == 1 and s >= 0.45
            )
            fp = sum(
                1 for y, s in zip(y_true, combined_scores, strict=True) if y == 0 and s >= 0.45
            )
            results_by_attack[atk] = {
                "n_authentic": n_per_class,
                "n_manipulated": n_per_class,
                "combined_auc": roc_auc(y_true, combined_scores),
                "m2_synthetic_auc": roc_auc(y_true, m2_scores),
                "m3_tamper_auc": roc_auc(y_true, m3_scores),
                "tpr": round(tp / n_per_class, 4),
                "tpr_ci": wilson_ci(tp, n_per_class),
                "fpr": round(fp / n_per_class, 4),
                "fpr_ci": wilson_ci(fp, n_per_class),
            }

        # Attack 5: Metadata & C2PA stripping on AI/edited images
        meta_before_caught = 0
        meta_after_strip_caught = 0
        pixel_after_strip_caught = 0
        for i, rgb in enumerate(forg_base):
            # Before strip: PNG with Stable Diffusion parameters
            p_with = tdir / f"meta_with_{i:02d}.png"
            pi = PngImagePlugin.PngInfo()
            pi.add_text("parameters", "Stable Diffusion XL, Steps: 30, CFG scale: 7.0")
            Image.fromarray(rgb).save(p_with, format="PNG", pnginfo=pi)
            if analyze_provenance(p_with).anomaly_score >= 0.65:
                meta_before_caught += 1

            # After strip: re-save raw pixels only with zero metadata
            p_strip = tdir / f"meta_strip_{i:02d}.jpg"
            Image.fromarray(rgb).save(p_strip, format="JPEG", quality=85)
            pr_strip = analyze_provenance(p_strip)
            if pr_strip.consistency_checks["anomalies"]:
                meta_after_strip_caught += 1
            # Pixel detectors (M2 + M3) on the stripped file
            s_px = max(
                float(score_whole_image(rgb)["probability"]),
                analyze_image_tampering(p_strip).tamper_probability,
            )
            if s_px >= 0.45:
                pixel_after_strip_caught += 1

        results_by_attack["metadata_and_c2pa_strip"] = {
            "n_manipulated": n_per_class,
            "metadata_catch_before_strip": round(meta_before_caught / n_per_class, 4),
            "metadata_catch_after_strip": round(meta_after_strip_caught / n_per_class, 4),
            "pixel_fallback_catch_after_strip": round(pixel_after_strip_caught / n_per_class, 4),
            "pixel_fallback_ci": wilson_ci(pixel_after_strip_caught, n_per_class),
        }

    summary = {
        "milestone": "M7",
        "seed": SEED,
        "dataset": "synthetic_adversarial_redteam_benchmark (labeled synthetic)",
        "attacks": results_by_attack,
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    out = run_adversarial_benchmark()
    print(json.dumps(out, indent=2))
