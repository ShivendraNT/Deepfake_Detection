"""Report pack endpoint (T16). Returns DRAFTS only. There is deliberately no 'submit' route."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from satyapan.api.auth import Actor, get_actor, get_state
from satyapan.api.routes_cases import _get_case
from satyapan.api.state import AppState
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import CustodyEvent, Role

router = APIRouter()


@router.get("/cases/{case_id}/report", response_model=None)
def report(
    case_id: str,
    variant: Literal["ATTEMPTED", "MONEY_SENT"] = "ATTEMPTED",
    format: Literal["json", "html"] = "json",
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> Any:
    from satyapan.report.pack import ReportNotUnlockedError, build_report_pack, render_html

    if actor.role not in (Role.CHECKER, Role.SECURITY):
        raise HTTPException(status_code=403, detail="report pack: checker/security only")
    case = _get_case(state, case_id)
    try:
        pack = build_report_pack(
            case,
            state.master,
            state.custody.rows(case_id),
            variant,
            actor.employee.employee_id,
            utcnow(),
        )
    except ReportNotUnlockedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    state.custody.append(
        case_id=case_id,
        event=CustodyEvent.EXPORT,
        actor=actor.employee.employee_id,
        payload={"variant": variant, "format": format},
    )
    if format == "html":
        return HTMLResponse(render_html(pack))
    return JSONResponse(pack.model_dump(mode="json"))
