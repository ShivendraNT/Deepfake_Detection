from __future__ import annotations

import time

from satyapan.adapters.base import Transcriber
from satyapan.asks.extractor import ask_signals, extract_asks
from satyapan.contracts.enums import GreyReason
from satyapan.contracts.evidence import DetectorOutput, Signal
from satyapan.voice.audio_io import decode_to_16k_mono, estimate_speech_seconds, split_windows
from satyapan.voice.detector import WindowScorer
from satyapan.voice.rules import VoiceThresholds, classify_windows, voice_signal

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
    t0 = time.perf_counter()
    grey_reasons: list[GreyReason] = []
    signals: list[Signal] = []

    try:
        samples = decode_to_16k_mono(data, mime)
    except ValueError as exc:
        return DetectorOutput(
            detector=DETECTOR_NAME,
            version=DETECTOR_VERSION,
            evidence_id=evidence_id,
            signals=[],
            grey_reasons=[GreyReason.PARSE_FAILURE],
            artifacts={},
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            error=str(exc),
        )

    speech_seconds = estimate_speech_seconds(samples)
    windows = split_windows(samples)

    scorer_failed = False
    scores: list[float] = []
    try:
        scores = scorer.score_windows(windows)
    except Exception:
        scorer_failed = True
        scores = []
        grey_reasons.append(GreyReason.DETECTOR_ERROR)

    verdict = classify_windows(scores, thresholds, speech_seconds)
    grey_reasons.extend(verdict.grey_reasons)

    if not scorer_failed:
        signals.append(voice_signal(verdict, thresholds, [evidence_id]))

    trans_result = transcriber.transcribe(data, mime)
    transcript_text = trans_result.text
    spans = extract_asks(transcript_text)
    signals.extend(ask_signals(spans, evidence_id=evidence_id))

    artifacts = {
        "transcript": transcript_text,
        "language": trans_result.language,
        "voice_label": verdict.label,
    }

    # Deduplicate grey reasons preserving order
    seen: set[GreyReason] = set()
    deduped_grey: list[GreyReason] = []
    for g in grey_reasons:
        if g not in seen:
            seen.add(g)
            deduped_grey.append(g)

    return DetectorOutput(
        detector=DETECTOR_NAME,
        version=DETECTOR_VERSION,
        evidence_id=evidence_id,
        signals=signals,
        grey_reasons=deduped_grey,
        artifacts=artifacts,
        duration_ms=(time.perf_counter() - t0) * 1000.0,
    )
