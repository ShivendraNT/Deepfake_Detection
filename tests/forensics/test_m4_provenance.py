"""M4 tests: EXIF/XMP/PNG metadata extraction & consistency checks, embedded thumbnail mismatch,
C2PA JUMBF Content Credentials verification, and 3-class compression source attribution."""

from __future__ import annotations

import io
import struct
from pathlib import Path

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image, PngImagePlugin

from satyapan.forensics.locker import ForensicLocker
from satyapan.forensics.provenance import (
    analyze_provenance,
    embed_c2pa_jumbf_manifest,
    extract_and_verify_metadata,
    verify_c2pa_credentials,
)


def _make_rgb(seed: int = 1, w: int = 320, h: int = 240) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = 100.0 + 60.0 * np.sin(xx * 0.04) + rng.normal(0, 2, (h, w))
    g = 110.0 + 50.0 * np.cos(yy * 0.04) + rng.normal(0, 2, (h, w))
    b = 90.0 + 40.0 * np.sin((xx + yy) * 0.03) + rng.normal(0, 2, (h, w))
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def _build_jpeg_with_exif_and_thumb(
    main_rgb: np.ndarray,
    *,
    make: str = "Canon",
    model: str = "Canon EOS R6",
    software: str = "",
    dt_orig: str = "2026:10:15 10:30:00",
    dt_mod: str = "2026:10:15 10:30:00",
    gps_null_island: bool = False,
    thumb_rgb: np.ndarray | None = None,
    quality: int = 95,
    subsampling: int = 0,
) -> bytes:
    im = Image.fromarray(main_rgb)
    exif = im.getexif()
    if make:
        exif[0x010F] = make  # Make
    if model:
        exif[0x0110] = model  # Model
    if software:
        exif[0x0131] = software  # Software
    if dt_mod:
        exif[0x0132] = dt_mod  # DateTime
    if dt_orig:
        exif[0x9003] = dt_orig  # DateTimeOriginal
        exif[0x9004] = dt_orig  # DateTimeDigitized
    if gps_null_island:
        # GPS IFD 0x8825 pointing to (0, 0)
        exif[0x8825] = {
            1: "N",
            2: (0.0, 0.0, 0.0),
            3: "E",
            4: (0.0, 0.0, 0.0),
        }

    exif_bytes = exif.tobytes()
    if thumb_rgb is not None:
        t_buf = io.BytesIO()
        Image.fromarray(thumb_rgb).save(t_buf, format="JPEG", quality=75)
        # Append embedded thumbnail SOI..EOI inside APP1 payload
        exif_bytes = exif_bytes + b"\x00\x00" + t_buf.getvalue()

    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, subsampling=subsampling)
    raw = buf.getvalue()
    # Inject custom APP1 segment right after SOI
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif_bytes) + 2) + exif_bytes
    return raw[:2] + app1 + raw[2:]


def test_metadata_consistency_catches_chronology_editor_ai_and_thumbnail_mismatch(
    tmp_path: Path,
) -> None:
    rgb = _make_rgb(seed=5)
    # Inverted thumbnail (completely different scene from main_rgb) + inverted dates + Photoshop tag
    wrong_thumb = 255 - rgb
    bad_jpeg = _build_jpeg_with_exif_and_thumb(
        rgb,
        software="Adobe Photoshop 25.0",
        dt_orig="2026:10:20 14:00:00",
        dt_mod="2026:10:18 09:00:00",  # ModifyDate earlier than DateTimeOriginal!
        gps_null_island=True,
        thumb_rgb=wrong_thumb,
    )
    meta, checks, timeline, arts = extract_and_verify_metadata(
        bad_jpeg, filename="edited.jpg", artifact_dir=tmp_path
    )
    assert checks["timestamp_chronology_ok"] is False
    assert "photoshop" in checks["detected_editing_software"]
    assert checks["gps_plausible"] is False
    assert checks["thumbnail_check"]["present"] is True
    assert checks["thumbnail_check"]["consistent"] is False
    assert Path(arts["thumbnail_comparison"]).exists()
    assert len(timeline) >= 2


def test_png_ai_parameters_detected() -> None:
    rgb = _make_rgb(seed=9, w=256, h=256)
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text(
        "parameters",
        "portrait of CEO, Steps: 30, Sampler: Euler a, CFG scale: 7.0, Model: sd_xl_base_1.0",
    )
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG", pnginfo=png_info)
    _, checks, _, _ = extract_and_verify_metadata(buf.getvalue(), filename="sd_output.png")
    assert len(checks["detected_ai_generators"]) >= 1


def test_c2pa_jumbf_signing_verification_and_tamper_detection() -> None:
    rgb = _make_rgb(seed=12)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=92)
    orig_jpeg = buf.getvalue()

    # 1. Unsigned image has no C2PA manifest
    no_c2pa = verify_c2pa_credentials(orig_jpeg)
    assert no_c2pa["present"] is False
    assert no_c2pa["status"] == "no_c2pa_manifest"

    # 2. Embed valid signed C2PA JUMBF manifest
    priv = Ed25519PrivateKey.generate()
    signed_jpeg = embed_c2pa_jumbf_manifest(
        orig_jpeg,
        {
            "claim_generator": "Sony Alpha C2PA Camera/1.2",
            "title": "Field Evidence Photo",
            "actions": [{"action": "c2pa.created"}],
        },
        priv,
        signer_id="sony-camera-cert",
    )
    valid_res = verify_c2pa_credentials(signed_jpeg)
    assert valid_res["present"] is True
    assert valid_res["status"] == "valid_c2pa_manifest"
    assert valid_res["signature_valid"] is True
    assert valid_res["hard_binding_valid"] is True

    # 3. Flip one byte in the JPEG scan data after signing -> must fail hard-binding hash check!
    tampered_jpeg = bytearray(signed_jpeg)
    tampered_jpeg[-20] ^= 0x01
    bad_res = verify_c2pa_credentials(bytes(tampered_jpeg))
    assert bad_res["present"] is True
    assert bad_res["status"] == "tampered_c2pa_hash_mismatch"
    assert bad_res["hard_binding_valid"] is False


def test_compression_source_attribution_three_classes(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m4_attr", collector="examiner_m4")
    rgb = _make_rgb(seed=22, w=640, h=480)

    # Class 1: Camera original (Make/Model + Q95 + 4:4:4 + matching thumbnail)
    cam_bytes = _build_jpeg_with_exif_and_thumb(
        rgb, make="Nikon", model="Nikon Z8", thumb_rgb=rgb, quality=95, subsampling=0
    )
    it_cam = locker.intake_bytes(cam_bytes, "DSC_001.JPG", source_type="image")
    res_cam = analyze_provenance(locker.checkout_working_copy(it_cam.evidence_id), locker=locker)
    assert res_cam.source_attribution == "camera_original"
    assert res_cam.finding == "consistent_with_camera_or_authentic_origin"

    # Class 2: WhatsApp / social messaging re-encode (stripped EXIF + Q70 + 4:2:0 subsampling)
    soc_buf = io.BytesIO()
    Image.fromarray(rgb).save(soc_buf, format="JPEG", quality=70, subsampling=2)
    it_soc = locker.intake_bytes(soc_buf.getvalue(), "IMG-20261024-WA0001.jpg", source_type="image")
    res_soc = analyze_provenance(locker.checkout_working_copy(it_soc.evidence_id), locker=locker)
    assert res_soc.source_attribution == "social_messaging_reencode"

    # Class 3: Editing software re-save (GIMP tag in EXIF)
    ed_bytes = _build_jpeg_with_exif_and_thumb(
        rgb, make="", model="", software="GIMP 2.10.36", quality=90, subsampling=0
    )
    it_ed = locker.intake_bytes(ed_bytes, "edited_export.jpg", source_type="image")
    res_ed = analyze_provenance(locker.checkout_working_copy(it_ed.evidence_id), locker=locker)
    assert res_ed.source_attribution == "editing_software_resave"
    assert res_ed.finding == "consistent_with_manipulation_or_editing"
