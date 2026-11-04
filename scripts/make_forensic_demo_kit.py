"""Build the deterministic committed forensic demo kit in `demo_kit/`.

Usage: `uv run python scripts/make_forensic_demo_kit.py`.

Generates 6 multi-modal forensic exhibits (JPEG, PNG, WAV, MP4), `manifest.json`, and
`golden_section63.md` for end-to-end and golden-file acceptance tests (M7).
"""

from __future__ import annotations

import hashlib
import io
import json
import struct
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image, PngImagePlugin

from satyapan.forensics.locker import ForensicEvidenceItem
from satyapan.forensics.provenance import embed_c2pa_jumbf_manifest
from satyapan.forensics.section63 import (
    build_section63_certificate,
    render_section63_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_KIT_DIR = ROOT / "demo_kit"
SEED = 20261106
FIXED_TIME = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)


def _deterministic_ed25519_key(seed_str: str) -> Ed25519PrivateKey:
    raw32 = hashlib.sha256(seed_str.encode("utf-8")).digest()
    return Ed25519PrivateKey.from_private_bytes(raw32)


def build_demo_kit(out_dir: Path = DEMO_KIT_DIR) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    h, w = 256, 256
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) / float(h)
    base = 95.0 + 60.0 * np.sin(2.0 * np.pi * 1.5 * xx) + 45.0 * np.cos(2.0 * np.pi * 1.2 * yy)
    noise = rng.normal(0.0, 3.0, (h, w, 3)).astype(np.float32)
    clean_rgb = np.clip(
        np.stack([base, base * 0.96, base * 1.04], axis=-1) + noise, 10, 245
    ).astype(np.uint8)

    # 1. 01_authentic_c2pa_photo.jpg
    im1 = Image.fromarray(clean_rgb)
    ex1 = im1.getexif()
    ex1[0x010F] = "Sony"
    ex1[0x0110] = "ILCE-7M4"
    ex1[0x9003] = "2026:10:18 11:00:00"
    ex1[0x0132] = "2026:10:18 11:00:00"
    b1 = io.BytesIO()
    im1.save(b1, format="JPEG", quality=95, subsampling=0, exif=ex1.tobytes())
    priv = _deterministic_ed25519_key("satyapan-demo-c2pa-key-v1")
    signed_jpg = embed_c2pa_jumbf_manifest(
        b1.getvalue(),
        {
            "claim_generator": "Sony ILCE-7M4 C2PA/2.0",
            "title": "Authentic Field Exhibit 01",
            "actions": [{"action": "c2pa.created"}],
        },
        priv,
        signer_id="sony-c2pa-demo-signer",
    )
    f1 = out_dir / "01_authentic_c2pa_photo.jpg"
    f1.write_bytes(signed_jpg)

    # 2. 02_synthetic_gan_scene.png
    grid2 = ((-1.0) ** (np.arange(h)[:, None] + np.arange(w)[None, :])).astype(np.float32)
    syn_r = base + 4.0 * grid2 + rng.normal(0.0, 1.0, (h, w))
    syn_g = base - 3.4 * grid2 + rng.normal(0.0, 1.0, (h, w))
    syn_b = base + 3.6 * grid2 + rng.normal(0.0, 1.0, (h, w))
    syn_rgb = np.clip(np.stack([syn_r, syn_g, syn_b], axis=-1), 0, 255).astype(np.uint8)
    pi2 = PngImagePlugin.PngInfo()
    pi2.add_text("parameters", "ComfyUI workflow, Steps: 28, Sampler: Euler, CFG scale: 7.0")
    f2 = out_dir / "02_synthetic_gan_scene.png"
    Image.fromarray(syn_rgb).save(f2, format="PNG", pnginfo=pi2)

    # 3. 03_tampered_copymove_splice.jpg
    tamp_rgb = clean_rgb.copy()
    obj = rng.integers(30, 225, (48, 48, 3), dtype=np.uint8)
    tamp_rgb[24:72, 24:72] = obj
    tamp_rgb[140:188, 140:188] = obj
    im3 = Image.fromarray(tamp_rgb)
    ex3 = im3.getexif()
    ex3[0x010F] = "Canon"
    ex3[0x0110] = "Canon EOS R6"
    ex3[0x0131] = "Adobe Photoshop 25.4"
    ex3[0x9003] = "2026:10:22 16:30:00"
    ex3[0x0132] = "2026:10:20 09:15:00"
    tb3 = io.BytesIO()
    Image.fromarray(255 - clean_rgb).save(tb3, format="JPEG", quality=75)
    ex3_bytes = ex3.tobytes() + b"\x00\x00" + tb3.getvalue()
    b3 = io.BytesIO()
    im3.save(b3, format="JPEG", quality=90)
    raw3 = b3.getvalue()
    app1_3 = b"\xff\xe1" + struct.pack(">H", len(ex3_bytes) + 2) + ex3_bytes
    f3 = out_dir / "03_tampered_copymove_splice.jpg"
    f3.write_bytes(raw3[:2] + app1_3 + raw3[2:])

    # 4. 04_whatsapp_reencoded_photo.jpg
    f4 = out_dir / "04_whatsapp_reencoded_photo.jpg"
    Image.fromarray(clean_rgb).save(f4, format="JPEG", quality=68, subsampling=2)

    # 5. 05_spliced_audio_recording.wav
    sr = 16000
    t1 = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
    t2 = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
    s1 = 0.20 * np.sin(2.0 * np.pi * 200.0 * t1) + rng.normal(0.0, 0.002, len(t1))
    s2 = 0.30 * np.sin(2.0 * np.pi * 310.0 * t2) + rng.normal(0.0, 0.075, len(t2))
    s2[0] = 0.95
    pcm = (np.clip(np.concatenate([s1, s2]), -0.99, 0.99) * 32767).astype(np.int16)
    f5 = out_dir / "05_spliced_audio_recording.wav"
    with wave.open(str(f5), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    # 6. 06_manipulated_video_clip.mp4
    import av

    f6 = out_dir / "06_manipulated_video_clip.mp4"
    container = av.open(str(f6), mode="w")
    stream = container.add_stream("mpeg4", rate=15)
    stream.width = 128
    stream.height = 96
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 500_000
    vy, vx = np.mgrid[0:96, 0:128].astype(np.float32)
    v_frames: list[np.ndarray] = []
    for fi in range(20):
        sh = fi * 3.5
        val = 125.0 + 85.0 * np.sin((vx + sh) * 0.09) + 35.0 * np.cos((vy + sh) * 0.09)
        v_frames.append(
            np.clip(np.stack([val, val * 0.92, val * 1.05], axis=-1), 0, 255).astype(np.uint8)
        )
    for k in range(6, 10):
        v_frames[k] = v_frames[5].copy()
    v_frames[14] = (255 - v_frames[13]).copy()
    for fr in v_frames:
        vf = av.VideoFrame.from_ndarray(fr, format="rgb24")
        for pkt in stream.encode(vf):
            container.mux(pkt)
    for pkt in stream.encode():
        container.mux(pkt)
    container.close()

    exhibits = [
        (
            f1,
            "image",
            "witness-camera",
            {"make": "Sony", "model": "ILCE-7M4", "os": "Firmware 3.0"},
            "consistent_with_authentic",
        ),
        (
            f2,
            "image",
            "suspect-workstation",
            {"make": "Custom", "model": "GPU-Node", "os": "Linux"},
            "consistent_with_manipulation",
        ),
        (
            f3,
            "image",
            "seized-laptop",
            {"make": "Apple", "model": "MacBookPro", "os": "macOS"},
            "consistent_with_manipulation",
        ),
        (
            f4,
            "image",
            "messaging-export",
            {"make": "Android", "model": "WhatsApp Media", "os": "Android"},
            "anomalies_detected_verify",
        ),
        (
            f5,
            "audio",
            "voice-recorder",
            {"make": "Samsung", "model": "S24", "os": "Android"},
            "consistent_with_manipulation",
        ),
        (
            f6,
            "video",
            "dvr-export",
            {"make": "Hikvision", "model": "NVR", "os": "Embedded"},
            "consistent_with_manipulation",
        ),
    ]

    manifest_items = []
    ev_items: list[ForensicEvidenceItem] = []
    for idx, (fp, stype, dev, dinfo, exp_finding) in enumerate(exhibits, 1):
        eid = f"EV{idx:04d}"
        sha = hashlib.sha256(fp.read_bytes()).hexdigest()
        sz = fp.stat().st_size
        manifest_items.append(
            {
                "evidence_id": eid,
                "filename": fp.name,
                "source_type": stype,
                "device": dev,
                "device_info": dinfo,
                "sha256": sha,
                "size_bytes": sz,
                "expected_overall_finding": exp_finding,
            }
        )
        ev_items.append(
            ForensicEvidenceItem(
                evidence_id=eid,
                case_id="case_demo_kit",
                original_name=fp.name,
                stored_path=f"originals/{eid}__{fp.name}",
                working_path=f"working/{eid}__{fp.name}",
                sha256=sha,
                size_bytes=sz,
                media_type="application/octet-stream",
                source_type=stype,
                device=dev,
                collector="examiner_arjun",
                collected_at_utc=FIXED_TIME,
                device_info=dinfo,
            )
        )

    manifest = {
        "kit_name": "Satyapan Forensic Demo Kit v1.0",
        "seed": SEED,
        "generated_by": "scripts/make_forensic_demo_kit.py",
        "licence": "MIT (100% synthetic/procedurally generated test media, zero private data)",
        "items": manifest_items,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Build golden Section 63 certificate markdown for deterministic golden-file testing
    cert = build_section63_certificate(
        ev_items,
        {"name": "Arjun Mehta", "role": "Senior Digital Forensic Examiner"},
        examiner={
            "name": "Arjun Mehta",
            "designation": "Senior Digital Forensic Examiner",
            "organisation": "National Cyber Forensic Laboratory",
        },
        integrity={
            "ok": True,
            "chain_head": "a" * 64,
            "custody_entries": 18,
            "records": [{"evidence_id": i.evidence_id, "sha256": i.sha256} for i in ev_items],
            "anchor": {
                "merkle_root": build_section63_certificate(ev_items)["part_b"]["merkle"]["root"],
                "chain_head": "a" * 64,
                "anchored_at_utc": FIXED_TIME.isoformat(),
            },
            "signers": [{"signer": "examiner_arjun", "public_key_sha256": "b" * 64}],
        },
        generated_at_utc=FIXED_TIME.isoformat(),
    )
    golden_md = render_section63_markdown(cert)
    (out_dir / "golden_section63.md").write_text(golden_md, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build_demo_kit()
    print(f"Built demo_kit with {len(m['items'])} items.")  # type: ignore[arg-type]
