"""Untrusted text is NEVER concatenated into the system prompt."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.contracts import Lang
from satyapan.explain.prompt import SYSTEM_PROMPT, build_llm_request, evidence_items_from_case
from satyapan.policy import decide

INJ = Path(__file__).resolve().parents[2] / "data" / "demo" / "injection" / "injections.jsonl"
INJECTIONS = [
    json.loads(line)["text"] for line in INJ.read_text(encoding="utf-8").splitlines() if line
]


@pytest.mark.parametrize("text", INJECTIONS)
def test_injection_only_in_user_json(repo, master, text: str) -> None:
    case = repo.get("case_s11")
    ev = case.evidence[0].model_copy(update={"excerpt": text[:300]})
    case = case.model_copy(update={"evidence": [ev]})
    items = evidence_items_from_case(case, decide(case, master))
    req = build_llm_request("VERIFY", Lang.EN, items)
    assert req.system == SYSTEM_PROMPT
    assert text[:40] not in req.system
    payload = json.loads(req.user_json)
    untrusted = [e for e in payload["evidence"] if e["source"] == "untrusted"]
    assert untrusted and all(len(e["value"]) <= 300 for e in untrusted)
    assert payload["band"] == "VERIFY"


def test_system_prompt_is_constant() -> None:
    import satyapan.explain.prompt as p

    assert isinstance(p.SYSTEM_PROMPT, str) and "{" not in p.SYSTEM_PROMPT
