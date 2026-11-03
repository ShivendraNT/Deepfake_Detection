"""M3 tests: Image (ELA, double-JPEG, copy-move, noise-residual + heatmaps), Video
(duplicated/dropped frames), and Audio (splice/discontinuity + spectrogram) detectors."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from satyapan.forensics.locker import ForensicLocker
from satyapan.forensics.tamper import (
    analyze_audio_tampering,
    analyze_image_tampering,
    analyze_video_tampering,
    copy_move_analysis,
    double_jpeg_analysis,
    ela_analysis,
    noise_residual_analysis,
)


def _base_natural_image(seed: int = 42, size: int = 256) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    base = 90.0 + 60.0 * np.sin(2.0 * np.pi * 1.5 * xx) + 40.0 * np.cos(2.0 * np.pi * 1.2 * yy)
    noise = rng.normal(0.0, 3.2, (size, size, 3)).astype(np.float32)
    rgb = np.stack([base, base * 0.95, base * 1.05], axis=-1) + noise
    return np.clip(rgb, 10, 245).astype(np.uint8)


def test_ela_and_noise_residual_detect_spliced_patch() -> None:
    rgb = _base_natural_image(seed=10)
    # Compress background at Q72
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=72)
    buf.seek(0)
    bg_jpeg = np.asarray(Image.open(buf).convert("RGB"), dtype=np.uint8).copy()

    clean_ela, _ = ela_analysis(bg_jpeg)
    clean_nr, _ = noise_residual_analysis(bg_jpeg)
    assert clean_ela["score"] < 0.40
    assert clean_nr["score"] < 0.40

    # Splice a high-frequency noisy foreign patch into [64:128, 64:128] without Q72 compression
    rng = np.random.default_rng(99)
    spliced = bg_jpeg.copy()
    patch = rng.uniform(20, 235, (64, 64, 3)).astype(np.uint8)
    spliced[64:128, 64:128] = patch

    sp_ela, ela_heat = ela_analysis(spliced)
    sp_nr, nr_heat = noise_residual_analysis(spliced)
    assert sp_ela["score"] > 0.65
    assert sp_nr["score"] > 0.65
    assert ela_heat.shape == (16, 16)
    assert nr_heat.shape == (16, 16)


def test_copy_move_detects_cloned_region() -> None:
    rgb = _base_natural_image(seed=21)
    clean_cm, _ = copy_move_analysis(rgb)
    assert clean_cm["score"] == 0.0

    # Add a distinct textured object at (32:80, 32:80) and clone it to (144:192, 144:192)
    rng = np.random.default_rng(77)
    forged = rgb.copy()
    obj = rng.integers(30, 225, (48, 48, 3), dtype=np.uint8)
    forged[32:80, 32:80] = obj
    forged[144:192, 144:192] = obj

    cm_info, cm_mask = copy_move_analysis(forged)
    assert cm_info["score"] >= 0.70
    assert cm_info["cloned_block_pairs"] >= 10
    assert cm_info["dominant_shift_px"] == [112, 112]
    assert float(np.max(cm_mask)) == 1.0


def test_double_jpeg_and_full_image_tampering_pipeline(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m3_img", collector="examiner_m3")
    rgb = _base_natural_image(seed=33)
    # Create spliced + copy-moved image
    rng = np.random.default_rng(55)
    obj = rng.integers(40, 220, (48, 48, 3), dtype=np.uint8)
    rgb[24:72, 24:72] = obj
    rgb[136:184, 136:184] = obj

    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=92)
    raw_bytes = buf.getvalue()

    djpeg = double_jpeg_analysis(raw_bytes, rgb)
    assert djpeg["q_table_present"] is True
    assert djpeg["format"] == "JPEG"

    item = locker.intake_bytes(raw_bytes, "tampered_receipt.jpg", source_type="image")
    with pytest.raises(PermissionError, match="Forensic violation"):
        analyze_image_tampering(item.stored_path, locker=locker)

    wp = locker.checkout_working_copy(item.evidence_id)
    art_dir = locker.artifacts_dir / item.evidence_id
    res = analyze_image_tampering(wp, locker=locker, artifact_dir=art_dir)
    assert res.finding == "consistent_with_tampering"
    assert res.tamper_probability >= 0.65
    for k in ("ela_heatmap", "copy_move_heatmap", "noise_residual_heatmap", "tamper_composite"):
        assert Path(res.artifacts[k]).exists()


def test_video_tampering_detects_duplicated_and_dropped_frames(tmp_path: Path) -> None:
    import av

    locker = ForensicLocker(tmp_path / "case_m3_vid", collector="examiner_m3")
    mp4_path = tmp_path / "edited_video.mp4"
    container = av.open(str(mp4_path), mode="w")
    stream = container.add_stream("mpeg4", rate=15)
    stream.width = 160
    stream.height = 120
    stream.pix_fmt = "yuv420p"
    stream.bit_rate = 800_000

    frames_rgb: list[np.ndarray] = []
    yy, xx = np.mgrid[0:120, 0:160].astype(np.float32)
    for i in range(30):
        # Smooth moving gradient bar
        shift = i * 3.0
        val = 127.0 + 90.0 * np.sin((xx + shift) * 0.08) + 40.0 * np.cos((yy + shift) * 0.08)
        rgb = np.clip(np.stack([val, val * 0.9, val * 1.05], axis=-1), 0, 255).astype(np.uint8)
        frames_rgb.append(rgb)

    # Inject 4 duplicated frames at index 10..13 and a huge splice jump at index 22
    for idx in (10, 11, 12, 13):
        frames_rgb[idx] = frames_rgb[9].copy()
    frames_rgb[22] = (255 - frames_rgb[21]).copy()

    for rgb in frames_rgb:
        vf = av.VideoFrame.from_ndarray(rgb, format="rgb24")
        for pkt in stream.encode(vf):
            container.mux(pkt)
    for pkt in stream.encode():
        container.mux(pkt)
    container.close()

    item = locker.intake(mp4_path, source_type="video", media_type="video/mp4")
    wp = locker.checkout_working_copy(item.evidence_id)
    art_dir = locker.artifacts_dir / item.evidence_id
    res = analyze_video_tampering(wp, locker=locker, artifact_dir=art_dir)
    assert res.finding == "consistent_with_tampering"
    assert (
        res.subchecks["duplicated_frame_count"] >= 2 or res.subchecks["dropped_frame_spikes"] >= 1
    )
    assert Path(res.artifacts["video_tamper_timeline"]).exists()


def test_audio_tampering_detects_splice_and_noise_floor_shift(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m3_aud", collector="examiner_m3")
    sr = 16000
    rng = np.random.default_rng(123)

    # First 2 seconds: quiet room speech-like signal (noise floor sigma=0.002)
    t1 = np.linspace(0, 2.0, 2 * sr, endpoint=False)
    seg1 = 0.15 * np.sin(2.0 * np.pi * 210.0 * t1) + rng.normal(0.0, 0.002, len(t1))

    # Next 2 seconds: spliced noisy room segment (noise floor sigma=0.08 + abrupt cut transient)
    t2 = np.linspace(0, 2.0, 2 * sr, endpoint=False)
    seg2 = 0.25 * np.sin(2.0 * np.pi * 330.0 * t2) + rng.normal(0.0, 0.08, len(t2))
    seg2[0] = 0.95  # hard sample cut discontinuity

    joined = np.clip(np.concatenate([seg1, seg2]), -0.99, 0.99)
    pcm = (joined * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    item = locker.intake_bytes(buf.getvalue(), "spliced_call.wav", source_type="audio")
    wp = locker.checkout_working_copy(item.evidence_id)
    art_dir = locker.artifacts_dir / item.evidence_id
    res = analyze_audio_tampering(wp, locker=locker, artifact_dir=art_dir)
    assert res.finding == "consistent_with_tampering"
    assert res.tamper_probability >= 0.65
    assert Path(res.artifacts["audio_splice_spectrogram"]).exists()
