"""Ask extraction. TASK T05 — see docs/tasks/T05-ask-extractor.md.

Deterministic: same text -> same spans. No ML, no LLM, no network.
"""

from __future__ import annotations

from satyapan.contracts.evidence import AskSpan, Signal

DETECTOR_NAME = "ask_extractor"


def normalise(text: str) -> str:
    """Unicode NFC, map curly quotes to straight quotes, collapse runs of whitespace to one
    space, strip the ends. AskSpan.start/end always refer to positions in the NORMALISED text."""
    raise NotImplementedError("T05: see docs/tasks/T05-ask-extractor.md")


def extract_asks(text: str) -> list[AskSpan]:
    """Run every LEXICON pattern (re.IGNORECASE) over normalise(text).

    Return one AskSpan per match, sorted by (start, ask_type). Overlapping matches of the
    SAME ask type are merged into one span. script = "devanagari" if the match contains any
    character in U+0900..U+097F else "latin".
    """
    raise NotImplementedError("T05: see docs/tasks/T05-ask-extractor.md")


def ask_signals(spans: list[AskSpan], evidence_id: str) -> list[Signal]:
    """One Signal per DISTINCT ask type: Signal.make(ASK_TO_REASON[ask_type],
    source=SignalSource.DETERMINISTIC, evidence_ids=[evidence_id], detector=DETECTOR_NAME,
    detail={"ask_type": "A2", "count": <n spans>, "lexicon_version": LEXICON_VERSION})."""
    raise NotImplementedError("T05: see docs/tasks/T05-ask-extractor.md")


def ask_score(text: str) -> int:
    """Research detector D4 score = number of DISTINCT ask types in the text."""
    raise NotImplementedError("T05: see docs/tasks/T05-ask-extractor.md")
