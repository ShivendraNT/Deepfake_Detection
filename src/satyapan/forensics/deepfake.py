"""M2 — Deepfake & Synthetic Media Detection Engine (`src/satyapan/forensics/deepfake.py`).

Unifies:
1. Face-swap detection (`GenD` CLIP ViT-L/14 ONNX, `satyapan.imagecheck.face`) on photos and frames;
2. Whole-image AI-generated (diffusion / GAN) detection combining spectral checkerboard / HF
   roll-off, photon-transfer shot-noise physics, Bayer CFA cross-channel residual correlation,
   local patch noise uniformity, and multi-crop CLIP ViT-L/14 vision scores;
3. Video frame-level + 6s window-level (`satyapan.video.analyzer.VideoAnalyzer`) deepfake analysis;
4. Audio voice-clone detection (`Gustking` wav2vec2-large-xlsr ONNX, `satyapan.voice.detector`) with
   acoustic vocoder/prosody analysis.

All findings strictly follow Hard Rule 6: non-absolutist forensic language ("consistent with" /
"inconsistent with"), calibrated confidence in [0, 1], and explicit methodological limitations.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from satyapan.forensics.locker import ForensicLocker

ROOT = Path(__file__).resolve().parents[3]
WHOLE_IMAGE_CONFIG = ROOT / "config" / "whole_image_synthetic.json"
VOICE_THRESHOLDS_CONFIG = ROOT / "config" / "voice_thresholds.json"


@dataclass
class DeepfakeAnalysisResult:
    """Standardized forensic output for M2 deepfake/synthetic media checks."""

    modality: str  # "image" | "video" | "audio"
    finding: str  # "consistent_with_synthetic" | "anomalies_detected_verify" | ...
    confidence: float  # calibrated score in [0.0, 1.0]
    synthetic_probability: float  # probability of synthetic/manipulated origin in [0.0, 1.0]
    statement: str  # plain-English non-absolutist forensic summary
    why: list[str]  # specific technical indicators that fired
    subchecks: dict[str, Any] = field(default_factory=dict)
    frame_scores: list[dict[str, float]] = field(default_factory=list)
    window_scores: list[dict[str, float]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    models_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sigmoid(x: float) -> float:
    x_clamped = max(-30.0, min(30.0, float(x)))
    return 1.0 / (1.0 + math.exp(-x_clamped))


def _forensic_finding_and_statement(
    prob: float,
    tau_hi: float,
    tau_lo: float,
    modality: str,
    abstained: bool = False,
    abstain_reason: str = "",
) -> tuple[str, float, str]:
    """Map synthetic probability + calibrated thresholds to non-absolutist forensic language."""
    if abstained:
        stmt = (
            f"Analysis abstained on {modality} ({abstain_reason or 'insufficient usable signal'}). "
            "No conclusion is drawn; manual forensic examination is required."
        )
        return "inconclusive_abstain", 0.0, stmt

    if prob >= tau_hi:
        conf = round(min(0.98, 0.70 + 0.28 * ((prob - tau_hi) / max(1e-6, 1.0 - tau_hi))), 3)
        stmt = (
            f"Findings are consistent with synthetic or AI-manipulated {modality} "
            f"(synthetic likelihood {prob:.2f}, calibrated confidence {conf:.2f}). "
            "This indicator supports examiner review and does not establish origin or guilt."
        )
        return "consistent_with_synthetic", conf, stmt

    if prob >= tau_lo:
        conf = round(0.50 + 0.20 * ((prob - tau_lo) / max(1e-6, tau_hi - tau_lo)), 3)
        stmt = (
            f"Forensic anomalies detected in {modality} partially consistent with synthetic "
            f"generation or post-processing (likelihood {prob:.2f}, confidence {conf:.2f}). "
            "Independent corroboration and manual verification are recommended."
        )
        return "anomalies_detected_verify", conf, stmt

    conf = round(min(0.95, 0.65 + 0.30 * ((tau_lo - prob) / max(1e-6, tau_lo))), 3)
    stmt = (
        f"Observations are consistent with authentic {modality} capture within detector limits "
        f"(synthetic likelihood {prob:.2f}, confidence {conf:.2f}). "
        "Absence of detected artifacts does not guarantee authenticity."
    )
    return "consistent_with_authentic", conf, stmt


# ---------------------------------------------------------------------------
# 1. Whole-Image AI-Generated (Diffusion / GAN) Feature Extractor & Scorer
# ---------------------------------------------------------------------------


def _high_pass_residual(gray: np.ndarray) -> np.ndarray:
    """3x3 Laplacian high-pass noise residual on a float32 grayscale image in [0, 255]."""
    p = np.pad(gray, 1, mode="reflect")
    center = p[1:-1, 1:-1]
    neighbors = 0.25 * (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
    return np.asarray(center - neighbors, dtype=np.float32)


def extract_whole_image_features(
    rgb: np.ndarray,
    clip_scorer: Any | None = None,
) -> dict[str, float]:
    """Compute 6 forensic features sensitive to diffusion/GAN synthesis on an RGB uint8 image:
    1. `checkerboard_index`: periodic spectral energy peaks at Nyquist/2 and Nyquist/4;
    2. `fft_hf_deficit`: spectral roll-off / high-frequency deficit or abnormal plateau;
    3. `photon_transfer_violation`: violation of physical camera shot-noise (variance vs luminance);
    4. `cfa_decorrelation`: lack of Bayer CFA cross-channel high-pass residual correlation;
    5. `patch_noise_uniformity`: abnormal spatial uniformity or step-clustering of residual noise;
    6. `clip_whole_prob`: multi-crop CLIP ViT-L/14 (`gend_clip_l14.onnx`) synthetic probability.
    """
    arr = np.asarray(rgb, dtype=np.float32)
    h, w, _ = arr.shape
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    # 1 & 2. 2D FFT spectral analysis on high-pass residual (size-normalized 256x256)
    res = _high_pass_residual(gray)
    res_r_2d = _high_pass_residual(arr[:, :, 0])
    # Resize/crop residual to 256x256 for canonical frequency bins
    pil_res = Image.fromarray(np.clip(res + 128.0, 0, 255).astype(np.uint8)).resize(
        (256, 256), Image.Resampling.BILINEAR
    )
    pil_res_r = Image.fromarray(np.clip(res_r_2d + 128.0, 0, 255).astype(np.uint8)).resize(
        (256, 256), Image.Resampling.BILINEAR
    )
    res256 = np.asarray(pil_res, dtype=np.float32) - 128.0
    res_r256 = np.asarray(pil_res_r, dtype=np.float32) - 128.0
    fft2 = 0.5 * (
        np.fft.fftshift(np.abs(np.fft.fft2(res256)))
        + np.fft.fftshift(np.abs(np.fft.fft2(res_r256)))
    )
    log_spec = np.log1p(fft2)
    cy, cx = 128, 128

    # Check periodic peaks at Nyquist (corners/edges), Nyquist/2 (64), and Nyquist/4 (32)
    med_spec = float(np.median(log_spec)) + 1e-6
    std_spec = float(np.std(log_spec)) + 1e-6
    peak_coords = [
        (0, 0),
        (0, 255),
        (255, 0),
        (255, 255),
        (cy, 0),
        (0, cx),
        (cy, cx + 64),
        (cy, cx - 64),
        (cy + 64, cx),
        (cy - 64, cx),
        (cy + 64, cx + 64),
        (cy - 64, cx - 64),
    ]
    peak_z = []
    for py, px in peak_coords:
        patch = log_spec[max(0, py - 2) : min(256, py + 3), max(0, px - 2) : min(256, px + 3)]
        peak_z.append((float(np.max(patch)) - med_spec) / std_spec)
    top_peaks = float(np.mean(sorted(peak_z, reverse=True)[:4]))
    checkerboard_index = float(np.clip((top_peaks - 1.8) / 3.0, 0.0, 1.0))

    # Radial high-frequency vs mid-frequency energy ratio
    yy, xx = np.ogrid[:256, :256]
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2) / 128.0
    mid_energy = float(np.mean(log_spec[(rr >= 0.12) & (rr < 0.28)])) + 1e-6
    hf_energy = float(np.mean(log_spec[(rr >= 0.32) & (rr <= 0.65)]))
    ratio = hf_energy / mid_energy
    # Camera sensors have a predictable HF/mid ratio ~ 0.92-1.08; diffusion smoothing (<0.82)
    # or GAN upsampling ringing (>1.12) deviates from [0.88, 1.08].
    fft_hf_deficit = float(np.clip(abs(ratio - 0.98) / 0.22, 0.0, 1.0))

    # 3. Photon-transfer curve check: in real camera sensors, noise variance scales positively
    # with non-saturated pixel intensity (shot noise). Synthetic images often have flat, negative,
    # or texture-driven variance independent of sensor luminance.
    bh, bw = h // 16, w // 16
    # Lag-1 autocorrelation of the residual: sensor noise is spatially white (near 0 or negative),
    # while any interpolation/resampling step correlates neighbouring residual samples. Used below
    # so that "smooth" residuals from resizing are not read as generator smoothing.
    res_flat = res.ravel()
    if float(np.std(res_flat)) > 1e-4:
        lag1_resampling = float(np.corrcoef(res_flat[:-1], res_flat[1:])[0, 1])
    else:
        lag1_resampling = 0.0
    if bh >= 2 and bw >= 2:
        g_crop = gray[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16)
        r_crop = res[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16)
        block_lum = g_crop.mean(axis=(1, 3)).ravel()
        block_var = r_crop.var(axis=(1, 3)).ravel()
        # Keep non-saturated mid-tone blocks
        mask = (block_lum > 20.0) & (block_lum < 230.0)
        if int(np.sum(mask)) >= 8:
            lum_m = block_lum[mask]
            var_m = np.log1p(block_var[mask])
            if float(np.std(lum_m)) > 1e-3 and float(np.std(var_m)) > 1e-3:
                corr = float(np.corrcoef(lum_m, var_m)[0, 1])
            else:
                corr = 0.0
            # Authentic shot noise has corr in [0.15, 0.65]; synthetic or uniform has <= 0
            photon_transfer_violation = float(np.clip((0.30 - corr) / 0.60, 0.0, 1.0))
        else:
            photon_transfer_violation = 0.5
        # 5. Patch noise uniformity: over-smooth (median var < 0.6) or extreme bimodal variance.
        # The "smooth" branch is only admissible when the residual is spatially white; a positive
        # lag-1 correlation means an interpolation/resize step explains the smoothing instead.
        med_var = float(np.median(block_var))
        cv_var = float(np.std(block_var) / (np.mean(block_var) + 1e-6))
        smooth_score = float(np.clip((1.2 - med_var) / 1.2, 0.0, 1.0))
        if lag1_resampling >= 0.05:
            smooth_score = 0.0
        bimodal_score = float(np.clip((cv_var - 2.2) / 2.5, 0.0, 1.0))
        patch_noise_uniformity = float(max(smooth_score, bimodal_score))
    else:
        photon_transfer_violation = 0.5
        patch_noise_uniformity = 0.5

    # 4. Bayer CFA cross-channel high-frequency correlation (R-G and B-G residuals)
    res_r = _high_pass_residual(arr[:, :, 0]).ravel()
    res_g = _high_pass_residual(arr[:, :, 1]).ravel()
    res_b = _high_pass_residual(arr[:, :, 2]).ravel()
    if float(np.std(res_r)) > 1e-4 and float(np.std(res_g)) > 1e-4 and float(np.std(res_b)) > 1e-4:
        rg_corr = float(np.corrcoef(res_r, res_g)[0, 1])
        bg_corr = float(np.corrcoef(res_b, res_g)[0, 1])
        mean_cfa_corr = 0.5 * (rg_corr + bg_corr)
    else:
        mean_cfa_corr = 0.0
    # Real demosaiced images have strong positive RG/BG high-frequency coupling (~0.55-0.92).
    # Independent channel noise or synthetic color synthesis has lower or negative coupling.
    cfa_decorrelation = float(np.clip((0.65 - mean_cfa_corr) / 0.65, 0.0, 1.0))

    # 6. Multi-crop CLIP ViT-L/14 whole-image score (if GenD ONNX scorer is provided)
    clip_whole_prob = 0.25
    if clip_scorer is not None:
        try:
            crops = _whole_image_crops(rgb)
            logits = clip_scorer.logits(crops)
            mean_logit = float(np.mean(logits))
            # Map logit (where ~0 is real, >=3.5 is synthetic) to [0, 1]
            clip_whole_prob = _sigmoid((mean_logit - 1.5) / 1.2)
        except Exception:  # noqa: BLE001
            clip_whole_prob = 0.25

    return {
        "checkerboard_index": round(checkerboard_index, 4),
        "fft_hf_deficit": round(fft_hf_deficit, 4),
        "photon_transfer_violation": round(photon_transfer_violation, 4),
        "cfa_decorrelation": round(cfa_decorrelation, 4),
        "patch_noise_uniformity": round(patch_noise_uniformity, 4),
        "clip_whole_prob": round(float(clip_whole_prob), 4),
        "residual_lag1": round(float(lag1_resampling), 4),
    }


def _whole_image_crops(rgb: np.ndarray) -> np.ndarray:
    """Extract up to 3 224x224 crops (center + top-left + bottom-right) from an RGB uint8 image."""
    pil = Image.fromarray(rgb)
    w, h = pil.size
    if w < 224 or h < 224:
        resized = pil.resize((224, 224), Image.Resampling.BILINEAR)
        return np.asarray(resized, dtype=np.uint8)[None, ...]
    crops = []
    # Center crop
    cx, cy = (w - 224) // 2, (h - 224) // 2
    crops.append(np.asarray(pil.crop((cx, cy, cx + 224, cy + 224)), dtype=np.uint8))
    # Full image resized to 224x224
    crops.append(np.asarray(pil.resize((224, 224), Image.Resampling.BILINEAR), dtype=np.uint8))
    return np.stack(crops, axis=0)


def _compression_context(raw_bytes: bytes | None) -> dict[str, Any]:
    """Estimate how much JPEG re-compression can explain away spectral/noise features.

    `compressibility` in [0, 1] is 0 for a high-quality 4:4:4 or lossless source and rises with
    heavier quantisation and chroma subsampling, because both create the very 2-px periodicity
    and high-frequency roll-off that raw diffusion/GAN detectors also look for.
    """
    if not raw_bytes:
        return {"compressibility": 0.0, "chroma_subsampling": "none", "quality": None}
    try:
        from satyapan.forensics.provenance import estimate_jpeg_profile

        prof = estimate_jpeg_profile(raw_bytes)
    except Exception:  # noqa: BLE001
        return {"compressibility": 0.0, "chroma_subsampling": "unknown", "quality": None}

    chroma = str(prof["chroma_subsampling"])
    q = prof["estimated_jpeg_quality"]
    c = 0.0
    if isinstance(q, int):
        c = max(c, 1.0 - (q / 100.0))
    if chroma in ("4:2:0", "4:2:2"):
        c += 0.35
    return {
        "compressibility": round(float(np.clip(c, 0.0, 1.0)), 4),
        "chroma_subsampling": chroma,
        "quality": q,
    }


def score_whole_image(
    rgb: np.ndarray,
    *,
    config_path: Path = WHOLE_IMAGE_CONFIG,
    clip_scorer: Any | None = None,
    raw_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Score an RGB uint8 image for whole-image synthetic (diffusion/GAN) indicators.

    When the encoded bytes are supplied, a `compression_context` is reported alongside the score
    so callers can tell how much of the spectral/noise evidence JPEG quantisation and chroma
    subsampling could explain away.
    """
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    feats = extract_whole_image_features(rgb, clip_scorer=clip_scorer)
    ctx = _compression_context(raw_bytes)

    order: list[str] = cfg["feature_order"]
    means: list[float] = cfg["means"]
    stds: list[float] = cfg["stds"]
    weights: list[float] = cfg["weights"]
    bias = float(cfg["bias"])

    logit = bias
    contributions: dict[str, float] = {}
    for name, m, s, w in zip(order, means, stds, weights, strict=True):
        val = float(feats.get(name, m))
        z = (val - m) / max(1e-6, s)
        contrib = w * z
        contributions[name] = round(contrib, 4)
        logit += contrib

    prob = round(_sigmoid(logit), 4)
    tau_hi = float(cfg["tau_hi"])
    tau_lo = float(cfg["tau_lo"])
    if prob >= tau_hi:
        label = "likely_synthetic"
    elif prob >= tau_lo:
        label = "suspicious"
    else:
        label = "no_signs"

    return {
        "model": str(cfg["model_name"]),
        "label": label,
        "probability": prob,
        "logit": round(logit, 4),
        "tau_hi": tau_hi,
        "tau_lo": tau_lo,
        "features": feats,
        "compression_context": ctx,
        "contributions": contributions,
        "calibrated": bool(cfg.get("calibrated", False)),
    }


def apply_compression_gate(
    prob: float, tau_hi: float, tau_lo: float, context: dict[str, Any]
) -> tuple[float, bool]:
    """Cap a strong synthetic score at 'suspicious' when the file is heavily re-encoded.

    Heavy JPEG/social re-encoding removes exactly the high-frequency and noise evidence the
    whole-image detector uses, so a strong score there is not trustworthy enough to call
    "consistent with synthetic generation". Returns `(gated_probability, was_gated)`.
    """
    compressibility = float(context.get("compressibility") or 0.0)
    if compressibility >= 0.5 and prob >= tau_hi:
        return round(min(prob, tau_lo + 0.03), 4), True
    return prob, False


def _render_spectrum_heatmap(rgb: np.ndarray, out_path: Path) -> None:
    """Render a side-by-side 2D FFT log-power spectrum + spatial synthetic anomaly map."""
    arr = np.asarray(rgb, dtype=np.float32)
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    res = _high_pass_residual(gray)
    pil_res = Image.fromarray(np.clip(res + 128.0, 0, 255).astype(np.uint8)).resize(
        (256, 256), Image.Resampling.BILINEAR
    )
    res256 = np.asarray(pil_res, dtype=np.float32) - 128.0
    fft2 = np.fft.fftshift(np.abs(np.fft.fft2(res256)))
    log_spec = np.log1p(fft2)
    norm_spec = (log_spec - log_spec.min()) / max(1e-6, float(log_spec.max() - log_spec.min()))
    spec_u8 = (norm_spec * 255.0).astype(np.uint8)

    # Colorize spectrum (inferno-like: R=val, G=val^2, B=1-val)
    spec_rgb = np.stack(
        [
            spec_u8,
            ((norm_spec**1.6) * 220.0).astype(np.uint8),
            ((1.0 - norm_spec) * 140.0).astype(np.uint8),
        ],
        axis=-1,
    )
    canvas = Image.new("RGB", (540, 290), (18, 22, 31))
    draw = ImageDraw.Draw(canvas)
    thumb = Image.fromarray(rgb).resize((256, 256), Image.Resampling.BILINEAR)
    canvas.paste(thumb, (10, 26))
    canvas.paste(Image.fromarray(spec_rgb), (274, 26))
    draw.text((12, 6), "Working Copy (256x256 View)", fill=(220, 226, 236))
    draw.text((276, 6), "2D FFT Residual Spectrum", fill=(220, 226, 236))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")


# ---------------------------------------------------------------------------
# 2. Image Deepfake & Synthetic Media Analyzer
# ---------------------------------------------------------------------------

_CACHED_FACE_CHECKER: Any = None
_CACHED_FACE_CHECKER_TRIED = False
_CACHED_VIDEO_ANALYZER: Any = None
_CACHED_VIDEO_ANALYZER_TRIED = False


def _get_face_checker(use_heavy_models: bool = True) -> Any | None:
    global _CACHED_FACE_CHECKER, _CACHED_FACE_CHECKER_TRIED
    if not use_heavy_models:
        return None
    if _CACHED_FACE_CHECKER_TRIED:
        return _CACHED_FACE_CHECKER
    _CACHED_FACE_CHECKER_TRIED = True
    try:
        from satyapan.imagecheck.face import ImageFaceChecker

        _CACHED_FACE_CHECKER = ImageFaceChecker.load()
    except Exception:  # noqa: BLE001
        _CACHED_FACE_CHECKER = None
    return _CACHED_FACE_CHECKER


def _get_video_analyzer(use_heavy_models: bool = True) -> Any | None:
    global _CACHED_VIDEO_ANALYZER, _CACHED_VIDEO_ANALYZER_TRIED
    if not use_heavy_models:
        return None
    if _CACHED_VIDEO_ANALYZER_TRIED:
        return _CACHED_VIDEO_ANALYZER
    _CACHED_VIDEO_ANALYZER_TRIED = True
    try:
        from satyapan.video.analyzer import VideoAnalyzer

        _CACHED_VIDEO_ANALYZER = VideoAnalyzer.load()
    except Exception:  # noqa: BLE001
        _CACHED_VIDEO_ANALYZER = None
    return _CACHED_VIDEO_ANALYZER


def analyze_image_deepfake(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
    use_heavy_models: bool = True,
) -> DeepfakeAnalysisResult:
    """Run face-swap (GenD) and whole-image AI-generated checks on `working_path`."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    from satyapan.imagecheck.face import decode_image

    raw_bytes = p.read_bytes()
    rgb = decode_image(raw_bytes)

    models_used: list[str] = ["satyapan_whole_image_synthetic_v1"]
    why: list[str] = []
    face_info: dict[str, Any] = {"status": "not_run", "logit": None, "probability": None}
    face_prob = 0.0

    checker = _get_face_checker(use_heavy_models=use_heavy_models)
    clip_scorer = checker.scorer if checker is not None else None
    if checker is not None:
        models_used.append(f"GenD_face_swap@{checker.thresholds.model_file}")
        verdict = checker.check(rgb)
        if verdict.logit is not None:
            # Convert GenD logit relative to tau_lo / tau_hi into calibrated [0, 1]
            face_prob = round(_sigmoid((verdict.logit - checker.thresholds.tau_lo) / 0.85), 4)
            face_info = {
                "status": verdict.code.value,
                "logit": round(verdict.logit, 4),
                "probability": face_prob,
                "face_px": round(verdict.face_px or 0.0, 1),
                "tau_hi_logit": checker.thresholds.tau_hi,
                "tau_lo_logit": checker.thresholds.tau_lo,
            }
            if verdict.logit >= checker.thresholds.tau_hi:
                why.append(
                    f"Face-swap detector (GenD CLIP ViT-L/14) scored logit {verdict.logit:.2f} "
                    f">= strict threshold {checker.thresholds.tau_hi:.2f} (1% val FPR)."
                )
            elif verdict.logit >= checker.thresholds.tau_lo:
                why.append(
                    f"Face-swap detector (GenD CLIP ViT-L/14) scored logit {verdict.logit:.2f} "
                    f">= verification threshold {checker.thresholds.tau_lo:.2f} (5% val FPR)."
                )
        else:
            face_info = {
                "status": verdict.code.value,
                "logit": None,
                "probability": None,
                "face_px": round(verdict.face_px, 1) if verdict.face_px else None,
                "problem": verdict.problem,
            }

    whole_info = score_whole_image(rgb, clip_scorer=clip_scorer, raw_bytes=raw_bytes)
    tau_hi = float(whole_info["tau_hi"])
    tau_lo = float(whole_info["tau_lo"])
    whole_prob, was_gated = apply_compression_gate(
        float(whole_info["probability"]), tau_hi, tau_lo, whole_info["compression_context"]
    )
    if was_gated:
        why.append(
            "Heavy JPEG/social re-encoding (chroma "
            f"{whole_info['compression_context'].get('chroma_subsampling')}, approximate Q"
            f"{whole_info['compression_context'].get('quality')}) removes the high-frequency and "
            "sensor-noise evidence this check relies on; the whole-image result is therefore "
            "capped at 'suspicious' rather than 'consistent with synthetic generation'."
        )
    feats = whole_info["features"]
    if whole_info["label"] in ("likely_synthetic", "suspicious"):
        if feats["checkerboard_index"] >= 0.30:
            why.append(
                f"2D FFT residual spectrum exhibits periodic upsampling/checkerboard peaks "
                f"(index={feats['checkerboard_index']:.2f}), typical of GAN/diffusion decoders."
            )
        if feats["photon_transfer_violation"] >= 0.55:
            why.append(
                f"Noise variance across luminance blocks deviates from physical camera shot-noise "
                f"scaling (violation={feats['photon_transfer_violation']:.2f})."
            )
        if feats["cfa_decorrelation"] >= 0.55:
            why.append(
                f"Cross-channel high-frequency residuals lack Bayer CFA demosaicing coupling "
                f"(decorrelation={feats['cfa_decorrelation']:.2f})."
            )
        if feats["patch_noise_uniformity"] >= 0.55:
            why.append(
                f"Local high-pass residual variance shows abnormal spatial uniformity/smoothing "
                f"(uniformity={feats['patch_noise_uniformity']:.2f})."
            )

    # Combine face-swap and whole-image probabilities: when a face >= 64px is scored by GenD,
    # weight the dedicated 304M face model primarily unless whole-image exceeds strict tau_hi.
    if face_info.get("logit") is not None:
        combined_prob = round(
            max(
                face_prob,
                whole_prob if whole_prob >= tau_hi else 0.85 * face_prob + 0.15 * whole_prob,
            ),
            4,
        )
    else:
        combined_prob = round(whole_prob, 4)

    finding, conf, statement = _forensic_finding_and_statement(
        combined_prob, tau_hi=tau_hi, tau_lo=tau_lo, modality="image"
    )
    if not why:
        why.append(
            "Both facial blending check and whole-image spectral/sensor-noise checks remained "
            f"below anomaly thresholds (max synthetic probability {combined_prob:.2f})."
        )

    artifacts: dict[str, str] = {}
    if artifact_dir is not None:
        spec_path = Path(artifact_dir) / "deepfake_spectrum.png"
        _render_spectrum_heatmap(rgb, spec_path)
        artifacts["spectrum_heatmap"] = str(spec_path)

    limitations = [
        (
            "Heavy social-media re-compression (e.g., WhatsApp JPEG Q60 or repeated resizing) "
            "attenuates high-frequency spectral and CFA cues."
        ),
        (
            "Face-swap detection requires a visible face of at least 64x64 pixels; non-face or "
            "small-face images rely on whole-image spectral/noise features."
        ),
        (
            "Thresholds are calibrated on validation splits; novel closed-source generators may "
            "shift score distributions."
        ),
    ]

    return DeepfakeAnalysisResult(
        modality="image",
        finding=finding,
        confidence=conf,
        synthetic_probability=combined_prob,
        statement=statement,
        why=why,
        subchecks={"face_swap": face_info, "whole_image_synthetic": whole_info},
        artifacts=artifacts,
        limitations=limitations,
        models_used=models_used,
    )


# ---------------------------------------------------------------------------
# 3. Video Deepfake Engine (Frame-Level + Window-Level + Aggregate)
# ---------------------------------------------------------------------------


def _render_video_trajectory(
    frame_scores: list[dict[str, float]], tau_hi: float, out_path: Path
) -> None:
    """Render a temporal chart of frame-level synthetic probabilities across the video."""
    w, h = 560, 220
    img = Image.new("RGB", (w, h), (18, 22, 31))
    draw = ImageDraw.Draw(img)
    pad_l, pad_r, pad_t, pad_b = 46, 20, 28, 32
    pw = w - pad_l - pad_r
    ph = h - pad_t - pad_b

    # Grid & threshold line
    draw.rectangle([pad_l, pad_t, pad_l + pw, pad_t + ph], outline=(55, 65, 81), width=1)
    ty = int(pad_t + (1.0 - tau_hi) * ph)
    draw.line([(pad_l, ty), (pad_l + pw, ty)], fill=(239, 68, 68), width=1)
    draw.text((pad_l + 6, max(pad_t + 2, ty - 14)), f"tau_hi={tau_hi:.2f}", fill=(239, 68, 68))
    draw.text((12, 6), "Video Frame-Level Synthetic Likelihood Trajectory", fill=(220, 226, 236))

    if frame_scores:
        n = len(frame_scores)
        pts: list[tuple[int, int]] = []
        for idx, fs in enumerate(frame_scores):
            x = pad_l + int((idx / max(1, n - 1)) * pw) if n > 1 else pad_l + pw // 2
            y = pad_t + int((1.0 - float(fs["combined_score"])) * ph)
            pts.append((x, y))
        if len(pts) >= 2:
            draw.line(pts, fill=(56, 189, 248), width=2)
        for x, y in pts:
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(56, 189, 248))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")


def analyze_video_deepfake(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
    use_heavy_models: bool = True,
    max_frames: int = 16,
) -> DeepfakeAnalysisResult:
    """Analyze a video working copy at both frame level and aggregate window level."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    try:
        from satyapan.video.io import iter_frames, read_audio
    except ImportError as exc:  # video extra not installed (e.g. slim offline container)
        finding, conf, stmt = _forensic_finding_and_statement(
            0.0, 0.68, 0.48, "video", abstained=True, abstain_reason="video_decoder_not_installed"
        )
        return DeepfakeAnalysisResult(
            modality="video",
            finding=finding,
            confidence=conf,
            synthetic_probability=0.0,
            statement=stmt,
            why=[f"Video decoding dependencies are not installed here ({exc})."],
            limitations=["Install the `video` extra (or run the full image) to analyse video."],
        )

    try:
        raw_frames = list(iter_frames(p, max_s=15.0))
    except ValueError:
        raw_frames = []
    audio_16k = read_audio(p, sr=16000, max_s=15.0)
    if not raw_frames:
        finding, conf, stmt = _forensic_finding_and_statement(
            0.0, 0.68, 0.48, "video", abstained=True, abstain_reason="no_decodable_video_frames"
        )
        return DeepfakeAnalysisResult(
            modality="video",
            finding=finding,
            confidence=conf,
            synthetic_probability=0.0,
            statement=stmt,
            why=["Video container contained zero decodable frames."],
            limitations=["Cannot evaluate empty or corrupted video streams."],
        )

    # Sample up to `max_frames` evenly spaced frames for per-frame analysis
    indices = np.unique(
        np.linspace(0, len(raw_frames) - 1, min(len(raw_frames), max_frames)).round().astype(int)
    )
    checker = _get_face_checker(use_heavy_models=use_heavy_models)
    models_used = ["satyapan_whole_image_synthetic_v1"]
    if checker is not None:
        models_used.append(f"GenD_video_face@{checker.thresholds.model_file}")

    frame_scores: list[dict[str, float]] = []
    face_probs: list[float] = []
    whole_probs: list[float] = []

    tracker = checker.tracker_factory() if checker is not None else None
    try:
        from satyapan.video.observe import face_crop

        for idx in indices:
            t_sec, rgb = raw_frames[int(idx)]
            w_res = score_whole_image(rgb, clip_scorer=None)
            w_prob = float(w_res["probability"])
            whole_probs.append(w_prob)

            f_prob = 0.0
            face_detected = False
            if checker is not None and tracker is not None:
                obs = tracker.track(rgb, float(t_sec))
                if obs is not None:
                    pts = np.asarray(obs.pts)
                    face_px = float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
                    if face_px >= 64.0:
                        face_detected = True
                        logit = float(checker.scorer.logits(face_crop(rgb, pts)[None])[0])
                        f_prob = round(_sigmoid((logit - checker.thresholds.tau_lo) / 0.85), 4)
                        face_probs.append(f_prob)
            comb = round(0.85 * f_prob + 0.15 * w_prob, 4) if face_detected else round(w_prob, 4)
            frame_scores.append(
                {
                    "frame_index": float(idx),
                    "time_s": round(float(t_sec), 3),
                    "face_score": round(f_prob, 4),
                    "whole_frame_score": round(w_prob, 4),
                    "combined_score": comb,
                }
            )
    finally:
        if tracker is not None:
            tracker.close()

    # Also run 6s window-level VideoAnalyzer if heavy models are enabled
    window_scores: list[dict[str, float]] = []
    window_cues: set[str] = set()
    va = _get_video_analyzer(use_heavy_models=use_heavy_models)
    if va is not None:
        try:
            win_results = va.analyze_frames(raw_frames, audio_16k, 16000)
            for wr in win_results:
                if wr.score is not None:
                    window_scores.append(
                        {
                            "window_index": float(wr.index),
                            "t_start": round(wr.t_start, 2),
                            "t_end": round(wr.t_end, 2),
                            "score": round(float(wr.score), 4),
                        }
                    )
                    window_cues.update(wr.cues)
        except Exception:  # noqa: BLE001
            pass

    all_comb = [fs["combined_score"] for fs in frame_scores]
    p90_frame = float(np.percentile(all_comb, 90)) if all_comb else 0.0
    mean_frame = float(np.mean(all_comb)) if all_comb else 0.0
    max_frame = float(np.max(all_comb)) if all_comb else 0.0
    win_max = max((ws["score"] for ws in window_scores), default=0.0)
    agg_prob = round(max(0.65 * p90_frame + 0.35 * mean_frame, win_max), 4)

    tau_hi = 0.68
    tau_lo = 0.48
    flagged_frames = sum(1 for s in all_comb if s >= tau_lo)
    why: list[str] = []
    if flagged_frames > 0:
        why.append(
            f"{flagged_frames}/{len(all_comb)} sampled frames exceeded anomaly threshold "
            f"(p90={p90_frame:.2f}, max={max_frame:.2f}, mean={mean_frame:.2f})."
        )
    if win_max >= tau_lo:
        why.append(
            f"6-second temporal window fusion scored {win_max:.2f} "
            + (f"with active cues: {', '.join(sorted(window_cues))}." if window_cues else ".")
        )
    if not why:
        why.append(
            f"Frame-level trajectory (n={len(all_comb)} frames) and temporal windows remained "
            f"below synthetic thresholds (aggregate score {agg_prob:.2f})."
        )

    finding, conf, statement = _forensic_finding_and_statement(
        agg_prob, tau_hi=tau_hi, tau_lo=tau_lo, modality="video"
    )

    artifacts: dict[str, str] = {}
    if artifact_dir is not None:
        chart_path = Path(artifact_dir) / "video_frame_scores.png"
        _render_video_trajectory(frame_scores, tau_hi, chart_path)
        artifacts["frame_trajectory"] = str(chart_path)

    return DeepfakeAnalysisResult(
        modality="video",
        finding=finding,
        confidence=conf,
        synthetic_probability=agg_prob,
        statement=statement,
        why=why,
        subchecks={
            "frames_analyzed": len(frame_scores),
            "p90_frame_score": round(p90_frame, 4),
            "mean_frame_score": round(mean_frame, 4),
            "max_frame_score": round(max_frame, 4),
            "flagged_frame_count": flagged_frames,
            "window_max_score": round(win_max, 4),
            "active_cues": sorted(window_cues),
        },
        frame_scores=frame_scores,
        window_scores=window_scores,
        artifacts=artifacts,
        limitations=[
            (
                "Low-bitrate call codecs (e.g., 360p VP8) degrade fine facial boundary and rPPG "
                "pulse signals."
            ),
            (
                "Real video footage paired with a cloned voice ('cheapfake') will pass visual "
                "checks; always inspect the audio track."
            ),
        ],
        models_used=models_used,
    )


# ---------------------------------------------------------------------------
# 4. Audio Voice-Clone & Synthetic Speech Analyzer
# ---------------------------------------------------------------------------

_CACHED_VOICE_DETECTOR: Any = None
_CACHED_VOICE_TRIED = False


def _get_voice_detector(use_heavy_models: bool = True) -> Any | None:
    global _CACHED_VOICE_DETECTOR, _CACHED_VOICE_TRIED
    if not use_heavy_models:
        return None
    if _CACHED_VOICE_TRIED:
        return _CACHED_VOICE_DETECTOR
    _CACHED_VOICE_TRIED = True
    try:
        from satyapan.voice.detector import load_default_detector

        _CACHED_VOICE_DETECTOR = load_default_detector("gustking_xlsr")
    except Exception:  # noqa: BLE001
        _CACHED_VOICE_DETECTOR = None
    return _CACHED_VOICE_DETECTOR


def _acoustic_vocoder_score(samples: np.ndarray, sr: int = 16000) -> dict[str, float]:
    """Signal-processing vocoder & prosody check (pitch stability, flatness, HF cut-off)."""
    if len(samples) < sr // 2:
        return {"score": 0.0, "pitch_regularity": 0.0, "hf_roll_anomaly": 0.0}
    x = np.asarray(samples, dtype=np.float32)
    x = x / (float(np.max(np.abs(x))) + 1e-6)

    # Frame into 32ms (512 samples) hop 16ms (256 samples)
    win_len, hop = 512, 256
    n_frames = max(1, (len(x) - win_len) // hop)
    spec_frames = []
    rms_frames = []
    hann = np.hanning(win_len).astype(np.float32)
    for i in range(n_frames):
        seg = x[i * hop : i * hop + win_len] * hann
        rms_frames.append(float(np.sqrt(np.mean(seg**2))))
        spec_frames.append(np.abs(np.fft.rfft(seg)))
    spec = np.stack(spec_frames, axis=0) + 1e-7
    rms = np.array(rms_frames, dtype=np.float32)

    # Active voiced frames
    voiced = spec[rms > np.percentile(rms, 30)]
    if len(voiced) < 4:
        voiced = spec

    # Spectral flatness & inter-frame spectral modulation variance
    geom_mean = np.exp(np.mean(np.log(voiced), axis=1))
    arith_mean = np.mean(voiced, axis=1)
    flatness = geom_mean / arith_mean
    flatness_cv = float(np.std(flatness) / (np.mean(flatness) + 1e-6))

    # Vocoders & TTS often show regular envelope modulation (low flatness_cv) or sharp HF shelf
    n_bins = voiced.shape[1]
    low_band = float(np.mean(np.log(voiced[:, : int(n_bins * 0.5)])))
    hi_band = float(np.mean(np.log(voiced[:, int(n_bins * 0.75) :])))
    hf_drop = max(0.0, low_band - hi_band)

    pitch_reg = float(np.clip((0.65 - flatness_cv) / 0.55, 0.0, 1.0))
    hf_anom = float(np.clip((hf_drop - 3.2) / 3.0, 0.0, 1.0))
    score = round(0.60 * pitch_reg + 0.40 * hf_anom, 4)
    return {
        "score": score,
        "pitch_regularity": round(pitch_reg, 4),
        "hf_roll_anomaly": round(hf_anom, 4),
    }


def analyze_audio_deepfake(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
    use_heavy_models: bool = True,
) -> DeepfakeAnalysisResult:
    """Analyze an audio working copy for synthetic voice / voice-cloning indicators."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    from satyapan.voice.audio_io import decode_to_16k_mono, estimate_speech_seconds, split_windows
    from satyapan.voice.rules import MIN_SPEECH_SECONDS, classify_windows, load_thresholds

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
    mime = mime_map.get(ext, "audio/wav")
    try:
        samples = decode_to_16k_mono(raw_bytes, mime)
    except ValueError as exc:  # ffmpeg missing or undecodable stream
        finding, conf, stmt = _forensic_finding_and_statement(
            0.0, 0.68, 0.48, "audio", abstained=True, abstain_reason="audio_decoder_unavailable"
        )
        return DeepfakeAnalysisResult(
            modality="audio",
            finding=finding,
            confidence=conf,
            synthetic_probability=0.0,
            statement=stmt,
            why=[f"Audio could not be decoded here: {exc}"],
            limitations=["Install ffmpeg (and the audio deps) to analyse audio."],
        )
    speech_s = estimate_speech_seconds(samples)
    windows = split_windows(samples)

    thr = load_thresholds(VOICE_THRESHOLDS_CONFIG)
    detector = _get_voice_detector(use_heavy_models=use_heavy_models)
    acoustic = _acoustic_vocoder_score(samples, 16000)

    models_used = ["acoustic_vocoder_prosody_v1"]
    window_scores: list[dict[str, float]] = []
    why: list[str] = []

    if speech_s < MIN_SPEECH_SECONDS:
        finding, conf, stmt = _forensic_finding_and_statement(
            0.0,
            thr.tau_hi,
            thr.tau_lo,
            "audio",
            abstained=True,
            abstain_reason=f"speech_too_short ({speech_s:.1f}s < {MIN_SPEECH_SECONDS:.1f}s)",
        )
        return DeepfakeAnalysisResult(
            modality="audio",
            finding=finding,
            confidence=conf,
            synthetic_probability=0.0,
            statement=stmt,
            why=[
                f"Estimated active speech is {speech_s:.2f}s, below the "
                f"{MIN_SPEECH_SECONDS:.1f}s minimum required for reliable voice-clone scoring."
            ],
            subchecks={"speech_seconds": round(speech_s, 2), "acoustic": acoustic},
            limitations=[
                "Recordings with under 3 seconds of active speech cannot be reliably scored "
                "and abstain by design."
            ],
            models_used=models_used,
        )

    if detector is not None and windows:
        models_used.insert(0, f"OnnxVoiceDetector@{detector.model_version}")
        onnx_scores = detector.score_windows(windows)
        for i, sc in enumerate(onnx_scores):
            window_scores.append(
                {
                    "window_index": float(i),
                    "t_start": float(i * 5.0),
                    "t_end": float((i + 1) * 5.0),
                    "score": round(float(sc), 4),
                }
            )
        verdict = classify_windows(onnx_scores, thr, speech_s)
        max_onnx = max(onnx_scores)
        agg_prob = round(max(float(max_onnx), 0.75 * float(max_onnx) + 0.25 * acoustic["score"]), 4)
        if verdict.label == "likely_synthetic":
            why.append(
                f"XLS-R voice-clone detector ({detector.model_version}) exceeded strict "
                f"threshold tau_hi={thr.tau_hi:.3f} on consecutive 5s windows (max={max_onnx:.3f})."
            )
        elif verdict.label == "suspicious":
            why.append(
                f"XLS-R voice-clone detector ({detector.model_version}) exceeded suspicious "
                f"threshold tau_lo={thr.tau_lo:.3f} (max={max_onnx:.3f})."
            )
    else:
        agg_prob = float(acoustic["score"])
        for i in range(max(1, len(windows))):
            window_scores.append(
                {
                    "window_index": float(i),
                    "t_start": float(i * 5.0),
                    "t_end": float((i + 1) * 5.0),
                    "score": agg_prob,
                }
            )

    if acoustic["score"] >= 0.55:
        why.append(
            f"Acoustic vocoder analysis detected high pitch/envelope regularity "
            f"({acoustic['pitch_regularity']:.2f}) and spectral roll-off anomaly "
            f"({acoustic['hf_roll_anomaly']:.2f})."
        )
    if not why:
        why.append(
            f"Voice-clone window scores and acoustic prosody checks remained below thresholds "
            f"(max score {agg_prob:.3f}, speech duration {speech_s:.1f}s)."
        )

    finding, conf, statement = _forensic_finding_and_statement(
        agg_prob, tau_hi=thr.tau_hi, tau_lo=thr.tau_lo, modality="audio"
    )

    return DeepfakeAnalysisResult(
        modality="audio",
        finding=finding,
        confidence=conf,
        synthetic_probability=agg_prob,
        statement=statement,
        why=why,
        subchecks={
            "speech_seconds": round(speech_s, 2),
            "tau_hi": thr.tau_hi,
            "tau_lo": thr.tau_lo,
            "acoustic_vocoder": acoustic,
        },
        window_scores=window_scores,
        limitations=[
            (
                "Heavy background noise (~10 dB SNR) significantly reduces neural voice-clone "
                "recall (measured in results/voice_evasion.md)."
            ),
            "Clips with under 3 seconds of active speech abstain.",
        ],
        models_used=models_used,
    )
