"""M2 Calibration & Held-Out Benchmark (`research/forensics/eval_m2_deepfake.py`).

Protocol:
1. Validation split (n=160: 40 authentic clean, 40 authentic JPEG-recompressed, 40 synthetic
   clean, 40 synthetic JPEG-recompressed): fits feature normalization + logistic weights over
   the 6 forensic features, then calibrates thresholds (`tau_hi` at <=2% val FPR, `tau_lo` at
   <=5% val FPR over ALL authentic val images) into `config/whole_image_synthetic.json`.
   Recompressed authentics are in calibration on purpose: JPEG artefacts mimic generator
   artefacts, so a threshold that ignores them false-positives on ordinary WhatsApp copies.
2. Held-out test split (n=160, disjoint seed): scored once with frozen weights/thresholds.
3. Compression gate: on heavily re-encoded files a strong whole-image score is capped at
   "suspicious" (it cannot tell synthesis from quantisation). Reports how often that fires and
   what it costs in recall.
4. Multi-modal spot check on `.cache/testkit` video and audio (real vs deepfake/cloned).
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np  # provenance: seeded-resampling-ok
from PIL import Image

from satyapan.forensics.deepfake import (
    WHOLE_IMAGE_CONFIG,
    analyze_audio_deepfake,
    analyze_video_deepfake,
    apply_compression_gate,
    score_whole_image,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "results" / "forensics_m2_deepfake.json"
VAL_SEED = 20261101
TEST_SEED = 20261102

BASE_FEATURES = [
    "checkerboard_index",
    "fft_hf_deficit",
    "photon_transfer_violation",
    "cfa_decorrelation",
    "patch_noise_uniformity",
    "clip_whole_prob",
]
FEATURE_ORDER = BASE_FEATURES


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


def make_authentic_camera_image(rng: np.random.Generator, size: int = 256) -> np.ndarray:
    """Camera-like image obeying physical sensor properties (shot noise, CFA coupling)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    ax = float(rng.uniform(0.6, 2.2))
    ay = float(rng.uniform(0.6, 2.2))
    phase = float(rng.uniform(0, 3.14))
    base_lum = (
        40.0
        + 150.0 * (0.5 * xx + 0.5 * yy)
        + 25.0 * np.sin(2.0 * math.pi * (ax * xx + ay * yy) + phase)
    )
    base_lum = np.clip(base_lum, 25.0, 225.0)
    shared_tex = rng.normal(0.0, 3.8, (size, size)).astype(np.float32)
    shot_sigma = 0.28 * np.sqrt(base_lum)
    shot_noise = rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * shot_sigma
    r = base_lum * float(rng.uniform(0.92, 1.08)) + shared_tex + shot_noise
    g = base_lum + shared_tex + 0.9 * shot_noise + rng.normal(0.0, 0.5, (size, size))
    b = base_lum * float(rng.uniform(0.88, 1.06)) + shared_tex + shot_noise
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def make_synthetic_ai_image(
    rng: np.random.Generator, size: int = 256, mode: str = "gan"
) -> np.ndarray:
    """AI generator-style image (checkerboard upsampling or diffusion VAE smoothing)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    freq = float(rng.uniform(1.0, 3.0))
    base = 120.0 + 70.0 * np.cos(2.0 * math.pi * freq * xx) * np.sin(2.0 * math.pi * freq * yy)
    ch_r = base + rng.normal(0.0, 1.2, (size, size)).astype(np.float32)
    ch_g = base + rng.normal(0.0, 1.2, (size, size)).astype(np.float32)
    ch_b = base + rng.normal(0.0, 1.2, (size, size)).astype(np.float32)

    if mode == "gan":
        grid2 = ((-1.0) ** (np.arange(size)[:, None] + np.arange(size)[None, :])).astype(np.float32)
        grid4 = (
            (-1.0) ** ((np.arange(size)[:, None] // 2) + (np.arange(size)[None, :] // 2))
        ).astype(np.float32)
        amp = float(rng.uniform(2.2, 4.5))
        ch_r += amp * grid2 + 0.6 * amp * grid4
        ch_g -= 0.8 * amp * grid2
        ch_b += 0.9 * amp * grid2
    else:
        inv_sigma = 0.35 * np.sqrt(np.clip(240.0 - base, 10.0, 220.0))
        ch_r += rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * inv_sigma
        ch_g += rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * inv_sigma
        ch_b += rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * inv_sigma
        pil_tmp = Image.fromarray(
            np.clip(np.stack([ch_r, ch_g, ch_b], axis=-1), 0, 255).astype(np.uint8)
        )
        pil_tmp = pil_tmp.resize((size // 2, size // 2), Image.Resampling.BILINEAR).resize(
            (size, size), Image.Resampling.BILINEAR
        )
        return np.asarray(pil_tmp, dtype=np.uint8)

    rgb = np.stack([ch_r, ch_g, ch_b], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def compress_jpeg(rgb: np.ndarray, quality: int) -> tuple[np.ndarray, bytes]:
    """Encode at `quality` with 4:2:0 chroma, then decode back to pixels."""
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality, subsampling=2)
    raw = buf.getvalue()
    dec = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=np.uint8)
    return dec, raw


def build_split(seed: int, n_per_class: int) -> list[tuple[np.ndarray, bytes | None, int, bool]]:
    """[(pixels, original_bytes_if_jpeg, label, is_compressed)]"""
    rng = np.random.default_rng(seed)  # provenance: seeded-resampling-ok
    out: list[tuple[np.ndarray, bytes | None, int, bool]] = []
    for _ in range(n_per_class):
        out.append((make_authentic_camera_image(rng), None, 0, False))
    for _ in range(n_per_class):
        pix, raw = compress_jpeg(make_authentic_camera_image(rng), int(rng.integers(58, 83)))
        out.append((pix, raw, 0, True))
    for i in range(n_per_class):
        mode = "gan" if i % 2 == 0 else "diffusion"
        out.append((make_synthetic_ai_image(rng, mode=mode), None, 1, False))
    for i in range(n_per_class):
        mode = "gan" if i % 2 == 0 else "diffusion"
        pix, raw = compress_jpeg(make_synthetic_ai_image(rng, mode=mode), int(rng.integers(58, 83)))
        out.append((pix, raw, 1, True))
    return out


def _feature_vector(rgb: np.ndarray, raw_bytes: bytes | None) -> list[float]:
    res = score_whole_image(rgb, raw_bytes=raw_bytes)
    feats = res["features"]
    return [float(feats[k]) for k in FEATURE_ORDER]


def fit_and_calibrate() -> dict[str, Any]:
    val = build_split(VAL_SEED, n_per_class=40)
    x_val = np.array([_feature_vector(p, raw) for p, raw, _y, _c in val], dtype=np.float64)
    y_val = np.array([y for _p, _r, y, _c in val], dtype=np.int32)

    means = x_val.mean(axis=0)
    stds = np.maximum(x_val.std(axis=0), 0.05)
    z_pos = ((x_val[y_val == 1] - means) / stds).mean(axis=0)
    z_neg = ((x_val[y_val == 0] - means) / stds).mean(axis=0)
    diff = z_pos - z_neg
    weights = diff / max(1e-6, float(np.linalg.norm(diff))) * 2.2
    # Keep the CLIP whole-image signal strong when a GenD scorer is available
    weights[FEATURE_ORDER.index("clip_whole_prob")] = 1.15
    bias = -0.35

    cfg = {
        "model_name": "satyapan_whole_image_synthetic_v2",
        "description": (
            "Logistic fusion over spectral checkerboard/high-frequency roll-off, photon-transfer "
            "noise curve, CFA cross-channel residual correlation, patch noise uniformity, and the "
            "CLIP ViT-L/14 whole-image logit; thresholds calibrated with JPEG-recompressed "
            "authentic images included so ordinary messaging re-encodes do not read as synthetic."
        ),
        "feature_order": FEATURE_ORDER,
        "means": [round(float(m), 4) for m in means],
        "stds": [round(float(s), 4) for s in stds],
        "weights": [round(float(w), 4) for w in weights],
        "bias": bias,
        "tau_hi": 0.68,
        "tau_lo": 0.48,
        "calibrated": True,
        "calibration_split": "val_n160_clean_and_jpeg_recompressed",
    }
    WHOLE_IMAGE_CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    # Calibrate thresholds on ALL authentic val images (clean + recompressed)
    val_probs = [float(score_whole_image(p, raw_bytes=r)["probability"]) for p, r, _y, _c in val]
    neg_probs = sorted(p for p, (_p, _r, y, _c) in zip(val_probs, val, strict=True) if y == 0)
    tau_hi = round(max(0.60, float(np.percentile(neg_probs, 98)) + 0.01), 4)
    tau_lo = round(max(0.45, float(np.percentile(neg_probs, 95)) + 0.005), 4)
    if tau_lo >= tau_hi:
        tau_lo = round(tau_hi - 0.12, 4)

    cfg["tau_hi"] = tau_hi
    cfg["tau_lo"] = tau_lo
    WHOLE_IMAGE_CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {
        "val_n": len(val),
        "val_auc": roc_auc([y for _p, _r, y, _c in val], val_probs),
        "tau_hi": tau_hi,
        "tau_lo": tau_lo,
    }


def evaluate_heldout_and_compression() -> dict[str, Any]:
    cal = fit_and_calibrate()
    tau_hi = float(cal["tau_hi"])
    tau_lo = float(cal["tau_lo"])

    test = build_split(TEST_SEED, n_per_class=40)
    clean = [(p, r, y) for p, r, y, c in test if not c]
    comp = [(p, r, y) for p, r, y, c in test if c]

    def score(group) -> tuple[list[int], list[float]]:
        ys = [y for _p, _r, y in group]
        ps = [float(score_whole_image(p, raw_bytes=r)["probability"]) for p, r, _y in group]
        return ys, ps

    def score_gated(group) -> tuple[list[int], list[float], int]:
        ys = [y for _p, _r, y in group]
        ps: list[float] = []
        gated = 0
        for p, r, _y in group:
            res = score_whole_image(p, raw_bytes=r)
            g, was = apply_compression_gate(
                float(res["probability"]),
                float(res["tau_hi"]),
                float(res["tau_lo"]),
                res["compression_context"],
            )
            ps.append(g)
            gated += int(was)
        return ys, ps, gated

    c_y, c_p = score(clean)
    k_y, k_p = score(comp)
    k_y_g, k_p_g, gated_n = score_gated(comp)
    n_pos_c = sum(c_y)
    n_neg_c = len(c_y) - n_pos_c
    n_pos_k = sum(k_y)
    n_neg_k = len(k_y) - n_pos_k

    def rate(ys: list[int], ps: list[float], label: int, thr: float) -> tuple[int, int]:
        hits = sum(1 for y, p in zip(ys, ps, strict=True) if y == label and p >= thr)
        total = sum(1 for y in ys if y == label)
        return hits, total

    tp_hi_c, n_pc = rate(c_y, c_p, 1, tau_hi)
    fp_hi_c, n_nc = rate(c_y, c_p, 0, tau_hi)
    tp_lo_k, n_pk = rate(k_y, k_p, 1, tau_lo)
    fp_lo_k, n_nk = rate(k_y, k_p, 0, tau_lo)
    tp_hi_k, _ = rate(k_y, k_p, 1, tau_hi)
    tp_hi_kg, _ = rate(k_y_g, k_p_g, 1, tau_hi)
    fp_hi_kg, _ = rate(k_y_g, k_p_g, 0, tau_hi)

    testkit_spot: dict[str, Any] = {}
    tk_video = ROOT / ".cache" / "testkit" / "video"
    tk_audio = ROOT / ".cache" / "testkit" / "audio"
    if (tk_video / "fake_faceswap_meeting_720p.mp4").exists() and (
        tk_video / "real_meeting_720p.mp4"
    ).exists():
        v_fake = analyze_video_deepfake(
            tk_video / "fake_faceswap_meeting_720p.mp4", use_heavy_models=True, max_frames=8
        )
        v_real = analyze_video_deepfake(
            tk_video / "real_meeting_720p.mp4", use_heavy_models=True, max_frames=8
        )
        testkit_spot["video_fake_prob"] = v_fake.synthetic_probability
        testkit_spot["video_fake_finding"] = v_fake.finding
        testkit_spot["video_real_prob"] = v_real.synthetic_probability
        testkit_spot["video_real_finding"] = v_real.finding

    if (tk_audio / "fake_cfo_clone_en.wav").exists() and (
        tk_audio / "real_public_domain_speech.wav"
    ).exists():
        a_fake = analyze_audio_deepfake(tk_audio / "fake_cfo_clone_en.wav", use_heavy_models=True)
        a_real = analyze_audio_deepfake(
            tk_audio / "real_public_domain_speech.wav", use_heavy_models=True
        )
        testkit_spot["audio_fake_prob"] = a_fake.synthetic_probability
        testkit_spot["audio_fake_finding"] = a_fake.finding
        testkit_spot["audio_real_prob"] = a_real.synthetic_probability
        testkit_spot["audio_real_finding"] = a_real.finding

    summary = {
        "milestone": "M2",
        "dataset": "synthetic_camera_vs_ai_generator_benchmark (seeded, val=160, test=160)",
        "calibration": cal,
        "test_clean": {
            "n_total": len(c_y),
            "n_synthetic": n_pos_c,
            "n_authentic": n_neg_c,
            "auc": roc_auc(c_y, c_p),
            "tpr_at_tau_hi": round(tp_hi_c / max(1, n_pc), 4),
            "tpr_at_tau_hi_ci": wilson_ci(tp_hi_c, n_pc),
            "fpr_at_tau_hi": round(fp_hi_c / max(1, n_nc), 4),
            "fpr_at_tau_hi_ci": wilson_ci(fp_hi_c, n_nc),
        },
        "test_jpeg_recompressed": {
            "n_total": len(k_y),
            "n_synthetic": n_pos_k,
            "n_authentic": n_neg_k,
            "auc": roc_auc(k_y, k_p),
            "tpr_at_tau_lo": round(tp_lo_k / max(1, n_pk), 4),
            "tpr_at_tau_lo_ci": wilson_ci(tp_lo_k, n_pk),
            "fpr_at_tau_lo": round(fp_lo_k / max(1, n_nk), 4),
            "fpr_at_tau_lo_ci": wilson_ci(fp_lo_k, n_nk),
        },
        "compression_gate": {
            "files_gated_at_tau_hi": gated_n,
            "synthetic_recall_at_tau_hi_before_gate": round(tp_hi_k / max(1, n_pk), 4),
            "synthetic_recall_at_tau_hi_after_gate": round(tp_hi_kg / max(1, n_pk), 4),
            "fpr_at_tau_hi_after_gate": round(fp_hi_kg / max(1, n_nk), 4),
        },
        "testkit_multimodal_spotcheck": testkit_spot,
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    res = evaluate_heldout_and_compression()
    print(json.dumps(res, indent=2))
