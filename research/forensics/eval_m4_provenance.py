"""M4 Reproducible Provenance & Source Attribution Benchmark (`eval_m4_provenance.py`).

Evaluates on a seeded benchmark (`SEED = 20261104`, labeled synthetic re-encoded set in ledger):
1. Compression-Fingerprint Source Attribution across 150 re-encoded images (50 per class):
   - `camera_original` (camera EXIF Make/Model + Q92..Q98 + 4:4:4/4:2:2 + intact APP1 thumbnail);
   - `social_messaging_reencode` (WhatsApp/Instagram stripped EXIF + 4:2:0 chroma + Q55..Q82);
   - `editing_software_resave` (Photoshop/GIMP/FFmpeg tag, PNG export, or thumbnail mismatch).
   Reports overall accuracy, macro-F1, and per-class precision/recall.
2. Metadata Consistency Anomaly Benchmark (n=60: 30 clean camera metadata + 30 tampered metadata:
   date inversion, Null Island GPS, AI generator parameters, thumbnail mismatch, PNG camera spoof).
3. C2PA Content Credentials JUMBF Benchmark (n=30: 15 valid Ed25519-signed JPEG/PNG manifests +
   15 post-signing byte-tampered or signature-corrupted manifests).
"""

from __future__ import annotations

import io
import json
import struct
import tempfile
from pathlib import Path
from typing import Any

import numpy as np  # provenance: seeded-resampling-ok
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image, PngImagePlugin

from satyapan.forensics.provenance import (
    analyze_provenance,
    embed_c2pa_jumbf_manifest,
    verify_c2pa_credentials,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "results" / "forensics_m4_provenance.json"
SEED = 20261104


def _make_scene_rgb(rng: np.random.Generator, w: int = 320, h: int = 240) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fx = float(rng.uniform(0.02, 0.06))
    fy = float(rng.uniform(0.02, 0.06))
    r = 110.0 + 60.0 * np.sin(xx * fx) + rng.normal(0, 3.0, (h, w))
    g = 115.0 + 55.0 * np.cos(yy * fy) + rng.normal(0, 3.0, (h, w))
    b = 95.0 + 45.0 * np.sin((xx + yy) * 0.5 * fx) + rng.normal(0, 3.0, (h, w))
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def _jpeg_with_exif(
    rgb: np.ndarray,
    *,
    make: str = "",
    model: str = "",
    software: str = "",
    dt_orig: str = "2026:10:12 11:00:00",
    dt_mod: str = "2026:10:12 11:00:00",
    gps_null: bool = False,
    thumb_rgb: np.ndarray | None = None,
    quality: int = 94,
    subsampling: int = 0,
) -> bytes:
    im = Image.fromarray(rgb)
    exif = im.getexif()
    if make:
        exif[0x010F] = make
    if model:
        exif[0x0110] = model
    if software:
        exif[0x0131] = software
    if dt_mod:
        exif[0x0132] = dt_mod
    if dt_orig:
        exif[0x9003] = dt_orig
    if gps_null:
        exif[0x8825] = {
            1: "N",
            2: (0.0, 0.0, 0.0),
            3: "E",
            4: (0.0, 0.0, 0.0),
        }
    eb = exif.tobytes()
    if thumb_rgb is not None:
        tb = io.BytesIO()
        Image.fromarray(thumb_rgb).save(tb, format="JPEG", quality=75)
        eb = eb + b"\x00\x00" + tb.getvalue()
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, subsampling=subsampling)
    raw = buf.getvalue()
    app1 = b"\xff\xe1" + struct.pack(">H", len(eb) + 2) + eb
    return raw[:2] + app1 + raw[2:]


def eval_attribution_and_metadata() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)  # provenance: seeded-resampling-ok
    classes = ["camera_original", "social_messaging_reencode", "editing_software_resave"]
    y_true: list[str] = []
    y_pred: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        cameras = [
            ("Canon", "EOS R6"),
            ("Nikon", "Z8"),
            ("Sony", "ILCE-7M4"),
            ("Apple", "iPhone 16 Pro"),
        ]
        editors = [
            "Adobe Photoshop 25.2",
            "GIMP 2.10.36",
            "Lightroom Classic 13.0",
            "FFmpeg Lavf60.16",
        ]

        # 1. 50 camera_original
        for i in range(50):
            rgb = _make_scene_rgb(rng)
            mk, md = cameras[i % len(cameras)]
            q = int(rng.integers(92, 99))
            sub = 0 if i % 2 == 0 else 1
            b = _jpeg_with_exif(rgb, make=mk, model=md, thumb_rgb=rgb, quality=q, subsampling=sub)
            p = tdir / f"cam_{i:03d}.jpg"
            p.write_bytes(b)
            res = analyze_provenance(p)
            y_true.append("camera_original")
            y_pred.append(res.source_attribution)

        # 2. 50 social_messaging_reencode (WhatsApp/Instagram style: stripped EXIF, 4:2:0, Q56..Q83)
        for i in range(50):
            rgb = _make_scene_rgb(rng)
            q = int(rng.integers(56, 84))
            buf = io.BytesIO()
            Image.fromarray(rgb).save(buf, format="JPEG", quality=q, subsampling=2)
            p = tdir / f"wa_{i:03d}.jpg"
            p.write_bytes(buf.getvalue())
            res = analyze_provenance(p)
            y_true.append("social_messaging_reencode")
            y_pred.append(res.source_attribution)

        # 3. 50 editing_software_resave (software tag, PNG export, or thumbnail mismatch)
        for i in range(50):
            rgb = _make_scene_rgb(rng)
            mode = i % 3
            if mode == 0:
                sw = editors[i % len(editors)]
                b = _jpeg_with_exif(rgb, software=sw, quality=int(rng.integers(85, 96)))
                p = tdir / f"ed_{i:03d}.jpg"
                p.write_bytes(b)
            elif mode == 1:
                p = tdir / f"ed_{i:03d}.png"
                Image.fromarray(rgb).save(p, format="PNG")
            else:
                b = _jpeg_with_exif(
                    rgb, make="Canon", model="EOS R6", thumb_rgb=(255 - rgb), quality=90
                )
                p = tdir / f"ed_{i:03d}.jpg"
                p.write_bytes(b)
            res = analyze_provenance(p)
            y_true.append("editing_software_resave")
            y_pred.append(res.source_attribution)

        # Compute per-class precision, recall, F1, and overall accuracy
        per_class: dict[str, dict[str, float]] = {}
        f1s: list[float] = []
        for c in classes:
            tp = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == c and yp == c)
            fp = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt != c and yp == c)
            fn = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == c and yp != c)
            prec = tp / max(1, tp + fp)
            rec = tp / max(1, tp + fn)
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
            f1s.append(f1)
            per_class[c] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
            }
        overall_acc = round(
            sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == yp) / len(y_true), 4
        )
        macro_f1 = round(float(np.mean(f1s)), 4)

        # 4. Metadata Consistency Anomaly Benchmark (30 clean camera + 30 metadata anomalies)
        meta_tp = 0
        meta_fp = 0
        for i in range(30):
            rgb = _make_scene_rgb(rng, w=160, h=120)
            b = _jpeg_with_exif(rgb, make="Sony", model="A7IV", thumb_rgb=rgb, quality=94)
            p = tdir / f"mclean_{i:03d}.jpg"
            p.write_bytes(b)
            r = analyze_provenance(p)
            if r.anomaly_score >= 0.65:
                meta_fp += 1

        for i in range(30):
            rgb = _make_scene_rgb(rng, w=160, h=120)
            kind = i % 5
            if kind == 0:
                # Date inversion
                b = _jpeg_with_exif(
                    rgb,
                    make="Sony",
                    model="A7IV",
                    dt_orig="2026:10:25 12:00:00",
                    dt_mod="2026:10:20 08:00:00",
                )
                p = tdir / f"mbad_{i:03d}.jpg"
                p.write_bytes(b)
            elif kind == 1:
                # Null island GPS
                b = _jpeg_with_exif(rgb, make="Sony", model="A7IV", gps_null=True)
                p = tdir / f"mbad_{i:03d}.jpg"
                p.write_bytes(b)
            elif kind == 2:
                # Thumbnail vs main image mismatch
                b = _jpeg_with_exif(rgb, make="Sony", model="A7IV", thumb_rgb=(255 - rgb))
                p = tdir / f"mbad_{i:03d}.jpg"
                p.write_bytes(b)
            elif kind == 3:
                # AI generator PNG chunk
                p = tdir / f"mbad_{i:03d}.png"
                pi = PngImagePlugin.PngInfo()
                pi.add_text("parameters", "ComfyUI workflow, Steps: 25, CFG scale: 7.5")
                Image.fromarray(rgb).save(p, format="PNG", pnginfo=pi)
            else:
                # Editing software tag
                b = _jpeg_with_exif(rgb, software="Adobe Photoshop 2026")
                p = tdir / f"mbad_{i:03d}.jpg"
                p.write_bytes(b)
            r = analyze_provenance(p)
            if r.anomaly_score >= 0.65:
                meta_tp += 1

        # 5. C2PA Content Credentials Verification Benchmark (15 valid + 15 tampered)
        priv = Ed25519PrivateKey.generate()
        c2pa_valid_verified = 0
        c2pa_tampered_caught = 0
        for i in range(15):
            rgb = _make_scene_rgb(rng, w=128, h=128)
            buf = io.BytesIO()
            Image.fromarray(rgb).save(buf, format="JPEG" if i % 2 == 0 else "PNG")
            signed = embed_c2pa_jumbf_manifest(
                buf.getvalue(),
                {"title": f"Asset {i}", "actions": [{"action": "c2pa.created"}]},
                priv,
            )
            if verify_c2pa_credentials(signed)["status"] == "valid_c2pa_manifest":
                c2pa_valid_verified += 1
            tampered = bytearray(signed)
            tampered[-16] ^= 0x01
            if verify_c2pa_credentials(bytes(tampered))["status"] == "tampered_c2pa_hash_mismatch":
                c2pa_tampered_caught += 1

    summary = {
        "milestone": "M4",
        "seed": SEED,
        "compression_attribution": {
            "n_total": 150,
            "n_per_class": 50,
            "accuracy": overall_acc,
            "macro_f1": macro_f1,
            "per_class": per_class,
        },
        "metadata_consistency": {
            "n_clean": 30,
            "n_anomalous": 30,
            "tpr": round(meta_tp / 30, 4),
            "fpr": round(meta_fp / 30, 4),
            "caught": f"{meta_tp}/30",
            "false_alarms": f"{meta_fp}/30",
        },
        "c2pa_verification": {
            "engine": "satyapan-jumbf-c2pa (c2pa-python fallback documented in BLOCKERS.md)",
            "valid_manifests_verified": f"{c2pa_valid_verified}/15",
            "post_sign_tampering_caught": f"{c2pa_tampered_caught}/15",
        },
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    out = eval_attribution_and_metadata()
    print(json.dumps(out, indent=2))
