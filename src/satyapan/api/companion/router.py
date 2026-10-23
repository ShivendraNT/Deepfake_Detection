"""Companion REST + SSE router (T25).

Endpoints are thin: they authenticate the demo actor, call `CompanionService`, and map errors to
HTTP. No endpoint accepts a band or a raw score (see models.py). SSE is the only live channel.
"""

from __future__ import annotations

import os
import queue
import re
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from satyapan.api.auth import Actor, get_actor, get_state
from satyapan.api.companion.models import (
    CallStartRequest,
    CallStartResponse,
    CallStopRequest,
    CallStopResponse,
    CaseSummary,
    CommandRequest,
    CommandResponse,
    CompanionAuditFeed,
    CompanionEvent,
    CompanionOobRequest,
    CompanionStateSnapshot,
    DraftArtifact,
    DraftRequest,
    EvidenceSubmitRequest,
    EvidenceSubmitResponse,
    OobTicket,
    ReportPackV2,
    ScreenTextRequest,
    ScreenTextResponse,
    SessionStartRequest,
    SessionStartResponse,
    WorkspaceSnapshot,
)
from satyapan.api.companion.service import (
    CompanionError,
    CompanionNotFound,
    CompanionService,
    ConsentRequiredError,
)
from satyapan.api.state import AppState
from satyapan.contracts.enums import Role

router = APIRouter(prefix="/companion", tags=["companion"])


def _service(state: AppState) -> CompanionService:
    return state.companion()


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConsentRequiredError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
def health(state: AppState = Depends(get_state)) -> dict[str, object]:
    """Liveness plus the safety posture the desktop app displays on startup."""
    svc = _service(state)
    return {
        "status": "ok",
        "version": "1",
        "policy_authority": "satyapan.policy",
        "raw_scores_visible": False,
        "manual_only": True,
        "default_mode": "SLEEP",
        "bus": svc.bus.stats(),
        # Finale readiness: can Satya hear (speech engine) and judge voices (model files)?
        "asr": state.asr_status(),
        "voice_model": _voice_model_present(),
        "vendors": len(state.master.vendors),
    }


def _voice_model_present() -> bool:
    from pathlib import Path

    models = Path(__file__).resolve().parents[4] / "extension" / "models"
    return (models / "model.onnx").exists() and (models / "logreg_prob.onnx").exists()


@router.get("/state", response_model=CompanionStateSnapshot)
def state_snapshot(
    actor: Actor = Depends(get_actor), state: AppState = Depends(get_state)
) -> CompanionStateSnapshot:
    del actor
    return _service(state).snapshot()


@router.get("/cases", response_model=list[CaseSummary])
def cases(actor: Actor = Depends(get_actor), state: AppState = Depends(get_state)):
    del actor
    return _service(state).list_cases()


@router.post("/session/start", response_model=SessionStartResponse)
def start_session(
    request: SessionStartRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> SessionStartResponse:
    try:
        snapshot, events = _service(state).start_session(request, actor=actor.employee.employee_id)
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc
    return SessionStartResponse(state=snapshot, events=events)


@router.post("/session/stop", response_model=SessionStartResponse)
def stop_session(
    actor: Actor = Depends(get_actor), state: AppState = Depends(get_state)
) -> SessionStartResponse:
    snapshot, events = _service(state).stop_session(actor=actor.employee.employee_id)
    return SessionStartResponse(state=snapshot, events=events)


@router.post("/commands", response_model=CommandResponse)
def commands(
    request: CommandRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> CommandResponse:
    try:
        snapshot, events = _service(state).command(request, actor=actor.employee.employee_id)
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc
    return CommandResponse(
        request_id=request.request_id,
        accepted=True,
        state=snapshot,
        events=events,
    )


@router.post("/evidence", response_model=EvidenceSubmitResponse)
def submit_evidence(
    request: EvidenceSubmitRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> EvidenceSubmitResponse:
    try:
        return _service(state).submit_evidence(request, actor=actor.employee.employee_id)
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc


@router.post("/drafts", response_model=DraftArtifact)
def draft(
    request: DraftRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> DraftArtifact:
    try:
        return _service(state).draft(
            request.kind, request.case_id, actor=actor.employee.employee_id
        )
    except CompanionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CompanionError as exc:
        raise _http_error(exc) from exc


@router.get("/workspace", response_model=WorkspaceSnapshot)
def workspace(
    case_id: str | None = Query(default=None, pattern=r"^case_[A-Za-z0-9_\-]+$"),
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> WorkspaceSnapshot:
    del actor
    try:
        return _service(state).workspace(case_id)
    except CompanionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/calls/start", response_model=CallStartResponse)
def start_call(
    request: CallStartRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> CallStartResponse:
    """Start one listened call on an already-consented session (403 otherwise)."""
    try:
        call_id, case_id, events = _service(state).start_call(
            request, state, actor=actor.employee.employee_id
        )
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc
    return CallStartResponse(call_id=call_id, case_id=case_id, events=events)


@router.post("/calls/stop", response_model=CallStopResponse)
def stop_call(
    request: CallStopRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> CallStopResponse:
    try:
        call_id, snapshot, events = _service(state).stop_call(
            state, request.call_id, actor=actor.employee.employee_id
        )
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc
    return CallStopResponse(call_id=call_id, state=snapshot, events=events)


@router.post("/files", response_model=EvidenceSubmitResponse)
async def upload_file(
    file: UploadFile = File(...),
    case_id: str | None = Form(default=None),
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> EvidenceSubmitResponse:
    """Hand Satya one file. Hash first, then detectors; the policy engine sets the band."""
    data = await file.read()
    try:
        return _service(state).submit_file(
            state,
            filename=file.filename,
            media_type=file.content_type or "application/octet-stream",
            data=data,
            case_id=case_id,
            actor=actor.employee.employee_id,
        )
    except CompanionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc


@router.post("/oob", response_model=OobTicket)
def request_oob(
    request: CompanionOobRequest,
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> OobTicket:
    """Challenge the exact transaction with the approver from the directory."""
    try:
        return _service(state).request_oob(state, request.case_id, actor=actor.employee.employee_id)
    except CompanionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConsentRequiredError, CompanionError) as exc:
        raise _http_error(exc) from exc


@router.post("/text-check", response_model=ScreenTextResponse)
def text_check(
    request: ScreenTextRequest,
    source: str = Query(default="screen", pattern=r"^(screen|clipboard)$"),
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> ScreenTextResponse:
    """Screen Guard / clipboard check on text OCR'd or copied on this laptop. Not stored.

    Requires a consented session (Screen Guard is one of the consent scopes)."""
    del actor
    svc = _service(state)
    if svc.snapshot().session_id is None:
        raise HTTPException(status_code=403, detail="start a consented session first")
    finding = svc.check_text(request.text, app=request.app, source=source)
    return ScreenTextResponse(finding=finding)


@router.get("/replay/{name}")
def replay_audio(name: str) -> FileResponse:
    """The labelled DEMO REPLAY recording for the presenter fallback (local file, never real
    media). Generate it with `make demo-audio`, or drop a consented take with the same name."""
    from pathlib import Path

    if not re.fullmatch(r"[a-z0-9_]{1,64}\.wav", name):
        raise HTTPException(status_code=400, detail="bad replay name")
    root = Path(__file__).resolve().parents[4]
    folders = (
        [Path(os.environ["SATYAPAN_REPLAY_DIR"])] if os.environ.get("SATYAPAN_REPLAY_DIR") else []
    )
    for folder in [*folders, root / ".cache" / "replay"]:
        path = folder / name
        if path.is_file():
            return FileResponse(path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="replay audio missing: run `make demo-audio`")


@router.get("/report-pack", response_model=ReportPackV2)
def report_pack(
    case_id: str = Query(..., pattern=r"^case_[A-Za-z0-9_\-]+$"),
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
) -> ReportPackV2:
    del actor
    try:
        return _service(state).report_pack(case_id)
    except CompanionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit", response_model=CompanionAuditFeed)
def audit(
    actor: Actor = Depends(get_actor), state: AppState = Depends(get_state)
) -> CompanionAuditFeed:
    if actor.role not in {Role.CHECKER, Role.SECURITY}:
        raise HTTPException(status_code=403, detail="audit feed is checker/security only")
    return CompanionAuditFeed(rows=_service(state).audit())


def _sse(event: CompanionEvent) -> str:
    return f"id: {event.event_id}\nevent: {event.type.value}\ndata: {event.model_dump_json()}\n\n"


@router.get("/events")
def events(
    actor: Actor = Depends(get_actor),
    state: AppState = Depends(get_state),
    replay_only: bool = Query(default=False),
    heartbeat_seconds: Annotated[int, Query(ge=1, le=60)] = 15,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Server-sent events. `replay_only=true` drains history and closes (used by tests/UI)."""
    del actor
    bus = _service(state).bus
    subscriber = bus.subscribe()
    history = bus.history(last_event_id)

    def gen() -> Iterator[str]:
        seen: set[str] = set()
        try:
            for event in history:
                seen.add(event.event_id)
                yield _sse(event)
            if replay_only:
                return
            yield "retry: 3000\n\n"
            while True:
                try:
                    event = subscriber.get(timeout=heartbeat_seconds)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if event.event_id in seen:
                    continue
                seen.add(event.event_id)
                yield _sse(event)
        finally:
            bus.unsubscribe(subscriber)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
