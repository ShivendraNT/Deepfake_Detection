"""Unified Forensic Case Pipeline (`src/satyapan/forensics/pipeline.py`).

Orchestrates M1 (ForensicLocker working-copy checkout + signed custody log), M2 (Deepfake &
Synthetic Media Engine), M3 (Multimedia Tampering Suite), and M4 (Provenance, C2PA & Source
Attribution) across all evidence items in a case, persists `analysis.json`, and builds the
chronological case timeline and limitations summary.
"""

from __future__ import annotations

import io
import json
import struct
import wave
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image

from satyapan.forensics.deepfake import (
    analyze_audio_deepfake,
    analyze_image_deepfake,
    analyze_video_deepfake,
)
from satyapan.forensics.locker import ForensicLocker, utcnow
from satyapan.forensics.provenance import (
    analyze_provenance,
    embed_c2pa_jumbf_manifest,
)
from satyapan.forensics.tamper import (
    analyze_audio_tampering,
    analyze_image_tampering,
    analyze_video_tampering,
)

ANALYSIS_FILE = "analysis.json"


def infer_source_and_media_type(filename: str) -> tuple[str, str]:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        return "image", "image/jpeg"
    if ext == "png":
        return "image", "image/png"
    if ext in ("webp", "bmp", "tiff"):
        return "image", f"image/{ext}"
    if ext in ("mp4", "mov", "mkv", "avi"):
        return "video", "video/mp4"
    if ext == "webm":
        return "video", "video/webm"
    if ext == "wav":
        return "audio", "audio/wav"
    if ext in ("mp3", "ogg", "opus", "m4a", "flac"):
        return "audio", f"audio/{ext}"
    if ext == "pdf":
        return "document", "application/pdf"
    return "document", "application/octet-stream"


def _combine_item_verdict(
    source_type: str,
    deepfake: dict[str, Any] | None,
    tamper: dict[str, Any] | None,
    provenance: dict[str, Any] | None,
) -> tuple[str, float, str, list[str], list[str]]:
    """Combine M2, M3, and M4 findings into a single non-absolutist item assessment."""
    df_prob = float((deepfake or {}).get("synthetic_probability") or 0.0)
    tm_prob = float((tamper or {}).get("tamper_probability") or 0.0)
    pr_prob = float((provenance or {}).get("anomaly_score") or 0.0)

    max_score = round(max(df_prob, tm_prob, pr_prob), 4)
    why: list[str] = []
    limits: list[str] = []

    for section, label in [
        (deepfake, "Deepfake/Synthetic Check"),
        (tamper, "Tampering Check"),
        (provenance, "Provenance/Attribution Check"),
    ]:
        if not section:
            continue
        for w in section.get("why") or []:
            entry = f"[{label}] {w}"
            if entry not in why:
                why.append(entry)
        for lim in section.get("limitations") or []:
            if lim not in limits:
                limits.append(lim)

    high_flags = []
    if df_prob >= 0.60:
        high_flags.append(f"synthetic generation (score {df_prob:.2f})")
    if tm_prob >= 0.62:
        high_flags.append(f"post-capture tampering (score {tm_prob:.2f})")
    if pr_prob >= 0.65:
        high_flags.append(f"provenance/metadata inconsistency (score {pr_prob:.2f})")

    if high_flags:
        finding = "consistent_with_manipulation"
        conf = round(min(0.97, 0.72 + 0.25 * max_score), 3)
        stmt = (
            f"Multi-engine forensic examination of this {source_type} is consistent with "
            f"{', '.join(high_flags)} (overall confidence {conf:.2f}). "
            "Findings assist the human examiner and do not by themselves establish guilt."
        )
    elif max_score >= 0.42:
        finding = "anomalies_detected_verify"
        conf = round(0.55 + 0.20 * max_score, 3)
        stmt = (
            f"Forensic checks detected moderate anomalies or re-encoding indicators on this "
            f"{source_type} (peak anomaly score {max_score:.2f}, confidence {conf:.2f}). "
            "Independent corroboration and manual verification are required."
        )
    else:
        finding = "consistent_with_authentic"
        conf = round(0.75 + 0.20 * (1.0 - max_score), 3)
        stmt = (
            f"Deepfake, tampering, and provenance checks found no manipulation indicators "
            f"on this {source_type} (peak anomaly score {max_score:.2f}, confidence {conf:.2f}); "
            "observations are consistent with authentic origin within stated detector limits."
        )

    return finding, conf, stmt, why, limits


def analyze_evidence_item(
    locker: ForensicLocker,
    evidence_id: str,
    *,
    use_heavy_models: bool = False,
) -> dict[str, Any]:
    """Checkout a verified working copy of `evidence_id` and run all applicable M2, M3, and M4
    forensic checks on the working copy."""
    item = locker.get_item(evidence_id)
    work_path = locker.checkout_working_copy(
        evidence_id, purpose=f"full_forensic_suite_{item.source_type}"
    )
    art_dir = locker.artifacts_dir / evidence_id
    art_dir.mkdir(parents=True, exist_ok=True)

    df_dict: dict[str, Any] | None = None
    tm_dict: dict[str, Any] | None = None
    pr_dict: dict[str, Any] | None = None

    if item.source_type == "image":
        df_res = analyze_image_deepfake(
            work_path, locker=locker, artifact_dir=art_dir, use_heavy_models=use_heavy_models
        )
        tm_res = analyze_image_tampering(work_path, locker=locker, artifact_dir=art_dir)
        pr_res = analyze_provenance(work_path, locker=locker, artifact_dir=art_dir)
        df_dict = df_res.to_dict()
        tm_dict = tm_res.to_dict()
        pr_dict = pr_res.to_dict()
    elif item.source_type == "video":
        df_res = analyze_video_deepfake(
            work_path,
            locker=locker,
            artifact_dir=art_dir,
            use_heavy_models=use_heavy_models,
            max_frames=10,
        )
        tm_res = analyze_video_tampering(work_path, locker=locker, artifact_dir=art_dir)
        pr_res = analyze_provenance(work_path, locker=locker, artifact_dir=art_dir)
        df_dict = df_res.to_dict()
        tm_dict = tm_res.to_dict()
        pr_dict = pr_res.to_dict()
    elif item.source_type == "audio":
        df_res = analyze_audio_deepfake(
            work_path, locker=locker, artifact_dir=art_dir, use_heavy_models=use_heavy_models
        )
        tm_res = analyze_audio_tampering(work_path, locker=locker, artifact_dir=art_dir)
        df_dict = df_res.to_dict()
        tm_dict = tm_res.to_dict()
    else:
        pr_res = analyze_provenance(work_path, locker=locker, artifact_dir=art_dir)
        pr_dict = pr_res.to_dict()

    finding, conf, stmt, why, limits = _combine_item_verdict(
        item.source_type, df_dict, tm_dict, pr_dict
    )

    # Collect relative artifact filenames inside art_dir
    artifact_files: dict[str, str] = {}
    for sub in (df_dict, tm_dict, pr_dict):
        if not sub:
            continue
        for k, fpath in (sub.get("artifacts") or {}).items():
            p = Path(fpath)
            if p.exists():
                artifact_files[k] = p.name

    item_report = {
        "evidence_id": item.evidence_id,
        "original_name": item.original_name,
        "source_type": item.source_type,
        "media_type": item.media_type,
        "sha256": item.sha256,
        "size_bytes": item.size_bytes,
        "device": item.device,
        "collected_at_utc": item.collected_at_utc.isoformat(),
        "working_copy_verified": True,
        "overall_finding": finding,
        "overall_confidence": conf,
        "overall_statement": stmt,
        "why": why,
        "limitations": limits,
        "deepfake": df_dict,
        "tampering": tm_dict,
        "provenance": pr_dict,
        "artifact_files": artifact_files,
    }
    (art_dir / "item_analysis.json").write_text(json.dumps(item_report, indent=2), encoding="utf-8")

    locker.log_action(
        evidence_id=evidence_id,
        action="analyze",
        file_sha256=item.sha256,
        notes=f"Completed M2/M3/M4 analysis on working copy -> {finding} (conf={conf:.2f})",
    )
    locker.write_anchor()
    return item_report


def analyze_case(
    locker: ForensicLocker,
    *,
    use_heavy_models: bool = False,
) -> dict[str, Any]:
    """Run forensic analysis across all items in `locker`, build the chronological timeline, and
    persist `case_dir/analysis.json`."""
    item_reports: list[dict[str, Any]] = []
    for item in locker.items():
        art_json = locker.artifacts_dir / item.evidence_id / "item_analysis.json"
        if art_json.exists():
            rep = json.loads(art_json.read_text(encoding="utf-8"))
        else:
            rep = analyze_evidence_item(locker, item.evidence_id, use_heavy_models=use_heavy_models)
        item_reports.append(rep)

    # Build unified chronological timeline (metadata events + custody log events)
    timeline: list[dict[str, Any]] = []
    for rep in item_reports:
        eid = rep["evidence_id"]
        pr = rep.get("provenance") or {}
        for ev in pr.get("timeline_events") or []:
            timeline.append(
                {
                    "time_utc": ev["time_utc"],
                    "kind": "metadata",
                    "evidence_id": eid,
                    "actor": rep.get("device", "media"),
                    "description": f"{eid} ({rep['original_name']}): {ev['event']}",
                }
            )
        tm = rep.get("tampering") or {}
        for loc in tm.get("localized_regions") or []:
            timeline.append(
                {
                    "time_utc": rep["collected_at_utc"],
                    "kind": "anomaly",
                    "evidence_id": eid,
                    "actor": "forensic_detector",
                    "description": (
                        f"{eid} ({rep['original_name']}): {loc.get('type')} at "
                        f"timestamps {loc.get('timestamps_s')}s"
                    ),
                }
            )

    for ce in locker.custody_entries():
        timeline.append(
            {
                "time_utc": ce.time_utc.isoformat(),
                "kind": "custody",
                "evidence_id": ce.evidence_id,
                "actor": ce.actor,
                "description": f"[Seq #{ce.seq} · {ce.action.upper()}] {ce.notes or ce.file_sha256[:16]}",
                "link_hash": ce.link[:16],
            }
        )

    timeline.sort(key=lambda x: str(x.get("time_utc", "")))

    # Aggregate global limitations
    global_limits = [
        "All forensic findings are probabilistic assessments ('consistent with' / 'inconsistent with') intended to assist a qualified human examiner; software never decides guilt or legal admissibility.",
        "Cryptographic SHA-256 hashes, Ed25519 custody signatures, and RFC 6962 Merkle proofs attest to integrity since intake, not to truth prior to seizure.",
        "Heavy lossy re-compression (e.g., WhatsApp/social media forwarding) attenuates high-frequency pixel, spectral, and CFA sensor cues.",
        "Unsigned EXIF/XMP metadata fields can be altered prior to intake unless bound by a verified C2PA Content Credentials signature.",
    ]
    for rep in item_reports:
        for lim in rep.get("limitations") or []:
            if lim not in global_limits:
                global_limits.append(lim)

    integrity = locker.integrity_info()
    merkle_proofs = {i.evidence_id: locker.audit_proof(i.evidence_id) for i in locker.items()}

    case_analysis = {
        "case_id": locker.case_id,
        "case_meta": locker.case_meta(),
        "generated_at_utc": utcnow().isoformat(),
        "integrity": integrity,
        "merkle_proofs": merkle_proofs,
        "items": item_reports,
        "timeline": timeline,
        "custody_log": [e.to_dict() for e in locker.custody_entries()],
        "limitations_of_analysis": global_limits,
    }
    (locker.case_dir / ANALYSIS_FILE).write_text(
        json.dumps(case_analysis, indent=2), encoding="utf-8"
    )
    return case_analysis


def load_case_analysis(locker: ForensicLocker) -> dict[str, Any]:
    """Load `analysis.json` and refresh live `integrity` and `merkle_proofs` so tamper simulations
    immediately reflect in the dashboard and report."""
    path = locker.case_dir / ANALYSIS_FILE
    if not path.exists():
        return analyze_case(locker)
    data = dict(json.loads(path.read_text(encoding="utf-8")))
    data["integrity"] = locker.integrity_info()
    data["merkle_proofs"] = {
        i.evidence_id: locker.audit_proof(i.evidence_id) for i in locker.items()
    }
    data["custody_log"] = [e.to_dict() for e in locker.custody_entries()]
    return data


# ---------------------------------------------------------------------------
# Built-in Multi-Modal Demo Case Seeder
# ---------------------------------------------------------------------------


def seed_demo_forensic_case(
    cases_root: str | Path,
    case_id: str = "case_forensic_demo_01",
    *,
    use_heavy_models: bool = False,
) -> ForensicLocker:
    """Create a rich, self-contained 4-item multi-modal forensic investigation case offline:
    - EV0001: Tampered invoice/scene photo (copy-move + spliced patch + Photoshop EXIF + inverted
      timestamps + mismatched embedded EXIF thumbnail);
    - EV0002: C2PA-signed authentic field photograph (valid Ed25519 JUMBF C2PA Content Credentials
      + Canon EOS R6 EXIF);
    - EV0003: Spliced extortion voice recording (cut-and-paste room noise-floor shift + splice
      transient + synthetic harmonic segment);
    - EV0004: Manipulated video clip (duplicated freeze-frame run + dropped-frame splice jump).
    """
    case_dir = Path(cases_root) / case_id
    locker = ForensicLocker(
        case_dir,
        collector="examiner_arjun",
        case_meta={
            "title": "Digital Impersonation & Manipulated Multimedia Evidence Investigation",
            "agency": "National Cyber Forensic Laboratory (NCFL — Demo Unit)",
            "examiner": "Arjun Mehta (Senior Digital Forensic Examiner)",
            "fir_reference": "FIR-2026-CYB-0419 (Demo)",
        },
    )
    if len(locker.items()) >= 4 and (case_dir / ANALYSIS_FILE).exists():
        return locker

    rng = np.random.default_rng(20261105)
    h, w = 256, 256
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) / float(h)
    base = 95.0 + 60.0 * np.sin(2.0 * np.pi * 1.5 * xx) + 45.0 * np.cos(2.0 * np.pi * 1.2 * yy)
    noise = rng.normal(0.0, 3.0, (h, w, 3)).astype(np.float32)
    clean_rgb = np.clip(
        np.stack([base, base * 0.96, base * 1.04], axis=-1) + noise, 10, 245
    ).astype(np.uint8)

    # 1. EV0001: Tampered image (copy-move cloned region + spliced patch + mismatched thumbnail + Photoshop EXIF)
    tampered_rgb = clean_rgb.copy()
    obj = rng.integers(30, 225, (48, 48, 3), dtype=np.uint8)
    tampered_rgb[24:72, 24:72] = obj
    tampered_rgb[140:188, 140:188] = obj
    im1 = Image.fromarray(tampered_rgb)
    ex1 = im1.getexif()
    ex1[0x010F] = "Canon"
    ex1[0x0110] = "Canon EOS R6"
    ex1[0x0131] = "Adobe Photoshop 25.4"
    ex1[0x9003] = "2026:10:22 16:30:00"  # DateTimeOriginal LATER than DateTime!
    ex1[0x0132] = "2026:10:20 09:15:00"
    t_buf = io.BytesIO()
    Image.fromarray(255 - clean_rgb).save(t_buf, format="JPEG", quality=75)
    ex1_bytes = ex1.tobytes() + b"\x00\x00" + t_buf.getvalue()
    b1 = io.BytesIO()
    im1.save(b1, format="JPEG", quality=90)
    raw1 = b1.getvalue()
    app1 = b"\xff\xe1" + struct.pack(">H", len(ex1_bytes) + 2) + ex1_bytes
    jpeg1 = raw1[:2] + app1 + raw1[2:]
    locker.intake_bytes(
        jpeg1,
        "suspect_payment_proof_edited.jpg",
        source_type="image",
        media_type="image/jpeg",
        device="seized-laptop-A",
        device_info={"make": "Apple", "model": "MacBookPro18,3", "os": "macOS 14.6"},
    )

    # 2. EV0002: Authentic C2PA-signed camera photograph
    im2 = Image.fromarray(clean_rgb)
    ex2 = im2.getexif()
    ex2[0x010F] = "Sony"
    ex2[0x0110] = "ILCE-7M4"
    ex2[0x9003] = "2026:10:18 11:00:00"
    ex2[0x0132] = "2026:10:18 11:00:00"
    b2 = io.BytesIO()
    im2.save(b2, format="JPEG", quality=95, subsampling=0, exif=ex2.tobytes())
    c2pa_priv = Ed25519PrivateKey.generate()
    signed_jpeg2 = embed_c2pa_jumbf_manifest(
        b2.getvalue(),
        {
            "claim_generator": "Sony ILCE-7M4 In-Camera C2PA/2.0",
            "title": "Verified Reference Scene Photo",
            "actions": [{"action": "c2pa.created"}],
        },
        c2pa_priv,
        signer_id="sony-camera-hardware-key",
    )
    locker.intake_bytes(
        signed_jpeg2,
        "reference_camera_c2pa_signed.jpg",
        source_type="image",
        media_type="image/jpeg",
        device="witness-camera-B",
        device_info={"make": "Sony", "model": "ILCE-7M4", "os": "Camera Firmware 3.01"},
    )

    # 3. EV0003: Spliced extortion audio clip (room noise-floor shift + splice transient)
    sr = 16000
    t1 = np.linspace(0, 2.0, 2 * sr, endpoint=False)
    t2 = np.linspace(0, 2.0, 2 * sr, endpoint=False)
    s1 = 0.20 * np.sin(2.0 * np.pi * 195.0 * t1) + rng.normal(0.0, 0.002, len(t1))
    s2 = 0.30 * np.sin(2.0 * np.pi * 290.0 * t2) + rng.normal(0.0, 0.075, len(t2))
    s2[0] = 0.95
    pcm = (np.clip(np.concatenate([s1, s2]), -0.99, 0.99) * 32767).astype(np.int16)
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    locker.intake_bytes(
        wav_buf.getvalue(),
        "spliced_voice_threat_note.wav",
        source_type="audio",
        media_type="audio/wav",
        device="seized-phone-C",
        device_info={"make": "Samsung", "model": "SM-S918B", "os": "Android 14"},
    )

    # 4. EV0004: Manipulated video clip (duplicated freeze frames + splice jump)
    import av

    vid_buf = io.BytesIO()
    container = av.open(vid_buf, mode="w", format="mp4")
    stream = container.add_stream("mpeg4", rate=15)
    stream.width = 160
    stream.height = 120
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 600_000
    vy, vx = np.mgrid[0:120, 0:160].astype(np.float32)
    v_frames: list[np.ndarray] = []
    for fi in range(24):
        sh = fi * 3.5
        val = 125.0 + 85.0 * np.sin((vx + sh) * 0.09) + 35.0 * np.cos((vy + sh) * 0.09)
        v_frames.append(
            np.clip(np.stack([val, val * 0.92, val * 1.05], axis=-1), 0, 255).astype(np.uint8)
        )
    for k in range(7, 11):
        v_frames[k] = v_frames[6].copy()
    v_frames[16] = (255 - v_frames[15]).copy()
    for fr in v_frames:
        vf = av.VideoFrame.from_ndarray(fr, format="rgb24")
        for pkt in stream.encode(vf):
            container.mux(pkt)
    for pkt in stream.encode():
        container.mux(pkt)
    container.close()
    locker.intake_bytes(
        vid_buf.getvalue(),
        "manipulated_cctv_clip.mp4",
        source_type="video",
        media_type="video/mp4",
        device="dvr-export-D",
        device_info={"make": "Hikvision", "model": "DS-7608", "os": "Embedded NVR"},
    )

    analyze_case(locker, use_heavy_models=use_heavy_models)
    return locker
