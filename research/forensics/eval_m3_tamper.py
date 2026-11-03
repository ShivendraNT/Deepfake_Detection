"""M3 Reproducible Tampering Detection Benchmark (`research/forensics/eval_m3_tamper.py`).

Generates a seeded synthetic tampering benchmark (`SEED = 20261103`, labeled synthetic in ledger)
covering:
1. Image Tampering Suite (n=120: 40 authentic single-JPEG images + 80 tampered images:
   30 spliced foreign patch, 30 copy-move cloned region, 20 double-JPEG / grid-mismatched):
   - Evaluates individual sub-detectors (ELA, Copy-Move, Noise-Residual, Double-JPEG) on their
     target tamper types and the combined `analyze_image_tampering` detector across all 120 images.
2. Video Tampering Suite (n=30 videos: 15 untampered smooth motion + 15 tampered with duplicated
   frame runs and/or dropped-frame splice jumps).
3. Audio Tampering Suite (n=40 audio clips: 20 continuous room recordings + 20 cut-and-paste
   spliced recordings with phase transients and/or room-tone shifts).
"""

from __future__ import annotations

import io
import json
import math
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np  # provenance: seeded-resampling-ok
from PIL import Image

from satyapan.forensics.tamper import (
    analyze_audio_tampering,
    analyze_image_tampering,
    analyze_video_tampering,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "results" / "forensics_m3_tamper.json"
SEED = 20261103


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


def _natural_rgb(rng: np.random.Generator, size: int = 256) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    fx = float(rng.uniform(1.0, 2.5))
    fy = float(rng.uniform(1.0, 2.5))
    ph = float(rng.uniform(0, 3.14))
    base = (
        85.0 + 65.0 * np.sin(2.0 * np.pi * fx * xx + ph) + 45.0 * np.cos(2.0 * np.pi * fy * yy - ph)
    )
    noise = rng.normal(0.0, 3.0, (size, size, 3)).astype(np.float32)
    rgb = np.stack([base, base * 0.96, base * 1.04], axis=-1) + noise
    return np.clip(rgb, 10, 245).astype(np.uint8)


def _encode_jpeg_bytes(rgb: np.ndarray, quality: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def eval_images(rng: np.random.Generator, tmp_dir: Path) -> dict[str, Any]:
    y_true: list[int] = []
    combined_scores: list[float] = []
    ela_spliced_scores: list[float] = []
    nr_spliced_scores: list[float] = []
    cm_forged_scores: list[float] = []
    djpeg_scores: list[float] = []
    auth_ela_scores: list[float] = []
    auth_cm_scores: list[float] = []
    auth_nr_scores: list[float] = []
    auth_djpeg_scores: list[float] = []

    # 1. 40 authentic single-compression JPEGs (Q82..Q94)
    for i in range(40):
        rgb = _natural_rgb(rng)
        q = int(rng.integers(82, 95))
        p = tmp_dir / f"auth_{i:03d}.jpg"
        p.write_bytes(_encode_jpeg_bytes(rgb, q))
        res = analyze_image_tampering(p)
        y_true.append(0)
        combined_scores.append(res.tamper_probability)
        auth_ela_scores.append(float(res.subchecks["ela"]["score"]))
        auth_cm_scores.append(float(res.subchecks["copy_move"]["score"]))
        auth_nr_scores.append(float(res.subchecks["noise_residual"]["score"]))
        auth_djpeg_scores.append(float(res.subchecks["double_jpeg"]["score"]))

    # 2. 30 spliced foreign patch images (Q70 background + unquantized noisy patch saved as PNG)
    for i in range(30):
        rgb = _natural_rgb(rng)
        bg_bytes = _encode_jpeg_bytes(rgb, quality=70)
        bg = np.asarray(Image.open(io.BytesIO(bg_bytes)).convert("RGB"), dtype=np.uint8).copy()
        y0 = int(rng.integers(32, 160))
        x0 = int(rng.integers(32, 160))
        patch = rng.integers(15, 240, (64, 64, 3), dtype=np.uint8)
        bg[y0 : y0 + 64, x0 : x0 + 64] = patch
        p = tmp_dir / f"splice_{i:03d}.png"
        Image.fromarray(bg).save(p, format="PNG")
        res = analyze_image_tampering(p)
        y_true.append(1)
        combined_scores.append(res.tamper_probability)
        ela_spliced_scores.append(float(res.subchecks["ela"]["score"]))
        nr_spliced_scores.append(float(res.subchecks["noise_residual"]["score"]))

    # 3. 30 copy-move forged images
    for i in range(30):
        rgb = _natural_rgb(rng)
        obj = rng.integers(25, 230, (48, 48, 3), dtype=np.uint8)
        y1, x1 = int(rng.integers(16, 80)), int(rng.integers(16, 80))
        y2, x2 = int(rng.integers(136, 196)), int(rng.integers(136, 196))
        rgb[y1 : y1 + 48, x1 : x1 + 48] = obj
        rgb[y2 : y2 + 48, x2 : x2 + 48] = obj
        p = tmp_dir / f"copymove_{i:03d}.png"
        Image.fromarray(rgb).save(p, format="PNG")
        res = analyze_image_tampering(p)
        y_true.append(1)
        combined_scores.append(res.tamper_probability)
        cm_forged_scores.append(float(res.subchecks["copy_move"]["score"]))

    # 4. 20 double-JPEG + 8x8 grid-spliced images (Q50 -> spliced smooth region -> Q92)
    for i in range(20):
        rgb = _natural_rgb(rng)
        q1_bytes = _encode_jpeg_bytes(rgb, quality=50)
        q1_img = np.asarray(Image.open(io.BytesIO(q1_bytes)).convert("RGB"), dtype=np.uint8).copy()
        # Smooth out a 64x64 region to break the 8x8 JPEG grid + re-save at Q94
        q1_img[64:128, 64:128] = 128
        p = tmp_dir / f"djpeg_{i:03d}.jpg"
        p.write_bytes(_encode_jpeg_bytes(q1_img, quality=94))
        res = analyze_image_tampering(p)
        y_true.append(1)
        combined_scores.append(res.tamper_probability)
        djpeg_scores.append(float(res.subchecks["double_jpeg"]["score"]))

    n_auth = 40
    n_tamp = 80
    tp = sum(1 for y, s in zip(y_true, combined_scores, strict=True) if y == 1 and s >= 0.42)
    fp = sum(1 for y, s in zip(y_true, combined_scores, strict=True) if y == 0 and s >= 0.42)

    return {
        "n_authentic": n_auth,
        "n_tampered": n_tamp,
        "combined_auc": roc_auc(y_true, combined_scores),
        "combined_tpr": round(tp / n_tamp, 4),
        "combined_tpr_ci": wilson_ci(tp, n_tamp),
        "combined_fpr": round(fp / n_auth, 4),
        "combined_fpr_ci": wilson_ci(fp, n_auth),
        "subdetectors": {
            "ela_on_spliced_auc": roc_auc(
                [0] * 40 + [1] * 30, auth_ela_scores + ela_spliced_scores
            ),
            "noise_residual_on_spliced_auc": roc_auc(
                [0] * 40 + [1] * 30, auth_nr_scores + nr_spliced_scores
            ),
            "copy_move_on_cloned_auc": roc_auc(
                [0] * 40 + [1] * 30, auth_cm_scores + cm_forged_scores
            ),
            "double_jpeg_auc": roc_auc([0] * 40 + [1] * 20, auth_djpeg_scores + djpeg_scores),
        },
    }


def eval_videos(rng: np.random.Generator, tmp_dir: Path) -> dict[str, Any]:
    import av

    y_true: list[int] = []
    scores: list[float] = []
    yy, xx = np.mgrid[0:96, 0:128].astype(np.float32)

    for idx in range(30):
        is_tampered = idx >= 15
        mp4 = tmp_dir / f"vid_{idx:03d}.mp4"
        container = av.open(str(mp4), mode="w")
        stream = container.add_stream("mpeg4", rate=15)
        stream.width = 128
        stream.height = 96
        stream.pix_fmt = "yuv420p"
        stream.bit_rate = 600_000

        speed = float(rng.uniform(2.5, 4.0))
        frames: list[np.ndarray] = []
        for f_i in range(24):
            shift = f_i * speed
            val = 125.0 + 85.0 * np.sin((xx + shift) * 0.09) + 35.0 * np.cos((yy + shift) * 0.09)
            rgb = np.clip(np.stack([val, val * 0.92, val * 1.05], axis=-1), 0, 255).astype(np.uint8)
            frames.append(rgb)

        if is_tampered:
            if idx % 2 == 0:
                # Duplicated frame freeze run (4 frames)
                for k in range(8, 12):
                    frames[k] = frames[7].copy()
            else:
                # Frame-drop / splice inversion jump
                frames[14] = (255 - frames[13]).copy()

        for rgb in frames:
            vf = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            for pkt in stream.encode(vf):
                container.mux(pkt)
        for pkt in stream.encode():
            container.mux(pkt)
        container.close()

        res = analyze_video_tampering(mp4)
        y_true.append(1 if is_tampered else 0)
        scores.append(res.tamper_probability)

    tp = sum(1 for y, s in zip(y_true, scores, strict=True) if y == 1 and s >= 0.42)
    fp = sum(1 for y, s in zip(y_true, scores, strict=True) if y == 0 and s >= 0.42)
    return {
        "n_authentic": 15,
        "n_tampered": 15,
        "auc": roc_auc(y_true, scores),
        "tpr": round(tp / 15, 4),
        "tpr_ci": wilson_ci(tp, 15),
        "fpr": round(fp / 15, 4),
        "fpr_ci": wilson_ci(fp, 15),
    }


def eval_audio(rng: np.random.Generator, tmp_dir: Path) -> dict[str, Any]:
    sr = 16000
    y_true: list[int] = []
    scores: list[float] = []

    for idx in range(40):
        is_tampered = idx >= 20
        f0 = float(rng.uniform(160.0, 280.0))
        if not is_tampered:
            t = np.linspace(0, 3.0, 3 * sr, endpoint=False)
            sig = 0.25 * np.sin(2.0 * np.pi * f0 * t) + rng.normal(0.0, 0.004, len(t))
        else:
            t1 = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
            t2 = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
            s1 = 0.20 * np.sin(2.0 * np.pi * f0 * t1) + rng.normal(0.0, 0.002, len(t1))
            s2 = 0.30 * np.sin(2.0 * np.pi * (f0 * 1.35) * t2) + rng.normal(0.0, 0.065, len(t2))
            s2[0] = 0.92  # splice transient
            sig = np.concatenate([s1, s2])

        pcm = (np.clip(sig, -0.99, 0.99) * 32767).astype(np.int16)
        wav_path = tmp_dir / f"aud_{idx:03d}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())

        res = analyze_audio_tampering(wav_path)
        y_true.append(1 if is_tampered else 0)
        scores.append(res.tamper_probability)

    tp = sum(1 for y, s in zip(y_true, scores, strict=True) if y == 1 and s >= 0.42)
    fp = sum(1 for y, s in zip(y_true, scores, strict=True) if y == 0 and s >= 0.42)
    return {
        "n_authentic": 20,
        "n_tampered": 20,
        "auc": roc_auc(y_true, scores),
        "tpr": round(tp / 20, 4),
        "tpr_ci": wilson_ci(tp, 20),
        "fpr": round(fp / 20, 4),
        "fpr_ci": wilson_ci(fp, 20),
    }


def run_all() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)  # provenance: seeded-resampling-ok
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        img_res = eval_images(rng, tdir)
        vid_res = eval_videos(rng, tdir)
        aud_res = eval_audio(rng, tdir)

    summary = {
        "milestone": "M3",
        "seed": SEED,
        "dataset": "synthetic_multimedia_tamper_benchmark (labeled synthetic)",
        "image_tampering": img_res,
        "video_tampering": vid_res,
        "audio_tampering": aud_res,
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    out = run_all()
    print(json.dumps(out, indent=2))
