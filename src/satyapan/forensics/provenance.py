"""M4 — Multimedia Provenance, Metadata Consistency, C2PA Content Credentials & Compression
Source Attribution (`src/satyapan/forensics/provenance.py`).

Implements:
1. EXIF / XMP / PNG / Container metadata extraction & 5 consistency checks:
   - Timestamp chronology (`DateTimeOriginal` vs `DateTimeDigitized` vs `DateTime` vs XMP);
   - Editing & generative AI software signatures (Photoshop, GIMP, FFmpeg, Stable Diffusion,
     ComfyUI, Midjourney, DALL-E, Firefly);
   - GPS coordinate validity, Null Island (0, 0) detection, and GPS-vs-EXIF date consistency;
   - Embedded EXIF APP1 thumbnail extraction & comparison against the main image (aspect ratio +
     normalized correlation / pixel difference), rendering `thumbnail_comparison.png`;
   - Camera Make/Model vs container format consistency.
2. C2PA Content Credentials / JUMBF (`c2pa` UUID `63327061-0011-0010-8000-00aa00389b71`) verifier:
   - Uses `c2pa-python` if installed; otherwise runs a pure-Python JPEG APP11 (`0xFFEB`) / PNG
     `caBX` / ISO BMFF `uuid` JUMBF parser with SHA-256 hard-binding and Ed25519 signature
     verification.
3. Compression-fingerprint source attribution:
   - Parses JPEG `SOF0`/`SOF2` chroma subsampling (`4:4:4`, `4:2:2`, `4:2:0`), luminance/chrominance
     quantization tables, resolution profile, and metadata survival to classify images into
     `camera_original`, `social_messaging_reencode` (WhatsApp/Instagram-style), or
     `editing_software_resave`.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import zlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from PIL import ExifTags, Image, ImageDraw

from satyapan.forensics.locker import ForensicLocker

C2PA_UUID = bytes.fromhex("6332706100110010800000aa00389b71")
C2PA_MAGIC = b"JUMBF_C2PA_V1:"

EDITING_SIGNATURES = (
    "photoshop",
    "lightroom",
    "gimp",
    "affinity",
    "paint.net",
    "pixlr",
    "snapseed",
    "canva",
    "picsart",
    "ffmpeg",
    "handbrake",
    "lavf",
    "audacity",
    "premiere",
    "davinci",
    "capcut",
)

AI_GENERATOR_SIGNATURES = (
    "stable diffusion",
    "automatic1111",
    "comfyui",
    "midjourney",
    "dall-e",
    "dalle",
    "firefly",
    "adobe firefly",
    "invokeai",
    "flux",
    "novelai",
    " sdxl",
    "cfg scale:",
    "sampler:",
)


@dataclass
class ProvenanceAnalysisResult:
    """Standardized forensic output for M4 provenance and source attribution."""

    modality: str
    finding: str  # "consistent_with_manipulation_or_editing" | "anomalies_detected_verify" | ...
    confidence: float
    anomaly_score: float
    source_attribution: str  # "camera_original" | "social_messaging_reencode" | ...
    attribution_probabilities: dict[str, float]
    statement: str
    why: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    consistency_checks: dict[str, Any] = field(default_factory=dict)
    c2pa: dict[str, Any] = field(default_factory=dict)
    compression_profile: dict[str, Any] = field(default_factory=dict)
    timeline_events: list[dict[str, str]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. Low-Level JPEG / PNG / XMP / EXIF / Thumbnail Parsers
# ---------------------------------------------------------------------------


def _parse_exif_datetime(val: Any) -> datetime | None:
    if not val:
        return None
    s = str(val).strip().rstrip("\x00")
    for fmt in (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s[:19] if "T" not in fmt else s, fmt)
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        except Exception:  # noqa: BLE001
            continue
    return None


def _rational_to_float(v: Any) -> float | None:
    try:
        if isinstance(v, tuple) and len(v) == 2:
            return float(v[0]) / float(v[1]) if float(v[1]) != 0 else 0.0
        return float(v)
    except Exception:  # noqa: BLE001
        return None


def _decode_gps_coord(coord: Any, ref: str) -> float | None:
    try:
        if not isinstance(coord, tuple | list) or len(coord) < 3:
            return None
        d = _rational_to_float(coord[0])
        m = _rational_to_float(coord[1])
        s = _rational_to_float(coord[2])
        if d is None or m is None or s is None:
            return None
        deg = d + m / 60.0 + s / 3600.0
        if str(ref).upper().strip() in ("S", "W"):
            deg = -deg
        return round(deg, 6)
    except Exception:  # noqa: BLE001
        return None


def _extract_embedded_jpeg_thumbnail(raw_bytes: bytes) -> bytes | None:
    """Locate an embedded JPEG thumbnail inside the EXIF APP1 segment (second SOI..EOI pair)."""
    if not raw_bytes.startswith(b"\xff\xd8"):
        return None
    # Search inside APP1 (0xFFE1) segments
    pos = 2
    n = len(raw_bytes)
    while pos + 4 <= n and raw_bytes[pos] == 0xFF:
        marker = raw_bytes[pos + 1]
        if marker in (0xDA, 0xD9):  # SOS or EOI
            break
        if marker == 0xFF:
            pos += 1
            continue
        seg_len = struct.unpack(">H", raw_bytes[pos + 2 : pos + 4])[0]
        seg_data = raw_bytes[pos + 4 : pos + 2 + seg_len]
        if marker == 0xE1 and seg_data.startswith(b"Exif\x00\x00"):
            soi = seg_data.find(b"\xff\xd8\xff", 6)
            if soi != -1:
                eoi = seg_data.find(b"\xff\xd9", soi + 3)
                if eoi != -1:
                    return seg_data[soi : eoi + 2]
        pos += 2 + seg_len
    return None


def _parse_jpeg_chroma_subsampling(raw_bytes: bytes) -> str:
    """Parse JPEG SOF0/SOF2 marker to determine chroma subsampling ('4:4:4', '4:2:2', '4:2:0')."""
    if not raw_bytes.startswith(b"\xff\xd8"):
        return "none"
    pos = 2
    n = len(raw_bytes)
    while pos + 4 <= n and raw_bytes[pos] == 0xFF:
        marker = raw_bytes[pos + 1]
        if marker in (0xDA, 0xD9):
            break
        if marker == 0xFF:
            pos += 1
            continue
        seg_len = struct.unpack(">H", raw_bytes[pos + 2 : pos + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):  # Baseline / Extended / Progressive SOF
            sof = raw_bytes[pos + 4 : pos + 2 + seg_len]
            if len(sof) >= 15 and sof[5] == 3:
                # Component 1 sampling byte is at sof[7], Component 2 at sof[10]
                samp1 = sof[7]
                samp2 = sof[10]
                h1, v1 = (samp1 >> 4) & 0x0F, samp1 & 0x0F
                h2, v2 = (samp2 >> 4) & 0x0F, samp2 & 0x0F
                if (h1, v1) == (1, 1) and (h2, v2) == (1, 1):
                    return "4:4:4"
                if (h1, v1) == (2, 1) and (h2, v2) == (1, 1):
                    return "4:2:2"
                if (h1, v1) == (2, 2) and (h2, v2) == (1, 1):
                    return "4:2:0"
                return f"{h1}x{v1}:{h2}x{v2}"
        pos += 2 + seg_len
    return "unknown"


def _extract_xmp_packet(raw_bytes: bytes) -> dict[str, str]:
    """Extract key XMP tags from an embedded `<x:xmpmeta ...>` XML packet if present."""
    out: dict[str, str] = {}
    start = raw_bytes.find(b"<x:xmpmeta")
    if start == -1:
        start = raw_bytes.find(b"<xmp:CreateDate")
    if start == -1:
        return out
    end = raw_bytes.find(b"</x:xmpmeta>", start)
    snippet = raw_bytes[start : (end + 12 if end != -1 else min(len(raw_bytes), start + 16384))]
    text = snippet.decode("utf-8", errors="ignore")
    for tag in (
        "CreateDate",
        "ModifyDate",
        "MetadataDate",
        "CreatorTool",
        "Software",
        "DigitalSourceType",
        "credit",
    ):
        m = re.search(rf"(?:xmp:|photoshop:|exif:|Iptc4xmpExt:)?{tag}[>=\"']([^<\"']+)", text)
        if m:
            out[tag] = m.group(1).strip()
    return out


# ---------------------------------------------------------------------------
# 2. Metadata Extraction & 5 Consistency Checks
# ---------------------------------------------------------------------------


def extract_and_verify_metadata(
    raw_bytes: bytes,
    filename: str = "",
    artifact_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]], dict[str, str]]:
    """Return `(metadata_dict, consistency_checks, timeline_events, artifacts)`."""
    exif_dict: dict[str, Any] = {}
    png_info: dict[str, str] = {}
    gps_info: dict[str, Any] = {}
    img_format = "UNKNOWN"
    width, height = 0, 0

    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            img_format = im.format or "UNKNOWN"
            width, height = im.size
            for k, v in (im.info or {}).items():
                if isinstance(k, str) and isinstance(v, str | int | float) and k.lower() != "exif":
                    png_info[k] = str(v)[:500]
            raw_exif = im.getexif()
            if raw_exif:
                for tag_id, val in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if tag_name == "GPSInfo":
                        continue
                    if isinstance(val, bytes):
                        try:
                            exif_dict[tag_name] = val.decode("utf-8", errors="ignore").strip("\x00")
                        except Exception:  # noqa: BLE001
                            continue
                    else:
                        exif_dict[tag_name] = str(val)
                # Exif SubIFD (0x8769)
                try:
                    sub_ifd = raw_exif.get_ifd(0x8769)
                    for tid, val in (sub_ifd or {}).items():
                        tname = ExifTags.TAGS.get(tid, str(tid))
                        if not isinstance(val, bytes):
                            exif_dict[tname] = str(val)
                except Exception:  # noqa: BLE001
                    pass
                # GPS IFD (0x8825)
                try:
                    gps_ifd = raw_exif.get_ifd(0x8825)
                    for tid, val in (gps_ifd or {}).items():
                        gname = ExifTags.GPSTAGS.get(tid, str(tid))
                        gps_info[gname] = val
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass

    xmp_dict = _extract_xmp_packet(raw_bytes)
    anomalies: list[str] = []
    timeline: list[dict[str, str]] = []
    artifacts: dict[str, str] = {}

    # Check 1: Timestamp Chronology
    dt_orig = _parse_exif_datetime(exif_dict.get("DateTimeOriginal") or xmp_dict.get("CreateDate"))
    dt_dig = _parse_exif_datetime(exif_dict.get("DateTimeDigitized"))
    dt_mod = _parse_exif_datetime(exif_dict.get("DateTime") or xmp_dict.get("ModifyDate"))

    if dt_orig:
        timeline.append(
            {
                "time_utc": dt_orig.isoformat(),
                "event": "EXIF/XMP DateTimeOriginal (claimed capture)",
                "source": filename or "metadata",
            }
        )
    if dt_dig and dt_dig != dt_orig:
        timeline.append(
            {
                "time_utc": dt_dig.isoformat(),
                "event": "EXIF DateTimeDigitized",
                "source": filename or "metadata",
            }
        )
    if dt_mod:
        timeline.append(
            {
                "time_utc": dt_mod.isoformat(),
                "event": "EXIF/XMP ModifyDate",
                "source": filename or "metadata",
            }
        )

    date_consistent = True
    if dt_orig and dt_mod and (dt_orig - dt_mod).total_seconds() > 60:
        date_consistent = False
        anomalies.append(
            f"Timestamp chronology inversion: DateTimeOriginal ({dt_orig.isoformat()}) is later "
            f"than ModifyDate ({dt_mod.isoformat()})."
        )
    if dt_orig and dt_dig and abs((dt_dig - dt_orig).total_seconds()) > 86400 * 365:
        date_consistent = False
        anomalies.append(
            f"Large discrepancy (>1 year) between DateTimeOriginal ({dt_orig.isoformat()}) "
            f"and DateTimeDigitized ({dt_dig.isoformat()})."
        )

    # Check 2: Software & Generative AI Signatures
    combined_sw_fields = " | ".join(
        str(v)
        for v in [
            exif_dict.get("Software", ""),
            exif_dict.get("ProcessingSoftware", ""),
            xmp_dict.get("CreatorTool", ""),
            xmp_dict.get("Software", ""),
            xmp_dict.get("DigitalSourceType", ""),
            png_info.get("Software", ""),
            png_info.get("parameters", ""),
            png_info.get("prompt", ""),
            png_info.get("Comment", ""),
        ]
        if v
    )
    sw_lower = combined_sw_fields.lower()
    detected_editors = [ed for ed in EDITING_SIGNATURES if ed in sw_lower]
    detected_ai = [ai for ai in AI_GENERATOR_SIGNATURES if ai in sw_lower]
    if "trainedalgorithmicmedia" in sw_lower and "trainedAlgorithmicMedia" not in detected_ai:
        detected_ai.append("IPTC:trainedAlgorithmicMedia")

    if detected_ai:
        anomalies.append(
            f"Metadata contains generative AI signature(s): {', '.join(detected_ai)} "
            f"({combined_sw_fields[:120]})."
        )
    if detected_editors:
        anomalies.append(
            f"Metadata records post-processing / editing software: {', '.join(detected_editors)}."
        )

    # Check 3: GPS Plausibility & Consistency
    gps_lat = _decode_gps_coord(
        gps_info.get("GPSLatitude"), str(gps_info.get("GPSLatitudeRef", "N"))
    )
    gps_lon = _decode_gps_coord(
        gps_info.get("GPSLongitude"), str(gps_info.get("GPSLongitudeRef", "E"))
    )
    gps_valid = True
    if gps_lat is not None and gps_lon is not None:
        if not (-90.0 <= gps_lat <= 90.0 and -180.0 <= gps_lon <= 180.0):
            gps_valid = False
            anomalies.append(f"Invalid out-of-range EXIF GPS coordinates: ({gps_lat}, {gps_lon}).")
        elif abs(gps_lat) < 1e-4 and abs(gps_lon) < 1e-4:
            gps_valid = False
            anomalies.append(
                "EXIF GPS points to Null Island (0.0, 0.0), typical of synthetic/spoofed EXIF."
            )
    gps_date_str = str(gps_info.get("GPSDateStamp", "")).strip()
    if gps_date_str and dt_orig:
        dt_gps = _parse_exif_datetime(f"{gps_date_str} 00:00:00")
        if dt_gps and abs((dt_orig - dt_gps).total_seconds()) > 86400 * 3:
            gps_valid = False
            anomalies.append(
                f"EXIF GPSDateStamp ({gps_date_str}) disagrees with DateTimeOriginal "
                f"({dt_orig.date().isoformat()}) by more than 3 days."
            )

    # Check 4: Embedded EXIF Thumbnail vs Main Image Consistency
    thumb_bytes = _extract_embedded_jpeg_thumbnail(raw_bytes)
    thumb_info: dict[str, Any] = {"present": False, "consistent": True}
    if thumb_bytes is not None and width > 0 and height > 0:
        try:
            with (
                Image.open(io.BytesIO(thumb_bytes)) as t_im,
                Image.open(io.BytesIO(raw_bytes)) as m_im,
            ):
                tw, th = t_im.size
                t_rgb = np.asarray(t_im.convert("RGB"), dtype=np.float32)
                m_resized = np.asarray(
                    m_im.convert("RGB").resize((tw, th), Image.Resampling.BILINEAR),
                    dtype=np.float32,
                )
                aspect_diff = abs((tw / max(1.0, float(th))) - (width / max(1.0, float(height))))
                mae = float(np.mean(np.abs(t_rgb - m_resized)))
                t_zm = t_rgb.ravel() - float(np.mean(t_rgb))
                m_zm = m_resized.ravel() - float(np.mean(m_resized))
                denom = float(np.linalg.norm(t_zm) * np.linalg.norm(m_zm))
                corr = float(np.sum(t_zm * m_zm) / denom) if denom > 1e-4 else 1.0

                thumb_consistent = aspect_diff <= 0.08 and mae <= 20.0 and corr >= 0.78
                thumb_info = {
                    "present": True,
                    "consistent": thumb_consistent,
                    "thumb_size": [tw, th],
                    "aspect_ratio_diff": round(aspect_diff, 4),
                    "pixel_mae": round(mae, 2),
                    "correlation": round(corr, 4),
                }
                if not thumb_consistent:
                    anomalies.append(
                        f"Embedded EXIF thumbnail disagrees with main image "
                        f"(MAE={mae:.1f}, corr={corr:.2f}, aspect_diff={aspect_diff:.3f}); "
                        "main image was likely cropped or spliced after original capture."
                    )
                if artifact_dir is not None:
                    adir = Path(artifact_dir)
                    adir.mkdir(parents=True, exist_ok=True)
                    comp = Image.new("RGB", (420, 210), (18, 22, 31))
                    draw = ImageDraw.Draw(comp)
                    comp.paste(t_im.convert("RGB").resize((180, 150)), (15, 40))
                    comp.paste(m_im.convert("RGB").resize((180, 150)), (225, 40))
                    draw.text((15, 12), f"EXIF Thumbnail ({tw}x{th})", fill=(220, 226, 236))
                    draw.text((225, 12), f"Main Image ({width}x{height})", fill=(220, 226, 236))
                    t_path = adir / "thumbnail_comparison.png"
                    comp.save(t_path, format="PNG")
                    artifacts["thumbnail_comparison"] = str(t_path)
        except Exception:  # noqa: BLE001
            pass

    # Check 5: Camera Make/Model vs Container Format Consistency
    camera_make = str(exif_dict.get("Make", "")).strip()
    camera_model = str(exif_dict.get("Model", "")).strip()
    camera_consistent = True
    if (camera_make or camera_model) and img_format == "PNG":
        camera_consistent = False
        anomalies.append(
            f"Contradictory container: file claims camera EXIF ({camera_make} {camera_model}) "
            "inside a PNG container rather than native camera JPEG/HEIC/RAW."
        )

    metadata_out = {
        "format": img_format,
        "width": width,
        "height": height,
        "camera_make": camera_make or None,
        "camera_model": camera_model or None,
        "software": combined_sw_fields or None,
        "datetime_original": dt_orig.isoformat() if dt_orig else None,
        "datetime_digitized": dt_dig.isoformat() if dt_dig else None,
        "datetime_modified": dt_mod.isoformat() if dt_mod else None,
        "gps": {"lat": gps_lat, "lon": gps_lon, "date": gps_date_str or None}
        if (gps_lat is not None or gps_lon is not None)
        else None,
        "exif_tag_count": len(exif_dict),
        "xmp_tags": xmp_dict,
        "png_text_chunks": png_info,
    }

    checks_out = {
        "timestamp_chronology_ok": date_consistent,
        "detected_editing_software": detected_editors,
        "detected_ai_generators": detected_ai,
        "gps_plausible": gps_valid,
        "thumbnail_check": thumb_info,
        "camera_container_consistent": camera_consistent,
        "anomalies": anomalies,
    }
    return metadata_out, checks_out, timeline, artifacts


# ---------------------------------------------------------------------------
# 3. C2PA Content Credentials / JUMBF Parser & Verifier
# ---------------------------------------------------------------------------


def embed_c2pa_jumbf_manifest(
    image_bytes: bytes,
    claim: dict[str, Any],
    private_key: Ed25519PrivateKey,
    signer_id: str = "satyapan-c2pa-authority",
) -> bytes:
    """Embed a signed JUMBF C2PA manifest into a JPEG (APP11 `0xFFEB`) or PNG (`caBX` chunk).

    Used by tests and the demo kit generator to produce verifiable C2PA-signed assets offline.
    """
    pub_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    if image_bytes.startswith(b"\xff\xd8"):
        # Compute SHA-256 over the JPEG payload (SOI + everything after where APP11 sits)
        payload_sha256 = hashlib.sha256(image_bytes).hexdigest()
        full_claim = {
            "c2pa_version": "2.0",
            "claim_generator": claim.get("claim_generator", "Satyapan Forensic C2PA Signer/1.0"),
            "title": claim.get("title", "Authenticated Multimedia Asset"),
            "digital_source_type": claim.get(
                "digital_source_type",
                "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
            ),
            "actions": claim.get("actions", [{"action": "c2pa.created"}]),
            "hard_binding_sha256": payload_sha256,
            "signer_id": signer_id,
            "public_key_pem": pub_pem,
        }
        claim_json = json.dumps(full_claim, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature_hex = private_key.sign(claim_json).hex()
        envelope = json.dumps(
            {"claim": full_claim, "signature": signature_hex},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        jumbf_body = C2PA_UUID + C2PA_MAGIC + envelope
        seg_len = len(jumbf_body) + 2
        app11 = b"\xff\xeb" + struct.pack(">H", seg_len) + jumbf_body
        return image_bytes[:2] + app11 + image_bytes[2:]

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        payload_sha256 = hashlib.sha256(image_bytes).hexdigest()
        full_claim = {
            "c2pa_version": "2.0",
            "claim_generator": claim.get("claim_generator", "Satyapan Forensic C2PA Signer/1.0"),
            "title": claim.get("title", "Authenticated Multimedia Asset"),
            "digital_source_type": claim.get(
                "digital_source_type",
                "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
            ),
            "actions": claim.get("actions", [{"action": "c2pa.created"}]),
            "hard_binding_sha256": payload_sha256,
            "signer_id": signer_id,
            "public_key_pem": pub_pem,
        }
        claim_json = json.dumps(full_claim, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature_hex = private_key.sign(claim_json).hex()
        envelope = json.dumps(
            {"claim": full_claim, "signature": signature_hex},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        chunk_data = C2PA_UUID + C2PA_MAGIC + envelope
        chunk_type = b"caBX"
        crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        chunk = (
            struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", crc)
        )
        # Insert right before IEND (last 12 bytes)
        return image_bytes[:-12] + chunk + image_bytes[-12:]

    raise ValueError("Unsupported container for C2PA JUMBF embedding")


def verify_c2pa_credentials(raw_bytes: bytes) -> dict[str, Any]:
    """Verify C2PA Content Credentials if present in `raw_bytes`."""
    # 1. Try external `c2pa` library if installed
    try:
        import c2pa  # type: ignore[import-not-found]

        reader = c2pa.Reader.from_stream("image/jpeg", io.BytesIO(raw_bytes))
        manifest_json = json.loads(reader.json())
        return {
            "present": True,
            "engine": "c2pa-python",
            "status": "valid_c2pa_manifest",
            "manifest": manifest_json,
        }
    except Exception:  # noqa: BLE001
        pass

    # 2. Pure-Python JUMBF (`c2pa` UUID) superbox detector and verifier
    idx = raw_bytes.find(C2PA_UUID)
    if idx == -1:
        return {
            "present": False,
            "engine": "satyapan-jumbf-c2pa",
            "status": "no_c2pa_manifest",
            "claim_generator": None,
            "digital_source_type": None,
        }

    magic_pos = idx + len(C2PA_UUID)
    if raw_bytes[magic_pos : magic_pos + len(C2PA_MAGIC)] != C2PA_MAGIC:
        return {
            "present": True,
            "engine": "satyapan-jumbf-c2pa",
            "status": "unparsed_c2pa_jumbf_box",
            "note": "Detected ISO JUMBF c2pa UUID box; external COSE chain needs c2pa-python.",
        }

    # Extract envelope JSON and reconstruct stripped payload for hard-binding SHA-256 check
    try:
        if (
            raw_bytes.startswith(b"\xff\xd8")
            and idx >= 4
            and raw_bytes[idx - 4 : idx - 2] == b"\xff\xeb"
        ):
            seg_start = idx - 4
            seg_len = struct.unpack(">H", raw_bytes[seg_start + 2 : seg_start + 4])[0]
            seg_end = seg_start + 2 + seg_len
            json_bytes = raw_bytes[magic_pos + len(C2PA_MAGIC) : seg_end]
            stripped_bytes = raw_bytes[:seg_start] + raw_bytes[seg_end:]
        elif raw_bytes.startswith(b"\x89PNG") and idx >= 8 and raw_bytes[idx - 4 : idx] == b"caBX":
            chunk_start = idx - 8
            c_len = struct.unpack(">I", raw_bytes[chunk_start : chunk_start + 4])[0]
            chunk_end = chunk_start + 8 + c_len + 4
            chunk_data = raw_bytes[chunk_start + 8 : chunk_start + 8 + c_len]
            stored_crc = struct.unpack(">I", raw_bytes[chunk_start + 8 + c_len : chunk_end])[0]
            calc_crc = zlib.crc32(b"caBX" + chunk_data) & 0xFFFFFFFF
            if stored_crc != calc_crc:
                return {
                    "present": True,
                    "engine": "satyapan-jumbf-c2pa",
                    "status": "tampered_c2pa_hash_mismatch",
                    "signature_valid": False,
                    "hard_binding_valid": False,
                }
            json_bytes = raw_bytes[magic_pos + len(C2PA_MAGIC) : chunk_start + 8 + c_len]
            stripped_bytes = raw_bytes[:chunk_start] + raw_bytes[chunk_end:]
        else:
            return {
                "present": True,
                "engine": "satyapan-jumbf-c2pa",
                "status": "malformed_c2pa_container",
            }

        envelope = json.loads(json_bytes.decode("utf-8"))
        claim = dict(envelope["claim"])
        sig_hex = str(envelope["signature"])
        pub_pem = str(claim["public_key_pem"]).encode("utf-8")
        pub_key = serialization.load_pem_public_key(pub_pem)
        if not isinstance(pub_key, Ed25519PublicKey):
            return {
                "present": True,
                "engine": "satyapan-jumbf-c2pa",
                "status": "unsupported_c2pa_key_type",
            }

        claim_canonical = json.dumps(claim, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            pub_key.verify(bytes.fromhex(sig_hex), claim_canonical)
            sig_ok = True
        except Exception:  # noqa: BLE001
            sig_ok = False

        actual_sha = hashlib.sha256(stripped_bytes).hexdigest()
        expected_sha = str(claim.get("hard_binding_sha256", ""))
        hash_ok = actual_sha == expected_sha

        if not sig_ok:
            status = "invalid_c2pa_signature"
        elif not hash_ok:
            status = "tampered_c2pa_hash_mismatch"
        else:
            status = "valid_c2pa_manifest"

        return {
            "present": True,
            "engine": "satyapan-jumbf-c2pa",
            "status": status,
            "signature_valid": sig_ok,
            "hard_binding_valid": hash_ok,
            "claim_generator": claim.get("claim_generator"),
            "title": claim.get("title"),
            "signer_id": claim.get("signer_id"),
            "digital_source_type": claim.get("digital_source_type"),
            "actions": claim.get("actions", []),
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "present": True,
            "engine": "satyapan-jumbf-c2pa",
            "status": "invalid_c2pa_manifest",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# 4. Compression-Fingerprint Source Attribution
# ---------------------------------------------------------------------------


def attribute_compression_source(
    raw_bytes: bytes,
    metadata_info: dict[str, Any],
    consistency_checks: dict[str, Any],
) -> dict[str, Any]:
    """Attribute an image's compression fingerprint to:
    - `camera_original`: camera EXIF + high-Q or 4:2:2/4:4:4 JPEG or intact thumbnail;
    - `social_messaging_reencode`: stripped EXIF + 4:2:0 JPEG Q50..Q84 + clamped dimensions;
    - `editing_software_resave`: editing software tags, non-standard Q-table, PNG re-save, or
      thumbnail mismatch.
    """
    img_format = str(metadata_info.get("format", "UNKNOWN"))
    width = int(metadata_info.get("width") or 0)
    height = int(metadata_info.get("height") or 0)
    long_edge = max(width, height)
    has_camera_exif = bool(metadata_info.get("camera_make") or metadata_info.get("camera_model"))
    has_any_exif = int(metadata_info.get("exif_tag_count") or 0) > 0
    has_editor_tag = bool(consistency_checks.get("detected_editing_software"))
    has_ai_tag = bool(consistency_checks.get("detected_ai_generators"))
    thumb_info = consistency_checks.get("thumbnail_check") or {}
    thumb_mismatch = bool(thumb_info.get("present") and not thumb_info.get("consistent", True))

    subsampling = _parse_jpeg_chroma_subsampling(raw_bytes)
    luma_q_mean: float | None = None
    chroma_q_mean: float | None = None
    estimated_q: int | None = None
    non_standard_q = False

    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            qtables = getattr(im, "quantization", None)
            if qtables and 0 in qtables:
                lq = list(qtables[0])
                luma_q_mean = round(float(np.mean(lq[:16])), 3)
                if luma_q_mean <= 1.05:
                    estimated_q = 100
                elif luma_q_mean < 50.0:
                    estimated_q = int(round(max(1, min(99, 100.0 - luma_q_mean * 1.4))))
                else:
                    estimated_q = int(round(max(1, 5000.0 / (luma_q_mean * 2.0))))
                if len(lq) >= 8 and lq[0] > lq[1] * 2.2:
                    non_standard_q = True
            if qtables and 1 in qtables:
                chroma_q_mean = round(float(np.mean(list(qtables[1])[:16])), 3)
    except Exception:  # noqa: BLE001
        pass

    # Compute unnormalized evidence scores for the 3 provenance profiles
    s_camera = 0.15
    s_social = 0.15
    s_edited = 0.15
    reasons: list[str] = []

    if has_ai_tag or has_editor_tag or thumb_mismatch or non_standard_q:
        s_edited += 0.75
        if has_editor_tag:
            ed_str = ", ".join(consistency_checks["detected_editing_software"])
            reasons.append(f"Editing software tag present ({ed_str}).")
        if has_ai_tag:
            ai_str = ", ".join(consistency_checks["detected_ai_generators"])
            reasons.append(f"Generative AI metadata present ({ai_str}).")
        if thumb_mismatch:
            reasons.append(
                "EXIF thumbnail differs from main image (indicative of post-capture edit)."
            )
        if non_standard_q:
            reasons.append("Non-standard JPEG quantization table structure.")

    if img_format == "PNG" and not has_camera_exif:
        s_edited += 0.55
        reasons.append(
            "Lossless PNG container without camera EXIF (typical of screenshot or editor export)."
        )

    if img_format == "JPEG":
        if has_camera_exif and not has_editor_tag and not thumb_mismatch:
            s_camera += 0.65
            reasons.append(
                f"Camera EXIF Make/Model present ({metadata_info.get('camera_make')} "
                f"{metadata_info.get('camera_model')})."
            )
        if (
            estimated_q is not None
            and estimated_q >= 90
            and subsampling in ("4:4:4", "4:2:2")
            and not has_editor_tag
            and not thumb_mismatch
        ):
            s_camera += 0.45
            reasons.append(
                f"High-fidelity JPEG (Q~{estimated_q}, chroma {subsampling}) "
                "consistent with camera original."
            )
        if (
            not has_any_exif
            and subsampling == "4:2:0"
            and estimated_q is not None
            and 45 <= estimated_q <= 85
        ):
            s_social += 0.78
            reasons.append(
                f"Stripped EXIF + 4:2:0 chroma subsampling + medium JPEG quality (Q~{estimated_q}, "
                f"long edge {long_edge}px) matches social/messaging re-encode."
            )
        elif (
            not has_camera_exif
            and not has_editor_tag
            and estimated_q is not None
            and estimated_q >= 88
            and subsampling == "4:4:4"
        ):
            s_edited += 0.45
            reasons.append(
                f"High-Q 4:4:4 JPEG (Q~{estimated_q}) with stripped camera EXIF "
                "matches editor export."
            )

    total = s_camera + s_social + s_edited
    probs = {
        "camera_original": round(s_camera / total, 4),
        "social_messaging_reencode": round(s_social / total, 4),
        "editing_software_resave": round(s_edited / total, 4),
    }
    predicted = max(probs, key=lambda k: probs[k])

    return {
        "predicted_source": predicted,
        "probabilities": probs,
        "format": img_format,
        "chroma_subsampling": subsampling,
        "estimated_jpeg_quality": estimated_q,
        "luma_q_mean": luma_q_mean,
        "chroma_q_mean": chroma_q_mean,
        "long_edge_px": long_edge,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 5. Unified Provenance & Attribution Entry Point
# ---------------------------------------------------------------------------


def analyze_provenance(
    working_path: str | Path,
    *,
    locker: ForensicLocker | None = None,
    artifact_dir: Path | None = None,
) -> ProvenanceAnalysisResult:
    """Run metadata consistency checks, C2PA verification, and compression source attribution on
    `working_path`."""
    p = Path(working_path)
    if locker is not None:
        locker.assert_is_working_copy(p)

    raw_bytes = p.read_bytes()
    meta, checks, timeline, artifacts = extract_and_verify_metadata(
        raw_bytes, filename=p.name, artifact_dir=artifact_dir
    )
    c2pa_info = verify_c2pa_credentials(raw_bytes)
    comp_info = attribute_compression_source(raw_bytes, meta, checks)

    why: list[str] = list(checks["anomalies"])
    for r in comp_info["reasons"]:
        if r not in why:
            why.append(r)

    # Compute overall provenance anomaly score
    anom_score = 0.0
    if checks["detected_ai_generators"]:
        anom_score = max(anom_score, 0.88)
    if not checks["timestamp_chronology_ok"]:
        anom_score = max(anom_score, 0.78)
    if not checks["gps_plausible"]:
        anom_score = max(anom_score, 0.75)
    if checks["thumbnail_check"].get("present") and not checks["thumbnail_check"].get("consistent"):
        anom_score = max(anom_score, 0.85)
    if not checks["camera_container_consistent"]:
        anom_score = max(anom_score, 0.72)
    if checks["detected_editing_software"]:
        anom_score = max(anom_score, 0.70)

    if c2pa_info["present"]:
        c_status = c2pa_info["status"]
        if c_status in ("tampered_c2pa_hash_mismatch", "invalid_c2pa_signature"):
            anom_score = max(anom_score, 0.92)
            why.insert(
                0,
                f"C2PA Content Credentials verification FAILED ({c_status}): asset payload was "
                "modified after the cryptographic manifest was signed.",
            )
        elif c_status == "valid_c2pa_manifest":
            dst = str(c2pa_info.get("digital_source_type") or "")
            if "trainedAlgorithmicMedia" in dst or "algorithmic" in dst.lower():
                anom_score = max(anom_score, 0.88)
                why.insert(
                    0,
                    f"Valid C2PA Content Credentials declare algorithmic/AI origin ({dst}).",
                )
            else:
                why.insert(
                    0,
                    f"Valid C2PA Content Credentials verified "
                    f"(signer={c2pa_info.get('signer_id')}, "
                    f"generator={c2pa_info.get('claim_generator')}).",
                )

    if comp_info["predicted_source"] == "social_messaging_reencode" and anom_score < 0.45:
        anom_score = max(anom_score, 0.48)

    anom_score = round(anom_score, 4)
    if anom_score >= 0.65:
        finding = "consistent_with_manipulation_or_editing"
        conf = round(min(0.96, 0.68 + 0.28 * ((anom_score - 0.65) / 0.35)), 3)
        stmt = (
            f"Provenance and metadata indicators are consistent with post-capture editing, "
            f"synthetic generation, or broken content credentials (anomaly score {anom_score:.2f}, "
            f"attributed source: {comp_info['predicted_source']})."
        )
    elif anom_score >= 0.42:
        finding = "anomalies_detected_verify"
        conf = round(0.55 + 0.15 * ((anom_score - 0.42) / 0.23), 3)
        stmt = (
            f"Provenance analysis indicates re-encoding or missing origin metadata "
            f"(attributed source: {comp_info['predicted_source']}, score {anom_score:.2f}). "
            "Original capture device cannot be confirmed from file headers alone."
        )
    else:
        finding = "consistent_with_camera_or_authentic_origin"
        conf = round(0.75 + 0.15 * (1.0 - anom_score), 3)
        stmt = (
            f"Metadata chronology, C2PA status, and compression profile are consistent with "
            f"{comp_info['predicted_source']} origin (anomaly score {anom_score:.2f}). "
            "Note that EXIF fields can be forged unless bound by a valid C2PA signature."
        )

    return ProvenanceAnalysisResult(
        modality="image" if meta["width"] > 0 else "document",
        finding=finding,
        confidence=conf,
        anomaly_score=anom_score,
        source_attribution=str(comp_info["predicted_source"]),
        attribution_probabilities=comp_info["probabilities"],
        statement=stmt,
        why=why,
        metadata=meta,
        consistency_checks=checks,
        c2pa=c2pa_info,
        compression_profile=comp_info,
        timeline_events=timeline,
        artifacts=artifacts,
        limitations=[
            (
                "Unsigned EXIF/XMP tags are user-editable and can be stripped by messaging apps "
                "or forged with tools like exiftool; only cryptographic C2PA manifests or external "
                "custody logs bind content to a signer."
            ),
            (
                "Compression-fingerprint attribution identifies the last encoding stage (e.g., "
                "WhatsApp re-encode) and cannot recover pre-reencode camera headers."
            ),
        ],
    )
