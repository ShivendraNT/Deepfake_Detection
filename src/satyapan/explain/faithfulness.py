"""Faithfulness checker for LLM summaries. TASK T15 — docs/tasks/T15-llm-summary-faithfulness.md."""

from __future__ import annotations

from satyapan.contracts.explain import EvidenceItemForLLM, FaithfulnessResult

FORBIDDEN_WORDS_EN: tuple[str, ...] = ("safe", "legitimate", "verified", "genuine", "authentic")
FORBIDDEN_WORDS_HI: tuple[str, ...] = ("सुरक्षित", "वैध", "सत्यापित", "असली", "प्रामाणिक")


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
    raise NotImplementedError("T15: see docs/tasks/T15-llm-summary-faithfulness.md")
