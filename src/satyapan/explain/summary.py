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
    """1. template = explain_template(decision, lang)
    2. if llm is None -> return template
    3. items = evidence_items_from_case(case, decision); req = build_llm_request(...)
    4. text = llm.complete(req.system, req.user_json, req.max_tokens)  (any Exception -> template)
    5. result = check_faithfulness(text, items, has_verified_clearance)
    6. ok -> Explanation(source="llm", faithfulness=result) ; else template with faithfulness=result
    The band in the returned Explanation is ALWAYS decision.band (never parsed from LLM text).
    """
    template = explain_template(decision, lang)
    if llm is None:
        return template
    items = evidence_items_from_case(case, decision)
    req = build_llm_request(decision.band.value, lang, items)
    try:
        text = llm.complete(req.system, req.user_json, req.max_tokens)
    except Exception:  # any LLM failure (timeout, HTTP, model down) -> authoritative template
        return template
    result = check_faithfulness(text, items, has_verified_clearance)
    if not result.ok:
        return template.model_copy(update={"faithfulness": result})
    return Explanation(
        lang=lang,
        band=decision.band,  # never parsed from the LLM text
        text=text.strip(),
        source="llm",
        reason_codes=decision.reason_codes,
        faithfulness=result,
    )
