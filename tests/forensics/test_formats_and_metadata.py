"""File identification, JPEG/PNG structure parsing and metadata-based findings."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from satyapan.forensics.engine import analyze_bytes
from satyapan.forensics.filetype import extension_mismatch, hashes, sniff
from satyapan.forensics.image.containers import (
    describe_trailing,
    estimate_quality,
    parse_jpeg,
    parse_png,
)
from satyapan.forensics.image.meta_read import parse_xmp
from satyapan.forensics.models import Hypothesis, MediaKind, Strength
from tests.forensics.conftest import exif_with_thumbnail, jpeg, png, textured


def codes(analysis, technique: str | None = None) -> set[str]:
    return {f.code for t in analysis.techniques for f in t.findings
            if technique is None or t.id == technique}  # fmt: skip


def test_hashes_known_values() -> None:
    h = hashes(b"abc")
    assert h.md5 == "900150983cd24fb0d6963f7d28e17f72"
    assert h.sha1 == "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert h.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert h.size_bytes == 3


def test_sniff_by_content_not_name() -> None:
    arr = textured(64, 48)
    assert sniff(jpeg(arr)).format == "jpeg"
    assert sniff(png(arr)).format == "png"
    assert sniff(b"RIFF\x00\x00\x00\x00WAVEfmt ").kind == MediaKind.AUDIO
    assert sniff(b"\x00\x00\x00\x18ftypisom\x00\x00").kind == MediaKind.VIDEO
    assert sniff(b"\x00\x00\x00\x18ftypM4A \x00\x00").kind == MediaKind.AUDIO
    assert sniff(b"\x00\x00\x00\x18ftypheic\x00\x00").format == "heic"
    assert sniff(b"OggS" + b"\x00" * 24 + b"OpusHead").format == "opus"
    assert sniff(b"ID3\x04\x00").format == "mp3"
    assert sniff(b"%PDF-1.7").kind == MediaKind.DOCUMENT
    assert sniff(b"MZ\x90\x00").format == "exe"
    assert sniff(b"hello world").format == "unknown"
    assert sniff(b"").format == "unknown"


def test_extension_mismatch() -> None:
    sn = sniff(jpeg(textured(32, 32)))
    assert extension_mismatch(sn, "photo.png") is True
    assert extension_mismatch(sn, "photo.JPG") is False
    assert extension_mismatch(sn, "no_extension") is False


def test_jpeg_quality_estimate_matches_encoder() -> None:
    for q in (55, 75, 90):
        info = parse_jpeg(jpeg(textured(128, 96), q=q))
        est, exact, _ = estimate_quality(info)
        assert exact and est == q
        assert info.frame == "baseline" and info.subsampling == "4:2:0"
        assert info.huffman_standard is True
        assert info.trailing_bytes == 0


def test_jpeg_trailing_archive_is_flagged(stub_models, tmp_path: Path) -> None:
    data = jpeg(textured(200, 150)) + b"PK\x03\x04" + b"secret" * 200
    info = parse_jpeg(data)
    assert info.trailing_bytes > 1000
    assert describe_trailing(info.trailing_head) == "ZIP archive"
    a, _ = analyze_bytes(data, "holiday.jpg", tmp_path, models=stub_models)
    f = [f for t in a.techniques for f in t.findings if f.code == "TRAILING_DATA"]
    assert f and f[0].hypothesis == Hypothesis.MANIPULATED and f[0].strength >= Strength.MODERATE


def test_png_text_chunks_and_a1111_signature(stub_models, tmp_path: Path) -> None:
    meta = PngInfo()
    meta.add_text("parameters", "portrait of an officer\nSteps: 20, Sampler: Euler a, CFG scale: 7, "
                  "Seed: 1234, Size: 512x512, Model hash: 6ce0161689, Model: v1-5-pruned")  # fmt: skip
    buf = io.BytesIO()
    Image.fromarray(textured(320, 240)).save(buf, format="PNG", pnginfo=meta)
    data = buf.getvalue()
    info = parse_png(data)
    assert "parameters" in info.text and info.width == 320
    a, _ = analyze_bytes(data, "officer.png", tmp_path, models=stub_models)
    gen = [f for t in a.techniques for f in t.findings if f.code == "GENERATOR_SIGNATURE"]
    assert gen and gen[0].strength == Strength.VERY_STRONG
    assert a.verdict.label.value == "SYNTHETIC"
    assert "Stable Diffusion" in (a.provenance.generator or "")


def test_exif_camera_editor_dates_gps(stub_models, tmp_path: Path) -> None:
    img = Image.fromarray(textured(400, 300))
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif[0x0110] = "Canon EOS 80D"
    exif[0x0131] = "Adobe Photoshop 25.0 (Windows)"
    exif[0x0132] = "2026:10:21 18:44:00"
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = "2026:10:19 09:12:05"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (28.0, 36.0, 50.0)
    gps[3], gps[4] = "E", (77.0, 12.0, 30.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, exif=exif)
    a, _ = analyze_bytes(buf.getvalue(), "IMG_4821.JPG", tmp_path, models=stub_models)
    c = codes(a)
    assert {"CAMERA_IDENTIFIED", "EDITING_SOFTWARE", "MODIFIED_AFTER_CAPTURE", "GPS_LOCATION"} <= c
    assert a.provenance.gps and abs(a.provenance.gps["lat"] - 28.6139) < 0.01
    assert a.provenance.software == "Adobe Photoshop"
    # editing software and a later save are weak alone: not a manipulation verdict by themselves
    assert a.verdict.label.value in ("NO_INDICATORS", "SUSPICIOUS", "INCONCLUSIVE")


def test_xmp_digital_source_type_and_history() -> None:
    packet = """<x:xmpmeta><rdf:RDF><rdf:Description xmp:CreatorTool="Adobe Firefly"
      Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia">
      <xmpMM:History><rdf:Seq><rdf:li stEvt:action="created" stEvt:softwareAgent="Adobe Firefly"
      stEvt:when="2026-10-20T10:00:00"/><rdf:li stEvt:action="saved"
      stEvt:softwareAgent="Adobe Photoshop 25.0" stEvt:when="2026-10-20T10:05:00"/></rdf:Seq>
      </xmpMM:History></rdf:Description></rdf:RDF></x:xmpmeta>"""
    props, hist = parse_xmp(packet)
    assert props["xmp:CreatorTool"] == "Adobe Firefly"
    assert props["Iptc4xmpExt:DigitalSourceType"].endswith("trainedAlgorithmicMedia")
    assert [h["action"] for h in hist] == ["created", "saved"]


def test_digital_source_type_drives_synthetic_verdict(stub_models, tmp_path: Path) -> None:
    xmp = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description '
           b'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/'
           b'trainedAlgorithmicMedia"/></rdf:RDF></x:xmpmeta>')  # fmt: skip
    buf = io.BytesIO()
    Image.fromarray(textured(256, 256)).save(buf, format="JPEG", quality=90, xmp=xmp)
    a, _ = analyze_bytes(buf.getvalue(), "ai.jpg", tmp_path, models=stub_models)
    assert "DIGITAL_SOURCE_TYPE" in codes(a)
    assert a.verdict.label.value == "SYNTHETIC"


def test_platform_traces(stub_models, tmp_path: Path) -> None:
    a, _ = analyze_bytes(jpeg(textured(1600, 1200), q=80), "IMG-20261021-WA0011.jpg", tmp_path,
                         models=stub_models)  # fmt: skip
    plats = [f.observations.get("platform") for t in a.techniques for f in t.findings
             if f.code == "PLATFORM_TRACE"]  # fmt: skip
    assert "WhatsApp (mobile)" in plats
    assert a.provenance.platform == "WhatsApp (mobile)"


def _with_thumb(main: np.ndarray, thumb_src: np.ndarray) -> bytes:
    tb = io.BytesIO()
    Image.fromarray(thumb_src).resize((160, 120)).save(tb, format="JPEG", quality=85)
    buf = io.BytesIO()
    Image.fromarray(main).save(
        buf, format="JPEG", quality=92, exif=exif_with_thumbnail(tb.getvalue())
    )
    return buf.getvalue()


def test_exif_thumbnail_consistent_edited_and_cropped(stub_models, tmp_path: Path) -> None:
    original = textured(640, 480, seed=1)
    a, _ = analyze_bytes(_with_thumb(original, original), "DSC_0001.JPG", tmp_path / "a",
                         models=stub_models)  # fmt: skip
    assert "THUMBNAIL_CONSISTENT" in codes(a, "image.thumbnail")
    edited = original.copy()
    edited[60:420, 80:560] = textured(480, 360, seed=9)
    b, _ = analyze_bytes(_with_thumb(edited, original), "DSC_0002.JPG", tmp_path / "b",
                         models=stub_models)  # fmt: skip
    f = [f for t in b.techniques for f in t.findings if f.code == "THUMBNAIL_CONTENT_MISMATCH"]
    assert f and f[0].hypothesis == Hypothesis.MANIPULATED and f[0].strength >= Strength.MODERATE
    cropped = original[:, 80:560]
    c, _ = analyze_bytes(_with_thumb(cropped, original), "DSC_0003.JPG", tmp_path / "c",
                         models=stub_models)  # fmt: skip
    assert "THUMBNAIL_ASPECT_MISMATCH" in codes(c, "image.thumbnail")


def test_no_thumbnail_skips_cleanly(stub_models, tmp_path: Path) -> None:
    a, _ = analyze_bytes(jpeg(textured(320, 240)), "x.jpg", tmp_path, models=stub_models)
    th = next(r for r in a.techniques if r.id == "image.thumbnail")
    assert th.status.value == "skipped"


def test_c2pa_ai_declaration_and_tampering(stub_models, tmp_path: Path) -> None:
    import importlib.util
    import sys

    import pytest

    if importlib.util.find_spec("c2pa") is None or importlib.util.find_spec("cryptography") is None:
        pytest.skip("c2pa-python / cryptography not installed")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from build_demo_dataset import c2pa_sign

    (tmp_path / "in.png").write_bytes(png(textured(256, 256)))
    c2pa_sign(tmp_path / "in.png", tmp_path / "signed.png", tmp_path)
    signed = (tmp_path / "signed.png").read_bytes()
    a, _ = analyze_bytes(signed, "signed.png", tmp_path / "a", models=stub_models)
    f = {x.code: x for t in a.techniques for x in t.findings}
    assert f["C2PA_AI_GENERATED"].strength == Strength.VERY_STRONG
    assert "C2PA_INVALID" not in f and a.verdict.label.value == "SYNTHETIC"
    b, _ = analyze_bytes(
        signed + b"appended" * 8, "tampered.png", tmp_path / "b", models=stub_models
    )
    g = {x.code: x for t in b.techniques for x in t.findings}
    assert g["C2PA_INVALID"].hypothesis == Hypothesis.MANIPULATED
    assert g["C2PA_AI_GENERATED"].strength == Strength.STRONG


def test_heic_iphone_photo_is_analysed(stub_models, tmp_path: Path) -> None:
    import pytest

    heif = pytest.importorskip("pillow_heif")
    heif.register_heif_opener()
    buf = io.BytesIO()
    Image.fromarray(textured(400, 300)).save(buf, format="HEIF", quality=90)
    a, _ = analyze_bytes(buf.getvalue(), "IMG_0001.HEIC", tmp_path, models=stub_models)
    assert a.media.format == "heic" and a.media.width == 400
    assert not [t.id for t in a.techniques if t.status.value == "error"]
