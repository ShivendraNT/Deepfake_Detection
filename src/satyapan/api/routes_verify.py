"""Verification endpoints: OOB-Confirm (T12), callbacks/clear/status/override (T13).

The route glue is written; the domain functions it calls raise NotImplementedError until the
task is done, which the app turns into HTTP 501.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from satyapan.api.auth import Actor, get_actor, get_state
from satyapan.api.routes_cases import _get_case
from satyapan.api.state import AppState
from satyapan.api.views import case_view
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import CallbackOutcome, CaseStatus, CustodyEvent, Role
from satyapan.pipeline import recompute

router = APIRouter()
log = logging.getLogger(__name__)


def _notify_companion(state: AppState, case: Any, oob_req: Any, reason: str | None) -> None:
    """Fan the OOB answer into the companion bus. A UI failure must never fail the answer."""
    try:
        state.companion().note_oob_result(case, oob_req, reason)
    except Exception:  # noqa: BLE001 - best-effort relay, never block the approval path
        log.exception("companion OOB fan-in failed for case %s", getattr(case, "id", "?"))


class OOBCreate(BaseModel):
    requester_employee_id: str


class OOBRespond(BaseModel):
    token: str
    approve: bool
    # Saksham's third button: "I did not request this". Stronger than a plain reject.
    reason: Literal["not_requested"] | None = None


@router.post("/cases/{case_id}/oob")
def create_oob(
    case_id: str,
    body: OOBCreate,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    case = _get_case(state, case_id)
    requester = state.master.employee(body.requester_employee_id)
    if requester is None:
        raise HTTPException(status_code=404, detail="requester not in directory")
    oob_req, _token = state.oob().create(case, requester, actor.employee.name, utcnow())
    case = recompute(case.model_copy(update={"oob": oob_req}), state.master)
    state.repo.put(case, redecide=False)
    return {"oob_id": oob_req.id, "expires_at": oob_req.expires_at.isoformat()}


@router.get("/oob", response_class=HTMLResponse)
@router.get("/oob/app", response_class=HTMLResponse)
def oob_app() -> Any:
    """Serve the mobile-first approver phone page directly."""
    html_path = Path("console/public/oob.html")
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>Satya OOB Approver Page</h1>")


@router.get("/oob/inbox")
def oob_inbox(
    request: Request,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> Any:
    """In-app fallback inbox for the claimed requester (e.g. the CFO's second screen)."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        html_path = Path("console/public/oob.html")
        if html_path.exists():
            return FileResponse(html_path, media_type="text/html")
    return [m for m in state.in_app_mailer.outbox if m["to"] == actor.employee.email]


@router.post("/oob/respond")
def respond_oob(
    body: OOBRespond, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    from satyapan.workflows.oob import OOBError

    try:
        oob_req = state.oob().respond(
            body.token,
            body.approve and body.reason != "not_requested",
            actor.employee.employee_id,
            utcnow(),
        )
    except OOBError as e:
        raise HTTPException(status_code=409, detail=type(e).__name__) from e
    case = _get_case(state, oob_req.case_id)
    case = recompute(case.model_copy(update={"oob": oob_req}), state.master)
    state.repo.put(case, redecide=False)
    state.custody.append(
        case_id=case.id,
        event=CustodyEvent.STATUS_CHANGE,
        actor=actor.employee.employee_id,
        payload={"oob": oob_req.result.value, "reason": body.reason},
    )
    out: dict[str, Any] = {
        "result": oob_req.result.value,
        "case_band": case.decision.band if case.decision else None,
    }
    if body.reason == "not_requested":
        out["reason"] = "not_requested"
    _notify_companion(state, case, oob_req, body.reason)
    return out


class CallbackIn(BaseModel):
    number_dialed: str
    outcome: CallbackOutcome
    confirmed_by_name: str | None = None
    bank_shown_payee_name: str | None = None
    notes: str = ""


@router.post("/cases/{case_id}/callbacks")
def add_callback(
    case_id: str,
    body: CallbackIn,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    from satyapan.workflows.callbacks import CallbackNumberError, record_callback

    case = _get_case(state, case_id)
    try:
        rec = record_callback(
            case,
            master=state.master,
            performed_by=actor.employee.employee_id,
            performed_as=actor.role,
            number_dialed=body.number_dialed,
            outcome=body.outcome,
            confirmed_by_name=body.confirmed_by_name,
            bank_shown_payee_name=body.bank_shown_payee_name,
            now=utcnow(),
        )
    except CallbackNumberError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    case = case.model_copy(update={"callbacks": [*case.callbacks, rec]})
    state.repo.put(case, redecide=False)
    return case_view(case, actor.role)


@router.post("/cases/{case_id}/clear")
def clear(
    case_id: str, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    from satyapan.workflows.status import clear_case

    case = _get_case(state, case_id)
    try:
        case = clear_case(
            case,
            actor_id=actor.employee.employee_id,
            role=actor.role,
            master=state.master,
            now=utcnow(),
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    state.repo.put(case, redecide=False)
    return case_view(case, actor.role)


class StatusIn(BaseModel):
    status: CaseStatus


@router.post("/cases/{case_id}/status")
def change_status(
    case_id: str,
    body: StatusIn,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    from satyapan.workflows.status import set_status

    case = _get_case(state, case_id)
    try:
        case = set_status(case, body.status, actor_id=actor.employee.employee_id, role=actor.role)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    state.repo.put(case, redecide=False)
    state.custody.append(
        case_id=case.id,
        event=CustodyEvent.STATUS_CHANGE,
        actor=actor.employee.employee_id,
        payload={"status": body.status.value},
    )
    return case_view(case, actor.role)


@router.post("/cases/{case_id}/security-ack")
def security_ack(
    case_id: str, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    from satyapan.workflows.status import acknowledge_security

    if actor.role != Role.SECURITY:
        raise HTTPException(status_code=403, detail="security role only")
    case = acknowledge_security(
        _get_case(state, case_id), actor_id=actor.employee.employee_id, role=actor.role
    )
    state.repo.put(case, redecide=False)
    return case_view(case, actor.role)


class OverrideIn(BaseModel):
    approver_ids: list[str]
    reason: str


@router.post("/cases/{case_id}/override")
def override(
    case_id: str,
    body: OverrideIn,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    from satyapan.workflows.status import request_override

    try:
        case = request_override(
            _get_case(state, case_id),
            approver_ids=body.approver_ids,
            reason=body.reason,
            master=state.master,
            now=utcnow(),
        )
    except (PermissionError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    state.repo.put(case, redecide=False)
    return case_view(case, actor.role)
