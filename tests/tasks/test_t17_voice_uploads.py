"""T17 acceptance: uploaded voice note -> voice signal + transcript + ask signals.
Audio is GENERATED in the test (a sine tone); no media files are ever committed.
Needs numpy (dev group) and ffmpeg on PATH (brew install ffmpeg)."""

from __future__ import annotations

import io
import math
import shutil
import struct
import wave

import pytest

from satyapan.adapters.base import FakeTranscriber
from satyapan.contracts import GreyReason, ReasonCode
from satyapan.voice.audio_io import decode_to_16k_mono, estimate_speech_seconds, split_windows
from satyapan.voice.rules import VoiceThresholds
from satyapan.voice.upload import analyze_voice_upload

pytestmark = pytest.mark.task("T17")

np = pytest.importorskip("numpy")
TH = VoiceThresholds(tau_hi=0.9, tau_lo=0.6, model_version="test")


def _wav(seconds: float, amp: float = 0.5, rate: int = 44_100) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(
            b"".join(
                struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * 220 * i / rate)))
                for i in range(n)
            )
        )
    return buf.getvalue()


class FakeScorer:
    model_version = "fake"

    def __init__(self, scores: list[float]) -> None:
        self.scores = scores

    def score_windows(self, windows):  # type: ignore[no-untyped-def]
        return self.scores[: len(windows)]


needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@needs_ffmpeg
def test_decode_and_windows() -> None:
    x = decode_to_16k_mono(_wav(12.0), "audio/wav")
    assert abs(len(x) - 12 * 16_000) < 400
    assert len(split_windows(x)) == 3  # 5 + 5 + 2 (>= 1 s kept)
    assert estimate_speech_seconds(x) > 10
    assert estimate_speech_seconds(np.zeros(16_000 * 4, dtype="float32")) == 0


@needs_ffmpeg
def test_synthetic_voice_and_asks() -> None:
    out = analyze_voice_upload(
        _wav(12.0),
        "audio/wav",
        "ev_1",
        FakeScorer([0.95, 0.96, 0.2]),
        FakeTranscriber(["Sir OTP batao jaldi"]),
        TH,
    )
    codes = {s.code for s in out.signals}
    assert ReasonCode.VOICE_LIKELY_SYNTHETIC in codes and ReasonCode.ASK_CREDENTIAL in codes
    assert out.artifacts["transcript"] == "Sir OTP batao jaldi"


@needs_ffmpeg
def test_scorer_crash_is_grey() -> None:
    class Boom(FakeScorer):
        def score_windows(self, windows):  # type: ignore[no-untyped-def]
            raise RuntimeError("onnx failed")

    out = analyze_voice_upload(
        _wav(6.0), "audio/wav", "ev_1", Boom([]), FakeTranscriber(["hello"]), TH
    )
    assert GreyReason.DETECTOR_ERROR in out.grey_reasons


@needs_ffmpeg
def test_short_speech_is_grey() -> None:
    out = analyze_voice_upload(
        _wav(2.0), "audio/wav", "ev_1", FakeScorer([0.1]), FakeTranscriber(["hi"]), TH
    )
    assert GreyReason.SPEECH_TOO_SHORT in out.grey_reasons


@needs_ffmpeg
def test_garbage_bytes_raise_value_error() -> None:
    with pytest.raises(ValueError):
        decode_to_16k_mono(b"not audio at all", "audio/ogg")
