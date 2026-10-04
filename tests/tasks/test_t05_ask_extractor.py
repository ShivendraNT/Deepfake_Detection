"""T05 acceptance: deterministic ask extractor on >= 80 team-written sentences.
Sentences live in tests/tasks/data/t05_ask_sentences.jsonl (NEVER copy ICFD test rows)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.asks.extractor import ask_score, ask_signals, extract_asks
from satyapan.contracts import AskType, ReasonCode

pytestmark = pytest.mark.task("T05")

DATA = Path(__file__).parent / "data" / "t05_ask_sentences.jsonl"
ROWS = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]


def _found(text: str) -> set[str]:
    return {s.ask_type.value for s in extract_asks(text)}


def test_precision_recall_on_team_sentences() -> None:
    tp = fp = fn = 0
    for r in ROWS:
        got, want = _found(r["text"]), set(r["asks"])
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    print(f"\nT05 ask extractor: n={len(ROWS)} precision={precision:.3f} recall={recall:.3f}")
    assert len(ROWS) >= 80, "write at least 80 labelled sentences (EN + Hinglish + Devanagari)"
    assert precision >= 0.90 and recall >= 0.85


def test_every_ask_type_covered_in_three_scripts() -> None:
    extract_asks("warm-up")
    for at in AskType:
        langs = {r["lang"] for r in ROWS if at.value in r["asks"]}
        assert {"en", "hi-Latn"} <= langs, f"{at} needs English and romanised Hinglish sentences"
    assert sum(1 for r in ROWS if r["lang"] == "hi-Deva") >= 10


def test_spans_point_into_normalised_text() -> None:
    from satyapan.asks.extractor import normalise

    text = "Sir,   kisi ko mat batana.  OTP batao."
    norm = normalise(text)
    for s in extract_asks(text):
        assert norm[s.start : s.end] == s.text


def test_deterministic() -> None:
    t = "Keep this confidential and share the OTP."
    assert extract_asks(t) == extract_asks(t)


def test_devanagari_script_tag() -> None:
    spans = extract_asks("किसी को मत बताना")
    assert spans and spans[0].script == "devanagari"


def test_ask_signals_one_per_type() -> None:
    spans = extract_asks("OTP batao. OTP bhejo. Kisi ko mat batana.")
    sigs = ask_signals(spans, "ev_1")
    assert sorted(s.code for s in sigs) == sorted(
        [ReasonCode.ASK_CREDENTIAL, ReasonCode.ASK_SECRECY]
    )
    assert all(s.source == "deterministic" and s.evidence_ids == ["ev_1"] for s in sigs)


def test_ask_score_counts_distinct_types() -> None:
    assert ask_score("OTP batao. OTP bhejo. Kisi ko mat batana.") == 2
    assert ask_score("Invoice attached.") == 0
