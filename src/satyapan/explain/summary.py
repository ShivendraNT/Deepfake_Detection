"""LLM summary with template fallback. TASK T15."""

from __future__ import annotations

from satyapan.adapters.base import LLMClient
from satyapan.contracts.case import Case, Decision
from satyapan.contracts.enums import Lang
from satyapan.contracts.explain import Explanation


def summarize(
    case: Case,
    decision: Decision,
    lang: Lang,
    llm: LLMClient | None,
    has_verified_clearance: bool = False,
) -> Explanation:
    """1. template = explain_template(decision, lang)
    2. if llm is None -> return template
    3. items = evidence_items_from_case(case, decision); req = build_llm_request(...)
    4. text = llm.complete(req.system, req.user_json, req.max_tokens)  (any Exception -> template)
    5. result = check_faithfulness(text, items, has_verified_clearance)
    6. ok -> Explanation(source="llm", faithfulness=result) ; else template with faithfulness=result
    The band in the returned Explanation is ALWAYS decision.band (never parsed from LLM text).
    """
    raise NotImplementedError("T15: see docs/tasks/T15-llm-summary-faithfulness.md")
