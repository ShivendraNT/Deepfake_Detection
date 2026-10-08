"""Faithfulness checker for LLM summaries. TASK T15 — docs/tasks/T15-llm-summary-faithfulness.md."""

from __future__ import annotations

import re

from satyapan.contracts.explain import EvidenceItemForLLM, FaithfulnessResult

FORBIDDEN_WORDS_EN: tuple[str, ...] = ("safe", "legitimate", "verified", "genuine", "authentic")
FORBIDDEN_WORDS_HI: tuple[str, ...] = ("सुरक्षित", "वैध", "सत्यापित", "असली", "प्रामाणिक")
_FORBIDDEN_ALL = FORBIDDEN_WORDS_EN + FORBIDDEN_WORDS_HI


def check_faithfulness(
    summary: str, items: list[EvidenceItemForLLM], has_verified_clearance: bool
) -> FaithfulnessResult:
    """Fail (ok=False) with a reason string for each problem:
    (a) "entity:<x>"   — a number (>= 3 digits, after removing commas), IFSC, UPI id, or a
        date in the summary that does not appear verbatim in any item.value (normalise:
        remove commas/spaces; '₹48,50,000' == '4850000').
    (b) "citation:<sentence #>" — a sentence with no [ev_...] citation, or citing an id that
        is not in items.
    (c) "forbidden:<word>" — any FORBIDDEN word (EN or HI, case-insensitive, whole word)
        unless has_verified_clearance is True.
    Sentence split: on '.', '!', '?', '।' followed by space or end.
    """
    failures: list[str] = []

    def _normalize(s: str) -> str:
        return s.replace(",", "").replace(" ", "")

    normalized_items = [_normalize(i.value) for i in items]
    valid_ids = {i.id for i in items}

    # (c) forbidden words
    if not has_verified_clearance:
        for w in _FORBIDDEN_ALL:
            if re.search(r"\b" + re.escape(w) + r"\b", summary, re.IGNORECASE):
                failures.append(f"forbidden:{w}")

    # (a) Entities extraction
    entities: list[str] = []
    entities.extend(re.findall(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", summary, re.IGNORECASE))
    entities.extend(
        re.findall(r"(?<![\w.\-])[\w.\-]+@[a-z]+(?![\w\-@]|\.\w)", summary, re.IGNORECASE)
    )
    entities.extend(re.findall(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b", summary))

    nums = re.findall(r"(?<![A-Za-z0-9])\d[\d,]*(?![A-Za-z0-9])", summary)
    for n in nums:
        clean = n.replace(",", "")
        if len(clean) >= 3:
            entities.append(clean)

    for ent in set(entities):
        norm_ent = _normalize(ent)
        if not any(norm_ent in val for val in normalized_items):
            failures.append(f"entity:{ent}")

    # (b) Citations
    sents = re.split(r"[.!?\u0964](?:\s+|$)", summary)
    for i, sent in enumerate(sents):
        sent = sent.strip()
        if not sent:
            continue
        cites = re.findall(r"\[(ev_[a-zA-Z0-9_\-]+)\]", sent)
        if not cites:
            failures.append(f"citation:{i + 1}")
        else:
            for c in cites:
                if c not in valid_ids:
                    failures.append(f"citation:{i + 1}")
                    break  # One bad citation is enough to fail the sentence

    return FaithfulnessResult(ok=len(failures) == 0, failures=failures)
