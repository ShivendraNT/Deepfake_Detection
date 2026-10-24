"""Case endpoints. GET routes PRE-IMPLEMENTED (T01). Upload depends on T09; explanation on T14."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from satyapan.api.auth import Actor, get_actor, get_state
from satyapan.api.state import AppState
from satyapan.api.views import case_summary, case_view
from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import CaseKind, Channel, CustodyEvent, Lang, Role
from satyapan.contracts.master import MasterChange
from satyapan.contracts.transaction import PaymentAction
from satyapan.pipeline import PipelineContext, analyze_evidence, merge_output, recompute

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/cases")
def list_cases(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [case_summary(c) for c in state.repo.all_cases()]


def _get_case(state: AppState, case_id: str) -> Case:
    case = state.repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@router.get("/cases/{case_id}")
def get_case(
    case_id: str, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    return case_view(_get_case(state, case_id), actor.role)


class CreateCaseRequest(BaseModel):
    title: str
    kind: CaseKind = CaseKind.PAYMENT
    txn: PaymentAction | None = None
    master_change: MasterChange | None = None


@router.post("/cases", status_code=201)
def create_case(
    body: CreateCaseRequest,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    if actor.role not in (Role.MAKER, Role.CHECKER):
        raise HTTPException(status_code=403, detail="only maker/checker create cases")
    case_id = f"case_{len(state.repo.cases) + 1:04d}"
    case = Case(
        id=case_id,
        title=body.title,
        kind=body.kind,
        created_at=utcnow(),
        created_by=actor.employee.employee_id,
        txn=body.txn,
        master_change=body.master_change,
    )
    case = state.repo.put(case)
    state.custody.append(
        case_id=case.id,
        event=CustodyEvent.DECISION,
        actor="system",
        payload={"band": case.decision.band.value if case.decision else None},
    )
    return case_view(case, actor.role)


@router.post("/cases/{case_id}/evidence")
async def upload_evidence(
    case_id: str,
    channel: Channel = Form(...),
    file: UploadFile = File(...),
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    """Hash first (T09 intake), then run detectors, then re-decide."""
    from satyapan.vault.intake import intake

    case = _get_case(state, case_id)
    data = await file.read()
    excerpt = None
    if channel in (Channel.WHATSAPP_TEXT, Channel.MANUAL):
        excerpt = data.decode("utf-8", errors="replace")[:300]
    ev = intake(
        data,
        case_id=case.id,
        channel=channel,
        filename=file.filename,
        media_type=file.content_type or "application/octet-stream",
        submitted_by=actor.employee.employee_id,
        store=state.store(),
        log=state.custody,
        excerpt=excerpt,
    )
    case = case.model_copy(update={"evidence": [*case.evidence, ev]})
    ctx = PipelineContext(
        master=state.master,
        settings=state.settings,
        thresholds=state.thresholds,
        transcriber=state.transcriber_override,
        text_model=state.text_model(),
        scorer=state.voice_scorer(),
    )
    out = analyze_evidence(data, ev, case, ctx)
    case = recompute(merge_output(case, ev, out), state.master)
    state.repo.put(case, redecide=False)
    state.custody.append(
        case_id=case.id,
        evidence_id=ev.id,
        event=CustodyEvent.ANALYSIS,
        actor="system",
        payload={"detector": out.detector, "version": out.version, "error": out.error},
    )
    return case_view(case, actor.role)


@router.get("/cases/{case_id}/explanation")
def explanation(
    case_id: str, lang: Lang = Lang.EN, state: AppState = Depends(get_state)
) -> dict[str, Any]:
    from satyapan.explain.templates import explain_template

    case = _get_case(state, case_id)
    if case.decision is None:
        raise HTTPException(status_code=409, detail="case has no decision")
    return explain_template(case.decision, lang).model_dump(mode="json")


@router.get("/cases/{case_id}/custody")
def custody(case_id: str, state: AppState = Depends(get_state)) -> dict[str, Any]:
    _get_case(state, case_id)
    rows = state.custody.rows(case_id)
    return {
        "rows": [r.model_dump(mode="json") for r in rows],
        "chain_head": state.custody.head(),
        "chain_ok": state.custody.verify_chain().ok,
    }


@router.get("/vendors")
def vendors(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [v.model_dump(mode="json") for v in state.master.vendors.values()]


@router.get("/employees")
def employees(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [
        {"employee_id": e.employee_id, "name": e.name, "title": e.title, "roles": e.roles}
        for e in state.master.employees.values()
    ]
