"""Satyapan Forensic Lab API (/lab/api/...) and the dashboard (/lab).

Everything runs on this workstation: uploads are hashed, stored write-once and analysed
locally; no evidence leaves the machine.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, Field

from satyapan.forensics import catalogue
from satyapan.forensics.models import ENGINE_VERSION, EvidenceRole
from satyapan.forensics.service import artifact_path, service

router = APIRouter()
UI_DIR = Path(__file__).resolve().parents[1] / "forensics" / "ui"


def _actor(x_examiner: str | None) -> str:
    return (x_examiner or "examiner").strip()[:80] or "examiner"


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    fir_number: str = ""
    police_station: str = ""
    district: str = ""
    state: str = ""
    offence_sections: str = ""
    investigating_officer: str = ""
    examiner: str = ""
    lab_name: str = "Satyapan Multimedia Forensic Lab"
    summary: str = ""


@router.get("/lab/api/health")
def lab_health() -> dict[str, Any]:
    svc = service()
    return {"status": "ok", "engine": ENGINE_VERSION, "models": svc.models.status(),
            "lab_dir": str(svc.store.root), "techniques": len(catalogue.ALL)}  # fmt: skip


@router.get("/lab/api/techniques")
def lab_techniques() -> list[dict[str, Any]]:
    return [{"id": t.id, "name": t.name, "category": t.category.value,
             "kinds": [k.value for k in t.kinds], "method": t.method, "reference": t.reference,
             "limitations": t.limitations} for t in catalogue.ALL]  # fmt: skip


@router.get("/lab/api/cases")
def lab_cases() -> list[dict[str, Any]]:
    svc = service()
    out = []
    for c in svc.store.cases():
        evs = svc.store.case_evidence(c.id)
        out.append({**c.model_dump(mode="json"), "evidence_count": len(evs),
                    "flagged": sum(1 for e in evs if e.verdict and e.verdict.value in
                                   ("SYNTHETIC", "MANIPULATED", "SUSPICIOUS")),
                    "pending": sum(1 for e in evs if e.status.value in ("queued", "analyzing"))})  # fmt: skip
    return out


@router.post("/lab/api/cases", status_code=201)
def lab_create_case(body: CaseIn, x_examiner: str | None = Header(None)) -> dict[str, Any]:
    case = service().create_case(actor=_actor(x_examiner), **body.model_dump())
    return case.model_dump(mode="json")


@router.get("/lab/api/cases/{case_id}")
def lab_case(case_id: str) -> dict[str, Any]:
    try:
        return service().case_view(case_id)
    except KeyError as exc:
        raise HTTPException(404, "case not found") from exc


@router.post("/lab/api/cases/{case_id}/evidence", status_code=201)
async def lab_add_evidence(
    case_id: str,
    files: list[UploadFile] = File(...),
    role: str = Form("questioned"),
    description: str = Form(""),
    received_from: str = Form(""),
    x_examiner: str | None = Header(None),
) -> list[dict[str, Any]]:
    svc = service()
    if svc.store.case(case_id) is None:
        raise HTTPException(404, "case not found")
    try:
        r = EvidenceRole(role)
    except ValueError as exc:
        raise HTTPException(422, "role must be 'questioned' or 'reference'") from exc
    out = []
    for f in files:
        data = await f.read()
        try:
            ev, dup = await asyncio.to_thread(
                svc.add_evidence, case_id, data, f.filename or "evidence.bin",
                actor=_actor(x_examiner), role=r, description=description,
                received_from=received_from,
            )  # fmt: skip
        except ValueError as exc:
            raise HTTPException(422, f"{f.filename}: {exc}") from exc
        out.append({**ev.model_dump(mode="json"), "duplicate": dup})
    return out


@router.get("/lab/api/evidence/{evidence_id}")
def lab_evidence(evidence_id: str) -> dict[str, Any]:
    svc = service()
    ev = svc.store.evidence(evidence_id)
    if ev is None:
        raise HTTPException(404, "evidence not found")
    a = svc.store.analysis(evidence_id)
    links = [ln.model_dump(mode="json") for ln in svc.store.links(ev.case_id)
             if evidence_id in (ln.source, ln.target)]  # fmt: skip
    return {"evidence": ev.model_dump(mode="json"),
            "analysis": a.model_dump(mode="json") if a else None, "links": links,
            "events": [e.model_dump(mode="json") for e in svc.events(evidence_id)]}  # fmt: skip


@router.post("/lab/api/evidence/{evidence_id}/reanalyze", status_code=202)
def lab_reanalyze(evidence_id: str, x_examiner: str | None = Header(None)) -> dict[str, str]:
    svc = service()
    if svc.store.evidence(evidence_id) is None:
        raise HTTPException(404, "evidence not found")
    svc.enqueue(evidence_id, _actor(x_examiner))
    return {"status": "queued"}


@router.get("/lab/api/evidence/{evidence_id}/events")
async def lab_events(evidence_id: str, request: Request) -> StreamingResponse:
    svc = service()
    if svc.store.evidence(evidence_id) is None:
        raise HTTPException(404, "evidence not found")

    async def gen() -> Any:
        sent = 0
        idle = 0
        while True:
            if await request.is_disconnected():
                return
            evs = svc.events(evidence_id, sent)
            for e in evs:
                yield f"data: {e.model_dump_json()}\n\n"
                if e.stage == "done":
                    return
            sent += len(evs)
            ev = svc.store.evidence(evidence_id)
            if not evs and ev is not None and ev.status.value in ("done", "error") and sent == 0:
                yield f"data: {json.dumps({'evidence_id': evidence_id, 'stage': 'done', 'status': ev.status.value, 'message': ev.headline or '', 'progress': 1.0})}\n\n"
                return
            idle = 0 if evs else idle + 1
            if idle and idle % 60 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})  # fmt: skip


@router.get("/lab/api/evidence/{evidence_id}/file")
def lab_evidence_file(evidence_id: str) -> FileResponse:
    try:
        ev, path = service().evidence_file(evidence_id)
    except KeyError as exc:
        raise HTTPException(404, "evidence not found") from exc
    return FileResponse(path, media_type=ev.mime, filename=ev.filename,
                        content_disposition_type="inline")  # fmt: skip


@router.get("/lab/api/evidence/{evidence_id}/artifacts/{name}")
def lab_artifact(evidence_id: str, name: str) -> FileResponse:
    try:
        p = artifact_path(service(), evidence_id, name)
    except KeyError as exc:
        raise HTTPException(404, "artifact not found") from exc
    return FileResponse(p, media_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream")


@router.get("/lab/api/cases/{case_id}/custody")
def lab_custody(case_id: str) -> dict[str, Any]:
    svc = service()
    if svc.store.case(case_id) is None:
        raise HTTPException(404, "case not found")
    return svc.custody_view(case_id)


class ReportIn(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)
    examiner: str = ""
    designation: str = ""
    notes: str = ""


@router.post("/lab/api/cases/{case_id}/reports", status_code=201)
async def lab_make_report(case_id: str, body: ReportIn,
                          x_examiner: str | None = Header(None)) -> dict[str, Any]:  # fmt: skip
    from satyapan.forensics.report.builder import generate_report

    svc = service()
    if svc.store.case(case_id) is None:
        raise HTTPException(404, "case not found")
    try:
        rec = await asyncio.to_thread(generate_report, svc, case_id, body.evidence_ids,
                                      body.examiner or _actor(x_examiner), body.designation,
                                      body.notes, _actor(x_examiner))  # fmt: skip
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return rec


@router.get("/lab/api/reports/{report_id}.pdf")
def lab_report_pdf(report_id: str) -> FileResponse:
    svc = service()
    rec = svc.store.report(report_id)
    if rec is None:
        raise HTTPException(404, "report not found")
    p = svc.store.report_path(rec["case_id"], report_id)
    if not p.exists():
        raise HTTPException(404, "report file missing")
    return FileResponse(p, media_type="application/pdf", filename=f"{report_id}.pdf",
                        content_disposition_type="inline")  # fmt: skip


@router.get("/lab/api/cases/{case_id}/export.json")
def lab_export(case_id: str) -> JSONResponse:
    svc = service()
    try:
        view = svc.case_view(case_id)
    except KeyError as exc:
        raise HTTPException(404, "case not found") from exc
    view["analyses"] = {e["id"]: (a.model_dump(mode="json") if (a := svc.store.analysis(e["id"]))
                                  else None) for e in view["evidence"]}  # fmt: skip
    view["custody"] = svc.custody_view(case_id)
    return JSONResponse(view, headers={"Content-Disposition":
                                       f'attachment; filename="{case_id}_export.json"'})  # fmt: skip


@router.post("/lab/api/demo", status_code=201)
async def lab_demo(reset: bool = True) -> dict[str, Any]:
    from satyapan.forensics.demo import load_demo_case

    try:
        case = await asyncio.to_thread(load_demo_case, service(), reset)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return case


# ------------------------------------------------------------------ dashboard (built React app)


def _ui_index() -> Response:
    index = UI_DIR / "index.html"
    if not index.exists():
        return HTMLResponse(
            "<h1>Satyapan Forensic Lab</h1><p>The dashboard is not built. Run "
            "<code>cd lab && npm install && npm run build</code>. The API is at "
            "<a href='/docs'>/docs</a>.</p>", status_code=503)  # fmt: skip
    return FileResponse(index, media_type="text/html")


@router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse("/lab")


@router.get("/lab", include_in_schema=False)
def lab_index() -> Response:
    return _ui_index()


@router.get("/lab/{path:path}", include_in_schema=False)
def lab_static(path: str) -> Response:
    if path.startswith("api/"):
        raise HTTPException(404, "not found")
    target = (UI_DIR / path).resolve()
    if UI_DIR.exists() and target.is_file() and UI_DIR.resolve() in target.parents:
        return FileResponse(target)
    return _ui_index()  # client-side routes
