"""Uploaded voice note / call recording -> voice signal + transcript + ask signals. TASK T17."""

from __future__ import annotations

from satyapan.adapters.base import Transcriber
from satyapan.contracts.evidence import DetectorOutput
from satyapan.voice.detector import WindowScorer
from satyapan.voice.rules import VoiceThresholds

DETECTOR_NAME = "voice_upload"
DETECTOR_VERSION = "0.1.0"


def analyze_voice_upload(
    data: bytes,
    mime: str,
    evidence_id: str,
    scorer: WindowScorer,
    transcriber: Transcriber,
    thresholds: VoiceThresholds,
) -> DetectorOutput:
    """1. samples = decode_to_16k_mono(data, mime)   (ValueError -> grey PARSE_FAILURE)
    2. scores = scorer.score_windows(split_windows(samples))
    3. verdict = classify_windows(scores, thresholds, estimate_speech_seconds(samples))
    4. signals = [voice_signal(verdict, thresholds, [evidence_id])]
    5. transcript = transcriber.transcribe(data, mime); signals += ask_signals(extract_asks(text))
    6. grey_reasons = verdict.grey_reasons (+ DETECTOR_ERROR if the scorer raised)
    artifacts = {"transcript": text, "language": ..., "voice_label": verdict.label}
    """
    raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")
