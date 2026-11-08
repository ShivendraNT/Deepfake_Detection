"""Pixel and audio signal techniques on synthetic inputs with known answers."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from satyapan.forensics.audio import dsp
from satyapan.forensics.audio.speaker import fbank
from satyapan.forensics.engine import analyze_bytes
from satyapan.forensics.image import watermark as wm
from satyapan.forensics.image.pixel_techniques import (
    blocking_profile,
    copy_move_clusters,
    grid_scores,
)
from satyapan.forensics.models import Hypothesis, Strength
from tests.forensics.conftest import jpeg, png, textured, wav


def finding_codes(a) -> set[str]:
    return {f.code for t in a.techniques for f in t.findings}


# ------------------------------------------------------------------ copy-move
def test_copy_move_found_on_cloned_patch(stub_models, tmp_path: Path) -> None:
    img = textured(640, 480, seed=3)
    img[300:400, 420:540] = img[60:160, 80:200]
    a, _ = analyze_bytes(jpeg(img, 93), "cm.jpg", tmp_path, models=stub_models)
    f = [f for t in a.techniques for f in t.findings if f.code == "COPY_MOVE"]
    assert f and f[0].hypothesis == Hypothesis.MANIPULATED and f[0].strength >= Strength.MODERATE
    assert len(f[0].regions) == 2  # source and copy boxes
    assert a.verdict.label.value in ("MANIPULATED", "SUSPICIOUS")


def test_copy_move_quiet_on_clean_image(stub_models, tmp_path: Path) -> None:
    a, _ = analyze_bytes(
        jpeg(textured(640, 480, seed=4), 93), "clean.jpg", tmp_path, models=stub_models
    )
    assert "COPY_MOVE" not in finding_codes(a)


def test_copy_move_clusters_report_transform() -> None:
    import cv2

    img = textured(500, 400, seed=5)
    img[250:330, 300:400] = img[40:120, 50:150]
    cl = copy_move_clusters(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
    assert cl and cl[0]["pairs"] >= 12
    assert abs(cl[0]["shift"] - np.hypot(250, 210)) < 25


# ------------------------------------------------------------------ JPEG grid
def test_jpeg_grid_aligned_vs_cropped() -> None:
    img = textured(512, 384, seed=6)
    once = np.asarray(Image.open(io.BytesIO(jpeg(img, 60))).convert("RGB"), dtype=np.float32)
    gray = once @ np.array([0.299, 0.587, 0.114], np.float32)
    p = blocking_profile(gray)
    assert (p["phase_h"], p["phase_v"]) == (7, 7)
    shifted = gray[3:, 5:]
    p2 = blocking_profile(shifted)
    assert (p2["phase_h"], p2["phase_v"]) != (7, 7)
    shift, _ = grid_scores(p2)
    assert shift > 0


def test_lossless_png_with_jpeg_history(stub_models, tmp_path: Path) -> None:
    once = np.asarray(Image.open(io.BytesIO(jpeg(textured(512, 384, seed=7), 50))).convert("RGB"))
    a, _ = analyze_bytes(png(once), "screenshot.png", tmp_path, models=stub_models)
    assert "PRIOR_JPEG_COMPRESSION" in finding_codes(a)
    b, _ = analyze_bytes(
        png(textured(512, 384, seed=7)), "render.png", tmp_path / "b", models=stub_models
    )
    assert "PRIOR_JPEG_COMPRESSION" not in finding_codes(b)


# ------------------------------------------------------------------ watermark
def test_watermark_decoder_matches_reference_library() -> None:
    imwatermark = pytest.importorskip("imwatermark")
    img = textured(512, 512, seed=8)
    enc = imwatermark.WatermarkEncoder()
    enc.set_watermark("bits", wm.SDXL_BITS)
    marked = enc.encode(np.ascontiguousarray(img[..., ::-1]), "dwtDct")[..., ::-1]
    marked = np.ascontiguousarray(marked)
    dec = imwatermark.WatermarkDecoder("bits", 48)
    ref = [int(b) for b in dec.decode(np.ascontiguousarray(marked[..., ::-1]), "dwtDct")]
    assert wm.decode(marked, 48) == ref
    hits = [m for m in wm.check(marked) if m.accuracy >= 0.85 and m.p_chance < 1e-6]
    assert hits and hits[0].name.startswith("Stable Diffusion XL")


def test_watermark_absent_on_plain_image() -> None:
    res = wm.check(textured(512, 512, seed=9))
    assert all(not (m.accuracy >= 0.85 and m.p_chance < 1e-6) for m in res)
    assert wm.p_at_least(48, 48) == pytest.approx(2.0**-48)


def test_watermark_detected_end_to_end(stub_models, tmp_path: Path) -> None:
    imwatermark = pytest.importorskip("imwatermark")
    enc = imwatermark.WatermarkEncoder()
    enc.set_watermark("bytes", b"SDV2")
    img = textured(512, 512, seed=10)
    marked = np.ascontiguousarray(
        enc.encode(np.ascontiguousarray(img[..., ::-1]), "dwtDct")[..., ::-1]
    )
    a, _ = analyze_bytes(png(marked), "gen.png", tmp_path, models=stub_models)
    assert "SD_WATERMARK" in finding_codes(a)
    assert a.verdict.label.value == "SYNTHETIC" and a.verdict.confidence == "strong support"


# ------------------------------------------------------------------ audio
def _hum(n: int, sr: int, f0: float, drift: np.ndarray | None = None) -> np.ndarray:
    f = np.full(n, f0) if drift is None else f0 + drift
    return 0.01 * np.sin(2 * np.pi * np.cumsum(f) / sr)


def test_enf_continuous_and_spliced() -> None:
    sr = 16000
    rng = np.random.default_rng(1)
    n = sr * 40
    walk = np.repeat(np.cumsum(rng.normal(0, 0.002, n // sr + 1)), sr)[:n]
    noise = 0.001 * rng.normal(0, 1, n)
    cont = _hum(n, sr, 50.0, walk) + noise
    r = dsp.enf_trace(cont.astype(np.float32))
    assert r.present and not r.jumps
    assert abs(np.median(r.freqs) - 50.0) < 0.05
    a = _hum(n // 2, sr, 50.03)
    b = _hum(n // 2, sr, 49.96)
    spliced = np.concatenate([a, b]) + noise
    r2 = dsp.enf_trace(spliced.astype(np.float32))
    assert r2.present and r2.jumps
    assert any(abs(j["t"] - 20.0) < 3.0 for j in r2.jumps)


def test_enf_absent_on_clean_audio() -> None:
    rng = np.random.default_rng(2)
    r = dsp.enf_trace((0.01 * rng.normal(0, 1, 16000 * 20)).astype(np.float32))
    assert not r.present


def test_digital_silence_and_noise_floor_jump() -> None:
    sr = 16000
    rng = np.random.default_rng(3)
    a = 0.002 * rng.normal(0, 1, sr * 6)
    b = 0.02 * rng.normal(0, 1, sr * 6)
    x = np.concatenate([a, np.zeros(int(0.05 * sr)), b]).astype(np.float32)
    cues = dsp.digital_silence(x, sr)
    assert cues and abs(cues[0].t - 6.0) < 0.1
    jumps, _, _ = dsp.noise_floor_jumps(x, sr)
    assert jumps and abs(jumps[0].t - 6.0) < 1.5


def test_effective_bandwidth_sees_low_pass() -> None:
    sr = 44100
    rng = np.random.default_rng(4)
    x = rng.normal(0, 0.1, sr * 4)
    spec = np.fft.rfft(x)  # brick-wall low-pass, as codecs and resamplers produce
    spec[np.fft.rfftfreq(len(x), 1 / sr) > 8000] = 0
    y = np.fft.irfft(spec, len(x)).astype(np.float32)
    bw = dsp.effective_bandwidth(y, sr)
    assert bw.sharp and 6500 < bw.cutoff_hz < 9500
    full = dsp.effective_bandwidth(x.astype(np.float32), sr)
    assert full.cutoff_hz > 20000


def test_fbank_shape_and_cmn() -> None:
    x = (0.1 * np.sin(2 * np.pi * 220 * np.arange(16000) / 16000)).astype(np.float32)
    f = fbank(x)
    assert f.shape == (98, 80)
    assert np.isfinite(f).all() and np.allclose(f.mean(axis=0), 0, atol=1e-4)


def test_fbank_matches_torchaudio_kaldi() -> None:
    torchaudio = pytest.importorskip("torchaudio")
    import torch

    x = (0.1 * np.random.default_rng(5).normal(0, 1, 16000)).astype(np.float32)
    ref = torchaudio.compliance.kaldi.fbank(torch.from_numpy(x)[None] * 32768, num_mel_bins=80,
                                            frame_length=25, frame_shift=10, dither=0.0,
                                            sample_frequency=16000, window_type="hamming",
                                            use_energy=False).numpy()  # fmt: skip
    ref = ref - ref.mean(axis=0, keepdims=True)
    assert np.abs(fbank(x) - ref).max() < 1e-2


def test_audio_analysis_runs_without_models(stub_models, tmp_path: Path) -> None:
    from tests.forensics.conftest import tone_speechlike

    data = wav(tone_speechlike(12.0))
    a, _ = analyze_bytes(data, "note.wav", tmp_path, models=stub_models)
    st = {t.id: t.status.value for t in a.techniques}
    assert st["audio.voice"] == "unavailable" and st["audio.transcript"] == "unavailable"
    assert st["audio.spectral"] == "ok" and st["audio.splice"] == "ok"
    assert any("Synthetic / cloned voice" in x for x in a.verdict.not_checked)
