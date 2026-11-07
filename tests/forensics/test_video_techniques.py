"""Video container and frame-integrity techniques on clips synthesised with ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from satyapan.forensics.engine import analyze_bytes

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def codes(a) -> set[str]:
    return {f.code for t in a.techniques for f in t.findings}


def clip(
    tmp: Path, name: str, src: str, seconds: float = 3.0, extra: list[str] | None = None
) -> Path:
    out = tmp / name
    ff("-f", "lavfi", "-i", f"{src}=size=320x240:rate=25", "-t", str(seconds),
       *(extra or []), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out))  # fmt: skip
    return out


def test_clean_clip_has_no_integrity_findings(stub_models, tmp_path: Path) -> None:
    p = clip(tmp_path, "clean.mp4", "testsrc2", 4.0)
    a, _ = analyze_bytes(p.read_bytes(), p.name, tmp_path / "a", models=stub_models, path=p)
    assert a.media.kind.value == "video" and a.media.fps and abs(a.media.fps - 25) < 0.5
    c = codes(a)
    assert not c & {"TIMESTAMP_GAPS", "DUPLICATED_FRAMES", "SHOT_BOUNDARIES"}
    frames = next(t for t in a.techniques if t.id == "video.frames")
    assert frames.status.value == "ok" and frames.data["frames"] >= 95
    assert any(art.name == "contact_sheet.jpg" for art in frames.artifacts)
    enc = [f for t in a.techniques for f in t.findings if f.code == "ENCODER_TAG"]
    assert enc and "FFmpeg" in enc[0].title


def test_hard_cut_between_two_shots(stub_models, tmp_path: Path) -> None:
    a1 = clip(tmp_path, "a.mp4", "testsrc2", 2.0)
    b1 = clip(tmp_path, "b.mp4", "mandelbrot", 2.0)
    out = tmp_path / "cut.mp4"
    ff("-i", str(a1), "-i", str(b1), "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out))  # fmt: skip
    a, _ = analyze_bytes(out.read_bytes(), out.name, tmp_path / "x", models=stub_models, path=out)
    assert "SHOT_BOUNDARIES" in codes(a)


def test_frozen_frames_inside_motion(stub_models, tmp_path: Path) -> None:
    av = pytest.importorskip("av")
    import numpy as np

    from tests.forensics.conftest import textured

    out = tmp_path / "frozen.mp4"
    base = textured(480, 240, seed=12)
    with av.open(str(out), "w") as container:
        st = container.add_stream("libx264", rate=25)
        st.width, st.height, st.pix_fmt = 320, 240, "yuv420p"
        for i in range(100):
            k = 40 if 41 <= i <= 49 else i  # frames 41-49 repeat frame 40 while the scene pans
            frame = av.VideoFrame.from_ndarray(
                np.ascontiguousarray(base[:, k : k + 320]), format="rgb24"
            )
            for pkt in st.encode(frame):
                container.mux(pkt)
        for pkt in st.encode():
            container.mux(pkt)
    a, _ = analyze_bytes(out.read_bytes(), out.name, tmp_path / "f", models=stub_models, path=out)
    dup = [f for t in a.techniques for f in t.findings if f.code == "DUPLICATED_FRAMES"]
    assert dup and dup[0].observations["count"] >= 8


def test_timestamp_gap_is_found(stub_models, tmp_path: Path) -> None:
    out = tmp_path / "gap.mp4"
    # drop 1.5 s from the middle but keep the original timestamps (no re-timing)
    ff("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=5",
       "-vf", "select='not(between(t,2,3.5))'", "-fps_mode", "passthrough", "-c:v", "libx264",
       "-pix_fmt", "yuv420p", str(out))  # fmt: skip
    a, _ = analyze_bytes(out.read_bytes(), out.name, tmp_path / "g", models=stub_models, path=out)
    gaps = [f for t in a.techniques for f in t.findings if f.code == "TIMESTAMP_GAPS"]
    assert gaps and gaps[0].hypothesis.value == "manipulated"
    assert any(1.8 < s.start_s < 2.3 for s in gaps[0].spans)


def test_audio_only_mp4_is_treated_as_audio(stub_models, tmp_path: Path) -> None:
    out = tmp_path / "voice.m4a"
    ff("-f", "lavfi", "-i", "sine=frequency=220:duration=3", "-c:a", "aac", str(out))
    a, _ = analyze_bytes(out.read_bytes(), out.name, tmp_path / "m", models=stub_models, path=out)
    assert a.media.kind.value == "audio"
    assert all(not t.id.startswith("video.") for t in a.techniques)


def test_video_without_audio_skips_audio_techniques(stub_models, tmp_path: Path) -> None:
    p = clip(tmp_path, "silent.mp4", "testsrc2", 2.0)
    a, _ = analyze_bytes(p.read_bytes(), p.name, tmp_path / "s", models=stub_models, path=p)
    st = {t.id: t.status.value for t in a.techniques}
    assert st["audio.spectral"] in ("skipped", "error") and st["audio.voice"] in (
        "skipped",
        "unavailable",
    )
    assert a.verdict is not None
