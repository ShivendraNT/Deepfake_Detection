"""Voice window rules: scores -> label -> Signal. PRE-IMPLEMENTED (shared by T07/T11/T17).

The same rule is mirrored in JavaScript in extension/lib/voice_rules.js (keep them in sync;
tests/harness/test_voice_rules_parity.py runs both on the same inputs when node exists).

Rule (docs/ARCHITECTURE.md §6):
- LIKELY_SYNTHETIC if >= 2 CONSECUTIVE windows have score >= tau_hi -> strong media signal (+1)
- INCONCLUSIVE if any window has score >= tau_lo (but the rule above did not fire)
- NO_SIGNS otherwise
- less than 3 s of speech in total -> grey reason SPEECH_TOO_SHORT (forces >= VERIFY)
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from satyapan.contracts.enums import GreyReason, ReasonCode, SignalSource, VoiceLabel
from satyapan.contracts.evidence import Signal

MIN_SPEECH_SECONDS = 3.0
MIN_CONSECUTIVE = 2


@dataclass(frozen=True)
class VoiceThresholds:
    tau_hi: float  # score at 1% FPR on Meet-captured bonafide calibration set (T18)
    tau_lo: float  # score at 5% FPR
    model_version: str
    calibration_set_sha256: str | None = None
    calibrated: bool = False


@dataclass(frozen=True)
class VoiceVerdict:
    label: VoiceLabel
    max_consecutive_over_hi: int
    windows: int
    max_score: float
    speech_seconds: float
    grey_reasons: tuple[GreyReason, ...] = ()


def load_thresholds(path: Path) -> VoiceThresholds:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return VoiceThresholds(
        tau_hi=float(raw["tau_hi"]),
        tau_lo=float(raw["tau_lo"]),
        model_version=str(raw["model_version"]),
        calibration_set_sha256=raw.get("calibration_set_sha256"),
        calibrated=bool(raw.get("calibrated", False)),
    )


def classify_windows(
    scores: Sequence[float],
    thresholds: VoiceThresholds,
    speech_seconds: float,
    min_consecutive: int = MIN_CONSECUTIVE,
) -> VoiceVerdict:
    if not 0.0 <= thresholds.tau_lo <= thresholds.tau_hi <= 1.0:
        raise ValueError("need 0 <= tau_lo <= tau_hi <= 1")
    run = best = 0
    for s in scores:
        run = run + 1 if s >= thresholds.tau_hi else 0
        best = max(best, run)
    grey: tuple[GreyReason, ...] = ()
    if speech_seconds < MIN_SPEECH_SECONDS:
        grey = (GreyReason.SPEECH_TOO_SHORT,)
    if best >= min_consecutive:
        label = VoiceLabel.LIKELY_SYNTHETIC
    elif any(s >= thresholds.tau_lo for s in scores) or grey:
        label = VoiceLabel.INCONCLUSIVE
    else:
        label = VoiceLabel.NO_SIGNS
    return VoiceVerdict(
        label=label,
        max_consecutive_over_hi=best,
        windows=len(scores),
        max_score=max(scores, default=0.0),
        speech_seconds=speech_seconds,
        grey_reasons=grey,
    )


_LABEL_TO_CODE = {
    VoiceLabel.LIKELY_SYNTHETIC: ReasonCode.VOICE_LIKELY_SYNTHETIC,
    VoiceLabel.INCONCLUSIVE: ReasonCode.VOICE_INCONCLUSIVE,
    VoiceLabel.NO_SIGNS: ReasonCode.VOICE_NO_SIGNS,
}


def voice_signal(
    verdict: VoiceVerdict,
    thresholds: VoiceThresholds,
    evidence_ids: list[str],
    detector: str = "voice_xlsr_l7",
) -> Signal:
    return Signal.make(
        _LABEL_TO_CODE[verdict.label],
        source=SignalSource.ML,
        evidence_ids=evidence_ids,
        detector=f"{detector}@{thresholds.model_version}",
        score=verdict.max_score,
        detail={
            "windows": verdict.windows,
            "consecutive_over_hi": verdict.max_consecutive_over_hi,
            "calibrated": thresholds.calibrated,
        },
    )
