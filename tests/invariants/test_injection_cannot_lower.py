"""Injected text in evidence can never lower a band (policy layer, by construction)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.contracts import ReasonCode, Signal, SignalSource
from satyapan.policy import decide, rank

INJ = Path(__file__).resolve().parents[2] / "data" / "demo" / "injection" / "injections.jsonl"
INJECTIONS = [json.loads(line) for line in INJ.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("inj", INJECTIONS, ids=[i["id"] for i in INJECTIONS])
@pytest.mark.parametrize("case_id", ["case_s07", "case_s08", "case_s09", "case_s12"])
def test_injection_text_and_llm_reaction_never_lower(repo, master, inj, case_id) -> None:
    case = repo.get(case_id)
    before = decide(case, master)
    ev = (
        case.evidence[0].model_copy(update={"excerpt": inj["text"][:300]})
        if case.evidence
        else None
    )
    # Worst case: the LLM was fooled and emits an extra (capped) style signal or nothing at all.
    fooled = Signal.make(ReasonCode.STYLE_PRESSURE, source=SignalSource.LLM)
    attacked = case.model_copy(
        update={"evidence": [ev] if ev else [], "signals": [*case.signals, fooled]}
    )
    after = decide(attacked, master)
    assert rank(after.band) >= rank(before.band)
