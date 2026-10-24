"""Voice-clone check in live calls and voice notes (docs/VOICE_DEEPFAKE.md).

The desktop capture window sends only audio; the engine cuts each utterance into 5 s windows
and scores them with the voice model. Makers only ever see a label. A client that scores its
own windows (the Chrome extension) is never scored twice.
"""

from __future__ import annotations

import io
import math
import shutil
import struct
import wave
from dataclasses import dataclass

import numpy as np
import pytest

from satyapan.adapters.base import FakeTranscriber
from satyapan.contracts.enums import ReasonCode
from satyapan.contracts.live import VoiceEvent, VoiceWindowResult
from satyapan.live.service import LiveService
from satyapan.voice.rules import VoiceThresholds

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _wav(seconds: float, rate: int = 16_000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(
            b"".join(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 220 * i / rate)))
                for i in range(n)
            )
        )
    return buf.getvalue()


@dataclass
class FixedScorer:
    value: float
    model_version: str = "test-voice"
    windows_seen: int = 0

    def score_windows(self, windows: list[np.ndarray]) -> list[float]:
        self.windows_seen += len(windows)
        return [self.value] * len(windows)


def _live(master, scorer: FixedScorer | None) -> LiveService:
    return LiveService(
        master=master,
        transcriber=FakeTranscriber(["hello, quick question about the invoice"]),
        thresholds=VoiceThresholds(0.9, 0.6, "test-voice"),
        voice_factory=lambda: scorer,
    )


def test_desktop_calls_get_their_voice_scored_here_and_raise_the_band(master) -> None:
    scorer = FixedScorer(0.97)
    live = _live(master, scorer)
    live.start("c1", "emp_priya")
    events = live.handle_chunk("c1", 0, _wav(10.5), "audio/wav", 0.0, 10.5)
    voice = [e for e in events if isinstance(e, VoiceEvent)]
    assert scorer.windows_seen == 2  # 10.5 s -> two 5 s windows (a tail under 1 s is dropped)
    assert voice and voice[-1].label.value == "likely_synthetic"
    assert all(e.score is None for e in voice)  # makers never see a score
    codes = {s.code for s in live.sessions["c1"].case.signals}
    assert ReasonCode.VOICE_LIKELY_SYNTHETIC in codes


def test_a_clean_voice_never_lowers_anything(master) -> None:
    live = _live(master, FixedScorer(0.05))
    live.start("c1", "emp_priya")
    events = live.handle_chunk("c1", 0, _wav(11.0), "audio/wav", 0.0, 11.0)
    voice = [e for e in events if isinstance(e, VoiceEvent)]
    assert voice and voice[-1].label.value == "no_signs"


def test_a_client_that_scores_its_own_windows_is_not_scored_twice(master) -> None:
    scorer = FixedScorer(0.97)
    live = _live(master, scorer)
    live.start("c1", "emp_priya")
    w = VoiceWindowResult(call_id="c1", window_index=0, t_start_s=0, t_end_s=5, score=0.1,
                          speech_seconds=5, model_version="ext")  # fmt: skip
    live.handle_voice("c1", [w])
    live.handle_chunk("c1", 0, _wav(11.0), "audio/wav", 0.0, 11.0)
    assert scorer.windows_seen == 0


def test_no_voice_model_means_no_voice_verdict_not_a_pass(master) -> None:
    live = _live(master, None)
    live.start("c1", "emp_priya")
    events = live.handle_chunk("c1", 0, _wav(6.0), "audio/wav", 0.0, 6.0)
    assert not [e for e in events if isinstance(e, VoiceEvent)]
    assert not {s.code for s in live.sessions["c1"].case.signals} & {
        ReasonCode.VOICE_NO_SIGNS,
        ReasonCode.VOICE_LIKELY_SYNTHETIC,
    }


def test_one_unusual_window_with_enough_speech_asks_for_a_call_back() -> None:
    """A short voice note is often one 5 s window: two windows over tau_hi can't happen, so a
    window over tau_lo with enough speech is SUSPICIOUS (VERIFY). Too little speech is
    'could not judge' (INCONCLUSIVE, no band effect); a clean voice is NO_SIGNS."""
    from satyapan.contracts.enums import ReasonCode, TargetRule
    from satyapan.voice.rules import VoiceThresholds, classify_windows, voice_signal

    thr = VoiceThresholds(tau_hi=0.9, tau_lo=0.6, model_version="t")
    sig = voice_signal(classify_windows([0.95], thr, speech_seconds=4.5), thr, ["ev_1"])
    assert sig.code == ReasonCode.VOICE_SUSPICIOUS and sig.target == TargetRule.VERIFY
    short = voice_signal(classify_windows([0.95], thr, speech_seconds=1.0), thr, ["ev_1"])
    assert short.code == ReasonCode.VOICE_INCONCLUSIVE and short.target == TargetRule.NONE
    clean = voice_signal(classify_windows([0.1, 0.2], thr, speech_seconds=9.0), thr, ["ev_1"])
    assert clean.code == ReasonCode.VOICE_NO_SIGNS
    two = voice_signal(classify_windows([0.95, 0.97], thr, speech_seconds=9.0), thr, ["ev_1"])
    assert two.code == ReasonCode.VOICE_LIKELY_SYNTHETIC
