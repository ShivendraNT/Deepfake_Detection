"""Ask extraction. TASK T05 — see docs/tasks/T05-ask-extractor.md.

Deterministic: same text -> same spans. No ML, no LLM, no network.
"""

from __future__ import annotations

import re
import unicodedata

from satyapan.asks.lexicon import LEXICON, LEXICON_VERSION
from satyapan.contracts.enums import ASK_TO_REASON, AskType, SignalSource
from satyapan.contracts.evidence import AskSpan, Signal

DETECTOR_NAME = "ask_extractor"

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def normalise(text: str) -> str:
    """Unicode NFC, map curly quotes to straight quotes, collapse runs of whitespace to one
    space, strip the ends. AskSpan.start/end always refer to positions in the NORMALISED text."""
    text = unicodedata.normalize("NFC", text)
    for curly, straight in ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'):
        text = text.replace(curly, straight)
    return " ".join(text.split())


def _script_of(text: str) -> str:
    return "devanagari" if _DEVANAGARI.search(text) else "latin"


def extract_asks(text: str) -> list[AskSpan]:
    """Run every LEXICON pattern (re.IGNORECASE) over normalise(text).

    Return one AskSpan per match, sorted by (start, ask_type). Overlapping matches of the
    SAME ask type are merged into one span. script = "devanagari" if the match contains any
    character in U+0900..U+097F else "latin".
    """
    norm = normalise(text)
    spans: list[AskSpan] = []
    for entry_id, ask_type, pattern in LEXICON:
        for m in re.finditer(pattern, norm, flags=re.IGNORECASE):
            spans.append(
                AskSpan(
                    ask_type=ask_type,
                    start=m.start(),
                    end=m.end(),
                    text=norm[m.start() : m.end()],
                    lexicon_id=entry_id,
                    script=_script_of(norm[m.start() : m.end()]),
                )
            )
    by_type: dict[AskType, list[AskSpan]] = {}
    for s in spans:
        by_type.setdefault(s.ask_type, []).append(s)
    merged: list[AskSpan] = []
    for group in by_type.values():
        group.sort(key=lambda s: s.start)
        cur = group[0]
        for s in group[1:]:
            if s.start < cur.end:
                start, end = cur.start, max(cur.end, s.end)
                cur = AskSpan(
                    ask_type=cur.ask_type,
                    start=start,
                    end=end,
                    text=norm[start:end],
                    lexicon_id=cur.lexicon_id,
                    script=_script_of(norm[start:end]),
                )
            else:
                merged.append(cur)
                cur = s
        merged.append(cur)
    merged.sort(key=lambda s: (s.start, s.ask_type))
    return merged


def ask_signals(spans: list[AskSpan], evidence_id: str) -> list[Signal]:
    """One Signal per DISTINCT ask type: Signal.make(ASK_TO_REASON[ask_type],
    source=SignalSource.DETERMINISTIC, evidence_ids=[evidence_id], detector=DETECTOR_NAME,
    detail={"ask_type": "A2", "count": <n spans>, "lexicon_version": LEXICON_VERSION})."""
    counts: dict[AskType, int] = {}
    for s in spans:
        counts[s.ask_type] = counts.get(s.ask_type, 0) + 1
    return [
        Signal.make(
            ASK_TO_REASON[ask_type],
            source=SignalSource.DETERMINISTIC,
            evidence_ids=[evidence_id],
            detector=DETECTOR_NAME,
            detail={"ask_type": ask_type.value, "count": n, "lexicon_version": LEXICON_VERSION},
        )
        for ask_type, n in counts.items()
    ]


def ask_score(text: str) -> int:
    """Research detector D4 score = number of DISTINCT ask types in the text."""
    return len({s.ask_type for s in extract_asks(text)})
