"""Faithfulness checker for LLM summaries. TASK T15 — docs/tasks/T15-llm-summary-faithfulness.md."""

from __future__ import annotations

import re

from satyapan.contracts.explain import EvidenceItemForLLM, FaithfulnessResult

FORBIDDEN_WORDS_EN: tuple[str, ...] = ("safe", "legitimate", "verified", "genuine", "authentic")
FORBIDDEN_WORDS_HI: tuple[str, ...] = ("सुरक्षित", "वैध", "सत्यापित", "असली", "प्रामाणिक")
# Reassurance phrases that slipped past the word list (judge red-team finding E3, 08 Oct).
# Same rule: blocked unless a verified clearance exists. Fail-closed: a faithful summary that
# happens to use one ("not approved") falls back to the template, which is acceptable.
FORBIDDEN_PHRASES_EN: tuple[str, ...] = (
    "no risk",
    "low risk",
    "risk-free",
    "fine to pay",
    "ok to pay",
    "okay to pay",
    "go ahead",
    "all clear",
    "approved",
    "nothing suspicious",
    "no red flags",
    "no concerns",
    "trustworthy",
    "sab theek",
    "koi risk nahi",
    "koi khatra nahi",
)
FORBIDDEN_PHRASES_HI: tuple[str, ...] = (
    "ठीक है",
    "सब ठीक",
    "कोई खतरा नहीं",
    "कोई जोखिम नहीं",
    "भरोसेमंद",
    "मंज़ूर",
    "मंजूर",
    "स्वीकृत",
)

_CITATION = re.compile(r"\[(ev_[A-Za-z0-9_\-]+)\]")
_SENTENCE_END = re.compile(r"(?<=[.!?।])(?:\s+|$)")
_DATE = re.compile(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b")
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_UPI = re.compile(r"(?<![\w.\-])[\w.\-]+@[a-z]+(?![\w\-@]|\.\w)")
_NUMBER = re.compile(r"\d[\d,]*")
# Devanagari vowel signs are not \w, so whole-word checks need explicit boundaries.
_WORD = r"\wऀ-ॿ"


def _norm(text: str) -> str:
    return re.sub(r"[,\s]", "", text)


def _sentences(summary: str) -> list[str]:
    """Split on . ! ? । followed by space or end. A fragment that is only citations (the model
    put them after the full stop) belongs to the sentence before it."""
    out: list[str] = []
    for part in _SENTENCE_END.split(summary):
        part = part.strip()
        if not part:
            continue
        if out and not _CITATION.sub("", part).strip(" .!?।"):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def _entities(text: str) -> list[str]:
    found: list[str] = []
    for pattern in (_DATE, _IFSC, _UPI):
        found += pattern.findall(text)
        text = pattern.sub(" ", text)
    found += [n for n in (m.replace(",", "") for m in _NUMBER.findall(text)) if len(n) >= 3]
    return found


def check_faithfulness(
    summary: str, items: list[EvidenceItemForLLM], has_verified_clearance: bool
) -> FaithfulnessResult:
    """Fail (ok=False) with a reason string for each problem:
    (a) "entity:<x>"   — a number (>= 3 digits, after removing commas), IFSC, UPI id, or a
        date in the summary that does not appear verbatim in any item.value (normalise:
        remove commas/spaces; '₹48,50,000' == '4850000').
    (b) "citation:<sentence #>" — a sentence with no [ev_...] citation, or citing an id that
        is not in items.
    (c) "forbidden:<word>" — any FORBIDDEN word or reassurance phrase (EN or HI,
        case-insensitive, whole word/phrase) unless has_verified_clearance is True.
    Sentence split: on '.', '!', '?', '।' followed by space or end.
    """
    failures: list[str] = []
    known_ids = {i.id for i in items}
    values = [_norm(i.value) for i in items]

    for x in _entities(_CITATION.sub(" ", summary)):
        if not any(_norm(x) in v for v in values):
            failures.append(f"entity:{x}")

    for n, sentence in enumerate(_sentences(summary), start=1):
        cited = _CITATION.findall(sentence)
        if not cited or any(c not in known_ids for c in cited):
            failures.append(f"citation:{n}")

    if not has_verified_clearance:
        for word in (
            FORBIDDEN_WORDS_EN + FORBIDDEN_WORDS_HI + FORBIDDEN_PHRASES_EN + FORBIDDEN_PHRASES_HI
        ):
            pattern = r"\s+".join(re.escape(w) for w in word.split())
            if re.search(rf"(?<![{_WORD}]){pattern}(?![{_WORD}])", summary, re.I):
                failures.append(f"forbidden:{word}")

    return FaithfulnessResult(ok=not failures, failures=list(dict.fromkeys(failures)))
