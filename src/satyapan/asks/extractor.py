"""Ask extraction. TASK T05 — see docs/tasks/T05-ask-extractor.md.

Deterministic: same text -> same spans. No ML, no LLM, no network.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from satyapan.asks.lexicon import LEXICON, LEXICON_VERSION
from satyapan.contracts.enums import ASK_TO_REASON
from satyapan.contracts.evidence import AskSpan, Signal, SignalSource

DETECTOR_NAME = "ask_extractor"


def normalise(text: str) -> str:
    """Unicode NFC, map curly quotes to straight quotes, collapse runs of
    whitespace to one space, strip the ends."""
    text = unicodedata.normalize("NFC", text)
    # Curly quotes mapping
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_asks(text: str) -> list[AskSpan]:
    """Run every LEXICON pattern (re.IGNORECASE) over normalise(text)."""
    norm_text = normalise(text)
    spans: list[AskSpan] = []

    for lex_id, ask_type, pattern in LEXICON:
        for match in re.finditer(pattern, norm_text, flags=re.IGNORECASE):
            match_text = match.group(0)
            has_deva = bool(re.search(r"[\u0900-\u097F]", match_text))
            script = "devanagari" if has_deva else "latin"

            spans.append(
                AskSpan(
                    ask_type=ask_type,
                    start=match.start(),
                    end=match.end(),
                    text=match_text,
                    lexicon_id=lex_id,
                    script=script,
                )
            )

    # Merge overlapping spans of the SAME ask_type
    if not spans:
        return []

    spans.sort(key=lambda s: (s.start, -s.end))
    merged: list[AskSpan] = []

    for current in spans:
        if not merged:
            merged.append(current)
            continue

        prev = merged[-1]
        if current.ask_type == prev.ask_type and current.start <= prev.end:
            # Overlap! Merge them.
            new_end = max(prev.end, current.end)
            new_text = norm_text[prev.start : new_end]
            # determine script from merged text
            has_deva = bool(re.search(r"[\u0900-\u097F]", new_text))
            script = "devanagari" if has_deva else "latin"
            merged[-1] = AskSpan(
                ask_type=prev.ask_type,
                start=prev.start,
                end=new_end,
                text=new_text,
                lexicon_id=prev.lexicon_id,  # keep the first one's id
                script=script,
            )
        else:
            merged.append(current)

    # Sort as requested: by (start, ask_type)
    merged.sort(key=lambda s: (s.start, s.ask_type))
    return merged


def ask_signals(spans: list[AskSpan], evidence_id: str) -> list[Signal]:
    counts = defaultdict(int)
    for span in spans:
        counts[span.ask_type] += 1

    signals = []
    for ask_type, count in counts.items():
        reason = ASK_TO_REASON[ask_type]
        signals.append(
            Signal.make(
                reason,
                source=SignalSource.DETERMINISTIC,
                evidence_ids=[evidence_id],
                detector=DETECTOR_NAME,
                detail={
                    "ask_type": ask_type.value,
                    "count": count,
                    "lexicon_version": LEXICON_VERSION,
                },
            )
        )
    return signals


def ask_score(text: str) -> int:
    spans = extract_asks(text)
    distinct = {span.ask_type for span in spans}
    return len(distinct)
