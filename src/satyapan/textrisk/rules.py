"""Scam-text model -> Signal. Raise-only: below tau_hi nothing is emitted (no "clean" code).

TEXT_SCAM_LIKELY is a style-group, ML-sourced signal: the policy caps it at VERIFY, it is never a
strong group and never corroborates an ask (ADR-021), so a wordy but honest message can at most
ask for a callback. Short texts (< MIN_WORDS) are not scored: too little to judge.
"""

from __future__ import annotations

import re

from satyapan.contracts.enums import ReasonCode, SignalSource
from satyapan.contracts.evidence import Signal
from satyapan.textrisk.model import TextRiskModel

MIN_WORDS = 6
_WORD = re.compile(r"\w+", re.UNICODE)


def text_signal(model: TextRiskModel, text: str, evidence_ids: list[str]) -> Signal | None:
    if len(_WORD.findall(text)) < MIN_WORDS:
        return None
    p = model.score(text)
    if p < model.tau_hi:
        return None
    return Signal.make(
        ReasonCode.TEXT_SCAM_LIKELY,
        source=SignalSource.ML,
        evidence_ids=evidence_ids,
        detector=f"textrisk@{model.version}",
        score=p,  # checker/security only
        detail={"top_ngrams": ", ".join(model.top_ngrams(text))},
    )
