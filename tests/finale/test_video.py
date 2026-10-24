"""Video deepfake check (docs/VIDEO_DEEPFAKE.md): cue maths on synthetic signals, the window
rule, the raise-only policy effect, and the live/file plumbing with a fake analyzer.

No media, no models, no network: frames are generated arrays, faces are synthetic landmarks.
"""

from __future__ import annotations

import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import (
    Band,
    CaseKind,
    ReasonCode,
    SignalGroup,
    SignalSource,
    TargetRule,
    VideoLabel,
)
from satyapan.contracts.evidence import Signal
from satyapan.contracts.live import VideoEvent
from satyapan.contracts.signal_table import SIGNAL_TABLE
from satyapan.policy.engine import decide
from satyapan.video import features as F
from satyapan.video import regions as R
from satyapan.video.fusion import FusionModel
from satyapan.video.landmarks import FaceObs
from satyapan.video.lighting import lighting_features
from satyapan.video.lipsync import lipsync_features
from satyapan.video.observe import FrameRecord, observe
from satyapan.video.rppg import pulse_features
from satyapan.video.rules import VideoThresholds, classify_windows, video_signal

FS = 15.0
THR = VideoThresholds(tau_hi=0.8, tau_lo=0.5, model_version="test")


def _rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


# ------------------------------------------------------------------------- pulse (rPPG)
def _skin(t: np.ndarray, pulse: np.ndarray, noise: float, rng: np.random.Generator) -> np.ndarray:
    """RGB skin trace whose blood-volume pulse mostly modulates green (as real skin does)."""
    base = np.array([170.0, 120.0, 100.0])
    mod = np.stack([0.3 * pulse, 1.0 * pulse, 0.15 * pulse], axis=1)
    return base * (1 + 0.004 * mod) + rng.normal(0, noise, (len(t), 3))


def test_pulse_is_found_when_every_patch_beats_together() -> None:
    rng = _rng(1)
    t = np.arange(0, 6, 1 / FS)
    beat = np.sin(2 * np.pi * 1.2 * t)  # 72 bpm
    traces = {p: _skin(t, beat, 0.05, rng) for p in ("forehead", "cheek_l", "cheek_r")}
    feats = pulse_features(t, traces, FS)
    assert feats["pulse_snr"] > 3.0
    assert feats["pulse_coherence"] > 0.8
    assert feats["pulse_hr_spread"] < 0.1


def test_no_pulse_means_low_coherence_and_low_snr() -> None:
    rng = _rng(2)
    t = np.arange(0, 6, 1 / FS)
    traces = {p: _skin(t, np.zeros_like(t), 0.3, rng) for p in ("forehead", "cheek_l", "cheek_r")}
    beating = {p: _skin(t, np.sin(2 * np.pi * 1.2 * t), 0.05, rng) for p in traces}
    flat, live = pulse_features(t, traces, FS), pulse_features(t, beating, FS)
    assert flat["pulse_coherence"] < live["pulse_coherence"]
    assert flat["pulse_snr"] < live["pulse_snr"]


def test_pulse_abstains_on_short_or_missing_input() -> None:
    t = np.arange(0, 2, 1 / FS)
    feats = pulse_features(t, {"forehead": np.ones((len(t), 3))}, FS)
    assert all(math.isnan(v) for v in feats.values())


# ------------------------------------------------------------------------- lighting
def _patches(
    n: int,
    cheek_shift: tuple[float, float, float] = (0, 0, 0),
    jitter: float = 0.0,
    rng: np.random.Generator | None = None,
) -> dict[str, np.ndarray]:
    rng = rng or _rng(3)
    skin = np.tile([170.0, 120.0, 100.0], (n, 1))
    out = {k: skin.copy() for k in ("forehead", "forehead_l", "forehead_r")}
    for k in ("cheek_l", "cheek_r"):
        out[k] = skin + np.array(cheek_shift) + rng.normal(0, jitter, (n, 3))
    return out


def test_lighting_matches_on_one_face_and_flags_a_pasted_one() -> None:
    same = lighting_features(_patches(60), np.full((60, 4), np.nan))
    pasted = lighting_features(_patches(60, cheek_shift=(25, -5, -15)), np.full((60, 4), np.nan))
    assert same["light_chroma_gap"] < 1.0
    assert pasted["light_chroma_gap"] > 8.0
    flicker = lighting_features(_patches(60, jitter=6.0), np.full((60, 4), np.nan))
    steady = lighting_features(_patches(60, jitter=0.2), np.full((60, 4), np.nan))
    assert flicker["light_flicker"] > steady["light_flicker"]


def test_specular_gap_needs_highlights_in_both_eyes() -> None:
    spec = np.tile([0.2, -0.3, 0.2, -0.3], (40, 1))
    assert lighting_features({}, spec)["light_spec_gap"] == pytest.approx(0.0)
    spec[:, 2] = -0.5  # the other eye's highlight sits elsewhere: inconsistent lights
    assert lighting_features({}, spec)["light_spec_gap"] > 0.5
    assert math.isnan(lighting_features({}, np.full((40, 4), np.nan))["light_spec_gap"])


# ------------------------------------------------------------------------- lip-sync
def _speech(envelope: np.ndarray, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(len(envelope) / FS * sr)
    env = np.interp(np.arange(n) / sr, np.arange(len(envelope)) / FS, envelope)
    return (rng.normal(0, 1, n) * (0.02 + env)).astype(np.float32)


def test_lips_that_move_with_the_voice_correlate() -> None:
    rng = _rng(4)
    t = np.arange(0, 6, 1 / FS)
    talk = np.clip(np.sin(2 * np.pi * 2.5 * t) + 0.4, 0, None)
    synced = lipsync_features(t, talk, _speech(talk, 16000, rng), 16000, FS)
    other = np.clip(np.sin(2 * np.pi * 1.1 * t + 1.3) + 0.4, 0, None)
    dubbed = lipsync_features(t, talk, _speech(other, 16000, rng), 16000, FS)
    assert synced["av_corr"] > 0.6
    assert synced["av_corr"] > dubbed["av_corr"] + 0.3


def test_lipsync_abstains_without_audio_or_speech() -> None:
    t = np.arange(0, 6, 1 / FS)
    mouth = np.abs(np.sin(t))
    assert math.isnan(lipsync_features(t, mouth, None, 16000, FS)["av_corr"])
    silence = np.zeros(16000 * 6, np.float32)
    assert math.isnan(lipsync_features(t, mouth, silence, 16000, FS)["av_corr"])


# ------------------------------------------------------------------------- windows, coverage
def test_windows_are_six_seconds_with_three_second_hops() -> None:
    assert F.windows(0.0, 12.0) == [(0.0, 6.0), (3.0, 9.0), (6.0, 12.0)]
    assert F.windows(0.0, 5.0) == []


def test_coverage_gate_abstains_on_missing_or_tiny_faces() -> None:
    ok = [FrameRecord(t=i / FS, found=True, face_w=150, luma=120) for i in range(90)]
    assert F.coverage(ok).usable
    gone = [FrameRecord(t=i / FS, found=i % 2 == 0, face_w=150, luma=120) for i in range(90)]
    assert F.coverage(gone).problem() == "no_face"
    tiny = [FrameRecord(t=i / FS, found=True, face_w=40, luma=120) for i in range(90)]
    assert F.coverage(tiny).problem() == "face_too_small"
    dark = [FrameRecord(t=i / FS, found=True, face_w=150, luma=10) for i in range(90)]
    assert F.coverage(dark).problem() == "bad_lighting"


# ------------------------------------------------------------------------- rule + policy
def test_two_consecutive_high_windows_are_needed() -> None:
    assert classify_windows([0.9, 0.9], THR).label == VideoLabel.LIKELY_SYNTHETIC
    assert classify_windows([0.9, None, 0.9], THR).label == VideoLabel.INCONCLUSIVE
    assert classify_windows([0.9, 0.1, 0.9], THR).label == VideoLabel.INCONCLUSIVE
    assert classify_windows([0.1, 0.2], THR).label == VideoLabel.NO_SIGNS
    nothing = classify_windows([None, None], THR, ["face_too_small", "face_too_small"])
    assert nothing.label == VideoLabel.INCONCLUSIVE
    assert nothing.problem == "face_too_small"
    with pytest.raises(ValueError):
        classify_windows([0.5], VideoThresholds(tau_hi=0.2, tau_lo=0.5, model_version="x"))


def test_video_codes_are_ml_media_and_raise_only() -> None:
    hi = SIGNAL_TABLE[ReasonCode.VIDEO_LIKELY_SYNTHETIC]
    assert (hi.group, hi.target) == (SignalGroup.MEDIA, TargetRule.PLUS_ONE)
    for code in (ReasonCode.VIDEO_NO_SIGNS, ReasonCode.VIDEO_INCONCLUSIVE):
        assert SIGNAL_TABLE[code].target == TargetRule.NONE
    for code in (
        ReasonCode.VIDEO_NO_SIGNS,
        ReasonCode.VIDEO_INCONCLUSIVE,
        ReasonCode.VIDEO_LIKELY_SYNTHETIC,
    ):
        assert SIGNAL_TABLE[code].allowed_sources == frozenset({SignalSource.ML})
        with pytest.raises(ValueError):
            Signal.make(code, source=SignalSource.LLM)


def _live_case(signals: list[Signal]) -> Case:
    return Case(
        id="case_live_v",
        title="Live call",
        kind=CaseKind.LIVE_CALL,
        created_at=utcnow(),
        created_by="emp_priya",
        signals=signals,
    )


def test_likely_synthetic_face_raises_one_band_and_clean_face_never_lowers(master) -> None:
    sig = video_signal(classify_windows([0.9, 0.95], THR), THR, ["ev_v"])
    assert sig.code == ReasonCode.VIDEO_LIKELY_SYNTHETIC
    assert decide(_live_case([sig]), master).band == Band.VERIFY
    ask = Signal.make(ReasonCode.ASK_SECRECY, source=SignalSource.DETERMINISTIC, evidence_ids=["e"])
    base = decide(_live_case([ask]), master).band
    clean = video_signal(classify_windows([0.1, 0.1], THR), THR, ["ev_v"])
    assert clean.code == ReasonCode.VIDEO_NO_SIGNS
    assert decide(_live_case([ask, clean]), master).band == base


# ------------------------------------------------------------------------- fusion model
def test_fusion_scores_rise_with_a_positive_weight_and_flag_missing(tmp_path: Path) -> None:
    raw = {
        "features": ["blend", "pulse_coherence"], "median": [0.0, 0.5], "mean": [0.0, 0.5],
        "scale": [1.0, 0.2], "coef": [1.5, -1.0], "missing_coef": [0.0, 0.3],
        "intercept": -0.5, "version": "t",
    }  # fmt: skip
    path = tmp_path / "fusion.json"
    path.write_text(json.dumps(raw))
    model = FusionModel.load(path)
    lo, hi = model.score(np.array([[-1.0, 0.5], [2.0, 0.5]]))
    assert hi > lo
    missing = model.score(np.array([[0.0, np.nan]]))[0]
    present = model.score(np.array([[0.0, 0.5]]))[0]
    assert missing > present  # the missing flag carries its own (learned) weight
    assert set(model.contributions(np.array([[2.0, 0.5]]))) == {"blend", "pulse_coherence"}


def test_shipped_fusion_and_thresholds_are_consistent() -> None:
    from satyapan.video.fusion import DEFAULT_PATH
    from satyapan.video.rules import DEFAULT_PATH as THR_PATH
    from satyapan.video.rules import load_thresholds

    if not DEFAULT_PATH.exists() or not THR_PATH.exists():
        pytest.skip("video fusion not fitted yet (research/video/fit_fusion.py)")
    model = FusionModel.load(DEFAULT_PATH)
    thr = load_thresholds(THR_PATH)
    assert set(model.features) <= set(F.FEATURES)
    assert 0.0 <= thr.tau_lo <= thr.tau_hi <= 1.0
    assert not thr.calibrated or "webcam" in thr.calibration_set


# ------------------------------------------------------------------------- stream + live
def _pts(cx: float = 320, cy: float = 240, w: float = 160) -> np.ndarray:
    pts = np.tile([cx, cy], (478, 1)).astype(np.float32)
    for k, idx in enumerate(R.FACE_OVAL):
        a = 2 * np.pi * k / len(R.FACE_OVAL)
        pts[idx] = [cx + 0.5 * w * np.sin(a), cy - 0.65 * w * np.cos(a)]
    pts[R.OVAL_IMG_LEFT], pts[R.OVAL_IMG_RIGHT] = [cx - w / 2, cy], [cx + w / 2, cy]
    pts[R.FOREHEAD], pts[R.GLABELLA] = [cx, cy - 0.4 * w], [cx, cy - 0.25 * w]
    pts[R.CHEEK_IMG_LEFT], pts[R.CHEEK_IMG_RIGHT] = (
        [cx - 0.25 * w, cy + 0.05 * w],
        [cx + 0.25 * w, cy + 0.05 * w],
    )
    pts[R.MOUTH_LEFT], pts[R.MOUTH_RIGHT] = (
        [cx - 0.15 * w, cy + 0.3 * w],
        [cx + 0.15 * w, cy + 0.3 * w],
    )
    pts[R.LIP_UPPER_INNER], pts[R.LIP_LOWER_INNER] = [cx, cy + 0.29 * w], [cx, cy + 0.33 * w]
    return pts


class _FakeTracker:
    def __init__(self) -> None:
        self.closed = False

    def track(self, frame: np.ndarray, t: float) -> FaceObs | None:
        return FaceObs(pts=_pts(), jaw_open=0.1) if frame.mean() > 5 else None

    def close(self) -> None:
        self.closed = True


def _frames(seconds: float, value: int = 128) -> list[tuple[float, np.ndarray]]:
    frame = np.full((480, 640, 3), value, np.uint8)
    return [(i / FS, frame) for i in range(int(seconds * FS))]


def _fake_analyzer(score: float = 0.9):
    from satyapan.video.analyzer import VideoAnalyzer

    fusion = FusionModel(
        features=("pulse_snr",),
        median=np.zeros(1),
        mean=np.zeros(1),
        scale=np.ones(1),
        coef=np.zeros(1),
        missing_coef=np.zeros(1),
        intercept=math.log(score / (1 - score)),
        version="fake",
    )
    return VideoAnalyzer(fusion, THR, scorer=None, tracker_factory=_FakeTracker)


def test_stream_emits_a_window_every_hop_and_forgets_frames() -> None:
    stream = _fake_analyzer().new_stream()
    out = stream.add_frames(_frames(6.2))
    assert [w.index for w in out] == [0]
    out = stream.add_frames([(t + 6.2, f) for t, f in _frames(3.0)])
    assert [w.index for w in out] == [1]
    assert all(r.t >= 6.0 for r in stream._records)  # only what the next window needs
    assert all(r.crop is None for r in stream._records)  # no CNN -> no crops kept
    stream.close()


def test_dark_screen_abstains_instead_of_guessing() -> None:
    stream = _fake_analyzer().new_stream()
    (window,) = stream.add_frames(_frames(6.2, value=0))
    assert window.score is None and window.coverage.problem() == "no_face"


def _live_service(analyzer, master):
    from satyapan.adapters.base import FakeTranscriber
    from satyapan.live.service import LiveService
    from satyapan.voice.rules import VoiceThresholds

    return LiveService(
        master=master,
        transcriber=FakeTranscriber([]),
        thresholds=VoiceThresholds(0.9, 0.5, "t"),
        video_factory=lambda: analyzer,
    )


def test_live_video_raises_band_and_never_ships_a_score(master) -> None:
    live = _live_service(_fake_analyzer(0.95), master)
    live.start("c1", "emp_priya")
    events = live.handle_video("c1", _frames(9.2))
    video = [e for e in events if isinstance(e, VideoEvent)]
    assert video and video[-1].label == VideoLabel.LIKELY_SYNTHETIC
    assert all(e.score is None for e in video)
    assert live.sessions["c1"].case.decision.band == Band.VERIFY
    live.stop_video("c1")


def test_live_video_unavailable_is_said_once(master) -> None:
    live = _live_service(None, master)
    live.start("c2", "emp_priya")
    first = live.handle_video("c2", _frames(1.0))
    assert [getattr(e, "code", None) for e in first] == ["video_unavailable"]
    assert live.handle_video("c2", _frames(1.0)) == []


def _jpeg(value: int) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(np.full((120, 160, 3), value, np.uint8)).save(buf, format="JPEG")
    return buf.getvalue()


def test_video_route_validates_and_relays(client) -> None:
    client.app.state.satyapan.video_override = _fake_analyzer(0.95)
    r = client.post("/live/c_route/start")
    assert r.status_code == 200
    files = [("frames", (f"f{i}.jpg", _jpeg(128), "image/jpeg")) for i in range(3)]
    bad = client.post("/live/c_route/video", files=files, data={"times": "[0, 1]"})
    assert bad.status_code == 422
    assert (
        client.post("/live/nope/video", files=files, data={"times": "[0,1,2]"}).status_code == 404
    )
    ok = client.post(
        "/live/c_route/video", files=files, data={"times": json.dumps([0.0, 0.066, 0.133])}
    )
    assert ok.status_code == 200 and ok.json() == []  # no window finished yet


def test_decode_jpeg_rejects_garbage() -> None:
    from satyapan.video.frames import decode_jpeg

    assert decode_jpeg(_jpeg(90)).shape == (120, 160, 3)
    with pytest.raises(ValueError):
        decode_jpeg(b"not an image")


def test_observe_measures_patches_and_mouth() -> None:
    frame = np.full((480, 640, 3), 140, np.uint8)
    rec = observe(frame, 0.0, _pts(), 0.2)
    assert rec.found and rec.face_w == pytest.approx(160, abs=1)
    assert set(rec.patches) == set(R.PATCHES)
    assert rec.mouth == pytest.approx(0.04 * 160 / (0.3 * 160), rel=0.05)
    assert all(math.isnan(v) for v in rec.spec)  # flat eyes: no highlight, no guess


@dataclass
class _Ev:
    id: str = "ev_video"
    filename: str | None = "clip.mp4"
    media_type: str = "video/mp4"
    analysis_runs: list[object] = field(default_factory=list)


def test_video_file_without_engine_is_an_abstention_not_a_grey_flag(master) -> None:
    from satyapan.pipeline import PipelineContext, _video
    from satyapan.settings import Settings
    from satyapan.voice.rules import VoiceThresholds

    ctx = PipelineContext(
        master=master, settings=Settings(), thresholds=VoiceThresholds(0.9, 0.5, "t")
    )
    out = _video(b"\x00" * 16, _Ev(), _live_case([]), ctx)  # type: ignore[arg-type]
    assert out.artifacts["video_label"] == "not_analysed"
    assert out.grey_reasons == [] and out.signals == []


def test_video_files_are_routed_to_the_video_channel() -> None:
    from satyapan.api.companion.service import _channel_for
    from satyapan.contracts.enums import Channel

    assert _channel_for("ceo_message.mp4", "application/octet-stream") == Channel.VIDEO
    assert _channel_for("clip.webm", "video/webm") == Channel.VIDEO
    assert _channel_for("note.webm", "audio/webm") == Channel.VOICE_NOTE


def test_model_files_are_never_committed() -> None:
    root = Path(__file__).resolve().parents[2]
    ignore = (root / ".gitignore").read_text()
    assert "*.onnx" in ignore and "models/" in ignore


def test_stream_audio_fills_gaps_with_silence_and_stays_bounded() -> None:
    stream = _fake_analyzer().new_stream()
    one = np.ones(16000, np.float32)
    stream.add_audio(one, 0.0)
    stream.add_audio(one, 2.0)  # a 1 s pause between utterances becomes silence
    assert stream._audio is not None and len(stream._audio) == 3 * 16000
    assert stream._audio[16000:32000].max() == 0.0
    for k in range(40):
        stream.add_audio(one, 3.0 + k)
    assert len(stream._audio) <= int((F.WINDOW_S + F.HOP_S + 2) * 16000)
    stream.close()


def test_a_patch_leaving_the_frame_does_not_break_the_window() -> None:
    recs = []
    for i in range(90):
        patches = {k: (170.0, 120.0, 100.0) for k in R.PATCHES}
        if i % 7 == 0:
            patches["cheek_r"] = (float("nan"),) * 3  # face at the frame edge
        recs.append(FrameRecord(t=i / FS, found=True, face_w=150, luma=120, patches=patches))
    feats = F.window_features(recs)
    assert math.isfinite(feats["light_chroma_gap"])


def test_lipsync_uses_the_covered_part_of_a_short_clip() -> None:
    rng = _rng(5)
    t = np.arange(0, 6, 1 / FS)
    talk = np.clip(np.sin(2 * np.pi * 2.5 * t) + 0.4, 0, None)
    audio = _speech(talk, 16000, rng)[: int(16000 * 5.0)]  # audio ends 1 s early
    assert lipsync_features(t, talk, audio, 16000, FS)["av_corr"] > 0.5
    too_short = audio[: int(16000 * 2.0)]
    assert math.isnan(lipsync_features(t, talk, too_short, 16000, FS)["av_corr"])
