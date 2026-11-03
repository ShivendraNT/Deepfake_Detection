"""M2 tests: Deepfake & synthetic media detection engine (image, video frame+aggregate, audio)."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from satyapan.forensics.deepfake import (
    analyze_audio_deepfake,
    analyze_image_deepfake,
    analyze_video_deepfake,
    extract_whole_image_features,
    score_whole_image,
)
from satyapan.forensics.locker import ForensicLocker


def _make_camera_rgb(seed: int = 7, size: int = 256) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    lum = 45.0 + 150.0 * (0.5 * xx + 0.5 * yy) + 20.0 * np.sin(2.0 * np.pi * xx)
    tex = rng.normal(0.0, 3.8, (size, size)).astype(np.float32)
    shot = rng.normal(0.0, 1.0, (size, size)).astype(np.float32) * (0.28 * np.sqrt(lum))
    rgb = np.stack([lum + tex + shot, lum + tex + 0.9 * shot, lum * 0.95 + tex + shot], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _make_synthetic_gan_rgb(seed: int = 11, size: int = 256) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    base = 120.0 + 60.0 * np.cos(4.0 * np.pi * xx) * np.sin(4.0 * np.pi * yy)
    grid2 = ((-1.0) ** (np.arange(size)[:, None] + np.arange(size)[None, :])).astype(np.float32)
    r = base + 3.8 * grid2 + rng.normal(0.0, 1.0, (size, size))
    g = base - 3.2 * grid2 + rng.normal(0.0, 1.0, (size, size))
    b = base + 3.5 * grid2 + rng.normal(0.0, 1.0, (size, size))
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def test_whole_image_features_and_scoring_separate_camera_from_synthetic() -> None:
    cam = _make_camera_rgb()
    syn = _make_synthetic_gan_rgb()

    f_cam = extract_whole_image_features(cam, clip_scorer=None)
    f_syn = extract_whole_image_features(syn, clip_scorer=None)
    assert f_syn["checkerboard_index"] > f_cam["checkerboard_index"]
    assert f_syn["cfa_decorrelation"] > f_cam["cfa_decorrelation"]

    s_cam = score_whole_image(cam)
    s_syn = score_whole_image(syn)
    assert s_syn["probability"] > s_cam["probability"]
    assert s_syn["label"] == "likely_synthetic"
    assert s_cam["label"] == "no_signs"


def test_image_deepfake_enforces_working_copy_and_non_absolutist_language(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m2_img", collector="examiner_m2")
    syn = _make_synthetic_gan_rgb()
    buf = io.BytesIO()
    Image.fromarray(syn).save(buf, format="PNG")
    item = locker.intake_bytes(buf.getvalue(), "synth_scene.png", source_type="image")

    # Running directly on sealed original must raise PermissionError
    with pytest.raises(PermissionError, match="Forensic violation"):
        analyze_image_deepfake(item.stored_path, locker=locker, use_heavy_models=False)

    work_path = locker.checkout_working_copy(item.evidence_id)
    art_dir = locker.artifacts_dir / item.evidence_id
    res = analyze_image_deepfake(
        work_path, locker=locker, artifact_dir=art_dir, use_heavy_models=False
    )
    assert res.modality == "image"
    assert res.finding == "consistent_with_synthetic"
    assert "consistent with" in res.statement.lower()
    assert 0.0 <= res.confidence <= 1.0
    assert Path(res.artifacts["spectrum_heatmap"]).exists()
    assert len(res.limitations) >= 2


def test_audio_deepfake_short_abstain_and_voiced_analysis(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m2_aud", collector="examiner_m2")

    # 1. Short audio (<3s) must abstain honestly
    sr = 16000
    t_short = np.linspace(0, 1.2, int(1.2 * sr), endpoint=False)
    pcm_short = (0.4 * np.sin(2.0 * np.pi * 220.0 * t_short) * 32767).astype(np.int16)
    buf_short = io.BytesIO()
    with wave.open(buf_short, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_short.tobytes())
    it_short = locker.intake_bytes(buf_short.getvalue(), "short.wav", source_type="audio")
    wp_short = locker.checkout_working_copy(it_short.evidence_id)
    res_short = analyze_audio_deepfake(wp_short, locker=locker, use_heavy_models=False)
    assert res_short.finding == "inconclusive_abstain"
    assert "abstained" in res_short.statement.lower()

    # 2. 5-second synthetic harmonic signal
    t_long = np.linspace(0, 5.2, int(5.2 * sr), endpoint=False)
    sig = 0.5 * np.sin(2.0 * np.pi * 180.0 * t_long) + 0.25 * np.sin(2.0 * np.pi * 360.0 * t_long)
    pcm_long = (sig * 32767).astype(np.int16)
    buf_long = io.BytesIO()
    with wave.open(buf_long, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_long.tobytes())
    it_long = locker.intake_bytes(buf_long.getvalue(), "synth_tone.wav", source_type="audio")
    wp_long = locker.checkout_working_copy(it_long.evidence_id)
    res_long = analyze_audio_deepfake(wp_long, locker=locker, use_heavy_models=False)
    assert res_long.modality == "audio"
    assert len(res_long.window_scores) >= 1
    assert (
        "consistent with" in res_long.statement.lower() or "anomalies" in res_long.statement.lower()
    )


def test_video_deepfake_frame_and_aggregate_scores(tmp_path: Path) -> None:
    import av

    locker = ForensicLocker(tmp_path / "case_m2_vid", collector="examiner_m2")
    mp4_path = tmp_path / "synth_clip.mp4"
    container = av.open(str(mp4_path), mode="w")
    stream = container.add_stream("mpeg4", rate=10)
    stream.width = 256
    stream.height = 256
    stream.pix_fmt = "yuv420p"
    for i in range(15):
        rgb = _make_synthetic_gan_rgb(seed=100 + i, size=256)
        frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    item = locker.intake(mp4_path, source_type="video", media_type="video/mp4")
    wp = locker.checkout_working_copy(item.evidence_id)
    art_dir = locker.artifacts_dir / item.evidence_id
    res = analyze_video_deepfake(
        wp, locker=locker, artifact_dir=art_dir, use_heavy_models=False, max_frames=6
    )
    assert res.modality == "video"
    assert len(res.frame_scores) == 6
    assert res.subchecks["frames_analyzed"] == 6
    assert "p90_frame_score" in res.subchecks
    assert Path(res.artifacts["frame_trajectory"]).exists()
