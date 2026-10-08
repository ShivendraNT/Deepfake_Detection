"""LLM summary with template fallback. TASK T15."""

from __future__ import annotations

from satyapan.adapters.base import LLMClient
from satyapan.contracts.case import Case, Decision
from satyapan.contracts.enums import Lang
from satyapan.contracts.explain import Explanation
from satyapan.explain.faithfulness import check_faithfulness
from satyapan.explain.prompt import build_llm_request, evidence_items_from_case
from satyapan.explain.templates import explain_template


def summarize(
    case: Case,
    decision: Decision,
    lang: Lang,
    llm: LLMClient | None,
    has_verified_clearance: bool = False,
) -> Explanation:
    template = explain_template(decision, lang)
    if llm is None:
        return template

    items = evidence_items_from_case(case, decision)
    req = build_llm_request(decision.band.value, lang, items)

    try:
        text = llm.complete(req.system, req.user_json, req.max_tokens)
    except Exception:
        return template

    result = check_faithfulness(text, items, has_verified_clearance)
    if result.ok:
        return Explanation(
            lang=lang,
            band=decision.band,
            text=text,
            source="llm",
            reason_codes=template.reason_codes,
            faithfulness=result,
        )
    else:
        template.faithfulness = result
        return template
