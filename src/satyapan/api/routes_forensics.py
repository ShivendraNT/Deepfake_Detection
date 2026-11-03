"""M5 — Explainable Multimedia Forensic Analysis Dashboard & REST API
(`src/satyapan/api/routes_forensics.py`).

Serves:
- `GET /forensics`: Self-contained offline Forensic Investigator Workstation UI;
- `GET /forensics/cases`: List forensic cases;
- `POST /forensics/cases`: Create a new forensic case;
- `POST /forensics/demo-case`: Seed and analyze the multi-modal demonstration case;
- `GET /forensics/cases/{case_id}`: Full case view (files, M2/M3/M4 findings + confidence + why +
  heatmaps/spectrograms, timeline, signed custody log + Merkle proofs, and limitations panel);
- `POST /forensics/cases/{case_id}/intake`: Upload & seal evidence -> working copy -> M2/M3/M4;
- `GET /forensics/cases/{case_id}/artifacts/{evidence_id}/{artifact_name}`: Serve PNG artifacts;
- `POST /forensics/cases/{case_id}/tamper-sim/{evidence_id}` & `.../tamper-restore/{evidence_id}`:
  Live 1-bit tamper simulation and restoration on sealed copies.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from satyapan.forensics.locker import ForensicLocker
from satyapan.forensics.pipeline import (
    analyze_evidence_item,
    infer_source_and_media_type,
    load_case_analysis,
    seed_demo_forensic_case,
)

router = APIRouter(tags=["forensics"])
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def get_forensic_cases_root(request: Request | None = None) -> Path:
    env_dir = os.environ.get("SATYAPAN_FORENSIC_CASES_DIR")
    if env_dir:
        p = Path(env_dir)
    elif request is not None and hasattr(request.app.state, "satyapan"):
        vault_dir = Path(request.app.state.satyapan.settings.vault_dir)
        p = vault_dir / "forensic_cases"
    else:
        p = Path("vault_data") / "forensic_cases"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _validate_id(val: str, kind: str = "case_id") -> str:
    if not _SAFE_ID_RE.match(val) or ".." in val:
        raise HTTPException(status_code=400, detail=f"Invalid {kind}: {val!r}")
    return val


class CreateForensicCaseRequest(BaseModel):
    case_id: str
    title: str = "Multimedia Forensic Investigation"
    agency: str = "Digital Forensics Laboratory"
    examiner: str = "examiner_arjun"
    fir_reference: str = ""


@router.get("/forensics/cases")
def list_forensic_cases(request: Request) -> dict[str, Any]:
    root = get_forensic_cases_root(request)
    cases: list[dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "case_meta.json").exists():
            locker = ForensicLocker(d)
            meta = locker.case_meta()
            rep = locker.verify_all()
            cases.append(
                {
                    "case_id": d.name,
                    "title": meta.get("title", d.name),
                    "agency": meta.get("agency", ""),
                    "examiner": meta.get("examiner", ""),
                    "evidence_count": len(locker.items()),
                    "integrity_ok": rep.ok,
                    "created_at_utc": meta.get("created_at_utc", ""),
                }
            )
    return {"cases": cases}


@router.post("/forensics/cases")
def create_forensic_case(body: CreateForensicCaseRequest, request: Request) -> dict[str, Any]:
    cid = _validate_id(body.case_id, "case_id")
    root = get_forensic_cases_root(request)
    locker = ForensicLocker(
        root / cid,
        collector=body.examiner,
        case_meta={
            "title": body.title,
            "agency": body.agency,
            "examiner": body.examiner,
            "fir_reference": body.fir_reference,
        },
    )
    return load_case_analysis(locker)


@router.post("/forensics/demo-case")
def load_or_seed_demo_case(request: Request) -> dict[str, Any]:
    root = get_forensic_cases_root(request)
    locker = seed_demo_forensic_case(root, "case_forensic_demo_01", use_heavy_models=False)
    return load_case_analysis(locker)


@router.get("/forensics/cases/{case_id}")
def get_forensic_case(case_id: str, request: Request) -> dict[str, Any]:
    cid = _validate_id(case_id, "case_id")
    root = get_forensic_cases_root(request)
    case_dir = root / cid
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail=f"Forensic case not found: {cid}")
    locker = ForensicLocker(case_dir)
    return load_case_analysis(locker)


@router.post("/forensics/cases/{case_id}/intake")
async def intake_forensic_evidence(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    device: str = Form("submitted-evidence"),
    make: str = Form(""),
    model: str = Form(""),
    os_name: str = Form(""),
    actor: str = Form("examiner_arjun"),
) -> dict[str, Any]:
    cid = _validate_id(case_id, "case_id")
    root = get_forensic_cases_root(request)
    case_dir = root / cid
    locker = ForensicLocker(case_dir, collector=actor)

    raw_bytes = await file.read()
    fname = file.filename or "evidence.bin"
    source_type, media_type = infer_source_and_media_type(fname)
    if file.content_type and file.content_type != "application/octet-stream":
        media_type = file.content_type

    dev_info: dict[str, Any] = {}
    if make:
        dev_info["make"] = make
    if model:
        dev_info["model"] = model
    if os_name:
        dev_info["os"] = os_name

    item = locker.intake_bytes(
        raw_bytes,
        fname,
        source_type=source_type,
        media_type=media_type,
        device=device,
        device_info=dev_info,
    )
    analyze_evidence_item(locker, item.evidence_id, use_heavy_models=False)
    # Rebuild case analysis.json
    from satyapan.forensics.pipeline import analyze_case

    return analyze_case(locker, use_heavy_models=False)


@router.get("/forensics/cases/{case_id}/artifacts/{evidence_id}/{artifact_name}")
def get_forensic_artifact(
    case_id: str,
    evidence_id: str,
    artifact_name: str,
    request: Request,
) -> FileResponse:
    cid = _validate_id(case_id, "case_id")
    eid = _validate_id(evidence_id, "evidence_id")
    aname = _validate_id(artifact_name, "artifact_name")
    root = get_forensic_cases_root(request)
    art_path = (root / cid / "artifacts" / eid / aname).resolve()
    base_dir = (root / cid / "artifacts").resolve()
    if not art_path.is_relative_to(base_dir) or not art_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(art_path, media_type="image/png")


@router.post("/forensics/cases/{case_id}/tamper-sim/{evidence_id}")
def simulate_case_tamper(case_id: str, evidence_id: str, request: Request) -> dict[str, Any]:
    cid = _validate_id(case_id, "case_id")
    eid = _validate_id(evidence_id, "evidence_id")
    root = get_forensic_cases_root(request)
    case_dir = root / cid
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    locker = ForensicLocker(case_dir)
    if not locker.simulate_tamper(eid):
        raise HTTPException(status_code=400, detail=f"Could not simulate tamper on {eid}")
    return load_case_analysis(locker)


@router.post("/forensics/cases/{case_id}/tamper-restore/{evidence_id}")
def restore_case_tamper(case_id: str, evidence_id: str, request: Request) -> dict[str, Any]:
    cid = _validate_id(case_id, "case_id")
    eid = _validate_id(evidence_id, "evidence_id")
    root = get_forensic_cases_root(request)
    case_dir = root / cid
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    locker = ForensicLocker(case_dir)
    if not locker.restore_tamper(eid):
        raise HTTPException(status_code=400, detail=f"Could not restore tamper on {eid}")
    return load_case_analysis(locker)


@router.get("/forensics/cases/{case_id}/report")
def export_forensic_case_report(
    case_id: str,
    request: Request,
    format: str = "pdf",
) -> Response:
    """Export the case forensic report as PDF, HTML, Markdown, or JSON (implemented in M6)."""
    cid = _validate_id(case_id, "case_id")
    root = get_forensic_cases_root(request)
    case_dir = root / cid
    if not case_dir.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    locker = ForensicLocker(case_dir)
    from satyapan.forensics.report import generate_forensic_report

    bundle = generate_forensic_report(locker)
    fmt = format.lower().strip()
    if fmt == "pdf":
        return Response(
            content=Path(bundle["pdf_path"]).read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{cid}_forensic_report.pdf"'},
        )
    if fmt == "html":
        return HTMLResponse(content=Path(bundle["html_path"]).read_text(encoding="utf-8"))
    if fmt in ("md", "markdown"):
        return Response(
            content=Path(bundle["md_path"]).read_text(encoding="utf-8"),
            media_type="text/markdown; charset=utf-8",
        )
    return Response(
        content=Path(bundle["json_path"]).read_text(encoding="utf-8"),
        media_type="application/json",
    )


FORENSICS_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Satyapan × Pramaan — Multimedia Forensic Analysis Workstation</title>
<style>
  :root {
    --bg: #0b0f17;
    --panel: #111827;
    --panel-alt: #1f2937;
    --border: #374151;
    --text: #f3f4f6;
    --muted: #9ca3af;
    --accent: #38bdf8;
    --danger: #ef4444;
    --warn: #f59e0b;
    --ok: #10b981;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.45;
  }
  header {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
    padding: 12px 20px; background: var(--panel); border-bottom: 1px solid var(--border); gap: 12px;
  }
  .brand { font-weight: 700; font-size: 16px; letter-spacing: 0.3px; }
  .brand span { color: var(--accent); font-weight: 600; font-size: 12px; margin-left: 8px; }
  .toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  button, select, input[type="text"] {
    background: var(--panel-alt); color: var(--text); border: 1px solid var(--border);
    padding: 6px 12px; border-radius: 6px; font-size: 13px; cursor: pointer;
  }
  button.primary { background: #0284c7; border-color: #0369a1; font-weight: 600; }
  button.danger { background: #991b1b; border-color: #ef4444; }
  button.ok { background: #065f46; border-color: #10b981; }
  .banner {
    padding: 10px 20px; font-size: 13px; font-weight: 600;
    display: flex; justify-content: space-between; align-items: center;
  }
  .banner.ok { background: rgba(16, 185, 129, 0.14); border-bottom: 1px solid var(--ok); color: #a7f3d0; }
  .banner.fail { background: rgba(239, 68, 68, 0.22); border-bottom: 1px solid var(--danger); color: #fecaca; }
  .workspace {
    display: grid; grid-template-columns: 320px 1fr; min-height: calc(100vh - 105px);
  }
  .sidebar {
    background: var(--panel); border-right: 1px solid var(--border); padding: 14px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .item-card {
    padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px;
    background: rgba(31, 41, 55, 0.55); cursor: pointer; transition: border-color 0.15s;
  }
  .item-card.active { border-color: var(--accent); background: rgba(56, 189, 248, 0.1); }
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600;
  }
  .badge.consistent_with_manipulation, .badge.consistent_with_synthetic, .badge.consistent_with_tampering {
    background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444;
  }
  .badge.anomalies_detected_verify {
    background: rgba(245, 158, 11, 0.2); color: #fde68a; border: 1px solid #f59e0b;
  }
  .badge.consistent_with_authentic, .badge.consistent_with_untampered, .badge.consistent_with_camera_or_authentic_origin {
    background: rgba(16, 185, 129, 0.2); color: #a7f3d0; border: 1px solid #10b981;
  }
  .main { padding: 18px 24px; overflow-y: auto; }
  .tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 16px; }
  .tab { background: transparent; border: 1px solid transparent; padding: 6px 14px; border-radius: 6px; }
  .tab.active { background: var(--panel-alt); border-color: var(--accent); color: var(--accent); font-weight: 600; }
  .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }
  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin-bottom: 14px;
  }
  .card h3 { margin: 0 0 8px 0; font-size: 15px; display: flex; justify-content: space-between; align-items: center; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #cbd5e1; word-break: break-all; }
  ul.why-list { margin: 8px 0; padding-left: 18px; font-size: 13px; }
  ul.why-list li { margin-bottom: 5px; }
  .artifacts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 10px; }
  .artifact-box { background: #090d14; border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; }
  .artifact-box img { max-width: 100%; border-radius: 4px; }
  .limits-panel {
    background: rgba(245, 158, 11, 0.08); border: 1px solid #d97706; border-radius: 8px; padding: 14px 16px;
  }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; }
</style>
</head>
<body>
<header>
  <div class="brand">
    SATYAPAN × PRAMAAN <span>Multimedia Evidence Authentication, Deepfake & Provenance Lab (Offline)</span>
  </div>
  <div class="toolbar">
    <select id="caseSelect" onchange="loadSelectedCase()"></select>
    <button class="primary" onclick="seedDemoCase()">Load Demo Case</button>
    <label style="background:#1f2937;border:1px solid #374151;padding:6px 12px;border-radius:6px;font-size:13px;cursor:pointer;">
      + Intake Evidence File
      <input type="file" id="fileInput" style="display:none" onchange="uploadEvidenceFile()"/>
    </label>
    <button onclick="downloadReport('pdf')">PDF Report + Sec 63</button>
    <button onclick="downloadReport('html')">HTML Report</button>
    <button onclick="downloadReport('json')">JSON</button>
  </div>
</header>

<div id="integrityBanner" class="banner ok">
  <span id="integrityText">Locker Integrity: Checking...</span>
  <span id="merkleText" class="mono"></span>
</div>

<div class="workspace">
  <aside class="sidebar">
    <div style="font-weight:700;font-size:13px;color:var(--muted);text-transform:uppercase;">
      Sealed Evidence Inventory (Read-Only Originals)
    </div>
    <div id="itemList"></div>
    <div class="limits-panel" style="margin-top:auto;font-size:12px;">
      <strong style="color:#fbbf24;">Forensic Decision Boundary</strong><br/>
      Findings are stated as <em>consistent with</em> or <em>inconsistent with</em> manipulation.
      Every detector runs on an isolated working copy; originals remain sealed (`0o444`).
      A human examiner signs the Section 63 BSA 2023 certificate.
    </div>
  </aside>

  <main class="main">
    <div class="tabs">
      <button class="tab active" onclick="setTab('findings', this)">1. Explainable Findings & Heatmaps</button>
      <button class="tab" onclick="setTab('timeline', this)">2. Chronological Timeline</button>
      <button class="tab" onclick="setTab('custody', this)">3. Signed Custody, Merkle Proof & Tamper Lab</button>
      <button class="tab" onclick="setTab('limits', this)">4. Limits of This Analysis</button>
    </div>
    <div id="tabContent"></div>
  </main>
</div>

<script>
let currentCase = null;
let selectedItemIdx = 0;
let activeTab = 'findings';

async function init() {
  const res = await fetch('/api/forensics/cases');
  const data = await res.json();
  if (!data.cases || data.cases.length === 0) {
    await seedDemoCase();
  } else {
    populateCaseSelect(data.cases, data.cases[0].case_id);
    await loadCase(data.cases[0].case_id);
  }
}

function populateCaseSelect(cases, activeId) {
  const sel = document.getElementById('caseSelect');
  sel.innerHTML = cases.map(c =>
    `<option value="${c.case_id}" ${c.case_id === activeId ? 'selected' : ''}>${c.case_id} (${c.evidence_count} items)</option>`
  ).join('');
}

async function seedDemoCase() {
  const res = await fetch('/api/forensics/demo-case', { method: 'POST' });
  currentCase = await res.json();
  const listRes = await fetch('/api/forensics/cases');
  const listData = await listRes.json();
  populateCaseSelect(listData.cases, currentCase.case_id);
  selectedItemIdx = 0;
  renderAll();
}

async function loadSelectedCase() {
  const cid = document.getElementById('caseSelect').value;
  if (cid) await loadCase(cid);
}

async function loadCase(caseId) {
  const res = await fetch(`/api/forensics/cases/${encodeURIComponent(caseId)}`);
  currentCase = await res.json();
  selectedItemIdx = 0;
  renderAll();
}

async function uploadEvidenceFile() {
  const inp = document.getElementById('fileInput');
  if (!inp.files || !inp.files[0] || !currentCase) return;
  const fd = new FormData();
  fd.append('file', inp.files[0]);
  fd.append('device', 'examiner-upload');
  const res = await fetch(`/api/forensics/cases/${encodeURIComponent(currentCase.case_id)}/intake`, {
    method: 'POST', body: fd
  });
  currentCase = await res.json();
  selectedItemIdx = currentCase.items.length - 1;
  inp.value = '';
  renderAll();
}

function downloadReport(fmt) {
  if (!currentCase) return;
  window.open(`/api/forensics/cases/${encodeURIComponent(currentCase.case_id)}/report?format=${fmt}`, '_blank');
}

async function toggleTamper(eid, isTampered) {
  if (!currentCase) return;
  const action = isTampered ? 'tamper-restore' : 'tamper-sim';
  const res = await fetch(`/api/forensics/cases/${encodeURIComponent(currentCase.case_id)}/${action}/${encodeURIComponent(eid)}`, {
    method: 'POST'
  });
  currentCase = await res.json();
  renderAll();
}

function setTab(tab, btn) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderMain();
}

function renderAll() {
  if (!currentCase) return;
  const integ = currentCase.integrity || {};
  const banner = document.getElementById('integrityBanner');
  const txt = document.getElementById('integrityText');
  const mtxt = document.getElementById('merkleText');
  if (integ.ok) {
    banner.className = 'banner ok';
    txt.textContent = `LOCKER INTEGRITY: PASSED · ${integ.evidence_count} Read-Only Originals Verified · ${integ.custody_entries} Ed25519 Signed Custody Entries`;
  } else {
    banner.className = 'banner fail';
    txt.textContent = `LOCKER INTEGRITY: TAMPERED / FAILED · Mismatched Files: ${(integ.file_mismatches || []).join(', ') || 'chain break'}`;
  }
  mtxt.textContent = `Merkle Root: ${(integ.merkle_root || '').slice(0, 24)}… | Chain Head: ${(integ.chain_head || '').slice(0, 24)}…`;

  const listEl = document.getElementById('itemList');
  listEl.innerHTML = (currentCase.items || []).map((it, idx) => `
    <div class="item-card ${idx === selectedItemIdx ? 'active' : ''}" onclick="selectedItemIdx=${idx};renderAll()">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
        <strong>${it.evidence_id} · ${it.original_name}</strong>
      </div>
      <div style="margin-bottom:6px;">
        <span class="badge ${it.overall_finding}">${it.overall_finding.replace(/_/g, ' ')}</span>
        <span style="font-size:11px;color:var(--muted);margin-left:6px;">Conf: ${(it.overall_confidence * 100).toFixed(0)}%</span>
      </div>
      <div class="mono" style="font-size:11px;color:var(--muted);">SHA-256: ${it.sha256.slice(0, 20)}…</div>
    </div>
  `).join('');

  renderMain();
}

function renderMain() {
  const el = document.getElementById('tabContent');
  if (!currentCase || !currentCase.items || currentCase.items.length === 0) {
    el.innerHTML = '<div class="card">No evidence items in this case yet.</div>';
    return;
  }
  const item = currentCase.items[selectedItemIdx] || currentCase.items[0];
  if (activeTab === 'findings') {
    const df = item.deepfake || {};
    const tm = item.tampering || {};
    const pr = item.provenance || {};
    const arts = item.artifact_files || {};
    const artHtml = Object.entries(arts).map(([label, fname]) => `
      <div class="artifact-box">
        <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:var(--accent);">${label.replace(/_/g, ' ').toUpperCase()}</div>
        <img src="/api/forensics/cases/${encodeURIComponent(currentCase.case_id)}/artifacts/${encodeURIComponent(item.evidence_id)}/${encodeURIComponent(fname)}"/>
      </div>
    `).join('');

    el.innerHTML = `
      <div class="card">
        <h3>
          <span>${item.evidence_id}: ${item.original_name} (${item.source_type.toUpperCase()})</span>
          <span class="badge ${item.overall_finding}">${item.overall_finding.replace(/_/g, ' ')} · Confidence ${(item.overall_confidence * 100).toFixed(1)}%</span>
        </h3>
        <p style="margin:6px 0 10px 0;font-size:14px;">${item.overall_statement}</p>
        <div class="mono">Sealed SHA-256: ${item.sha256} | Size: ${item.size_bytes.toLocaleString()} bytes | Source Device: ${item.device}</div>
        <h4 style="margin:12px 0 4px 0;font-size:13px;color:var(--accent);">Explainable Technical Indicators ("Why")</h4>
        <ul class="why-list">${(item.why || []).map(w => `<li>${w}</li>`).join('')}</ul>
      </div>

      <div class="grid-2">
        <div class="card">
          <h3><span>M2 · Deepfake & Synthetic Media Engine</span><span class="badge ${df.finding || ''}">${(df.finding || 'not_applicable').replace(/_/g, ' ')}</span></h3>
          <div style="font-size:13px;margin-bottom:8px;">${df.statement || 'Not applicable for this file type.'}</div>
          <div class="mono">Synthetic Likelihood: ${df.synthetic_probability ?? 'N/A'} | Models: ${(df.models_used || []).join(', ') || 'N/A'}</div>
        </div>
        <div class="card">
          <h3><span>M3 · Tampering & Manipulation Suite</span><span class="badge ${tm.finding || ''}">${(tm.finding || 'not_applicable').replace(/_/g, ' ')}</span></h3>
          <div style="font-size:13px;margin-bottom:8px;">${tm.statement || 'Not applicable for this file type.'}</div>
          <div class="mono">Tamper Likelihood: ${tm.tamper_probability ?? 'N/A'}</div>
        </div>
      </div>

      <div class="card">
        <h3>
          <span>M4 · Provenance, C2PA Content Credentials & Source Attribution</span>
          <span class="badge ${pr.finding || ''}">${pr.source_attribution || 'N/A'}</span>
        </h3>
        <div style="font-size:13px;margin-bottom:8px;">${pr.statement || 'Provenance summary unavailable.'}</div>
        <div class="mono">
          Attribution Probabilities: ${JSON.stringify(pr.attribution_probabilities || {})} |
          C2PA Status: ${(pr.c2pa && pr.c2pa.status) || 'none'}
        </div>
      </div>

      <div class="card">
        <h3>Visual Forensic Evidence (Heatmaps, Spectrum, Trajectory & Spectrogram)</h3>
        <div class="artifacts-grid">${artHtml || '<div style="color:var(--muted);">No visual artifacts for this item.</div>'}</div>
      </div>
    `;
  } else if (activeTab === 'timeline') {
    const rows = (currentCase.timeline || []).map(ev => `
      <tr>
        <td class="mono">${ev.time_utc}</td>
        <td><span class="badge">${ev.kind}</span></td>
        <td class="mono">${ev.evidence_id || ''}</td>
        <td>${ev.actor || ''}</td>
        <td>${ev.description || ''}</td>
      </tr>
    `).join('');
    el.innerHTML = `
      <div class="card">
        <h3>Chronological Case & Metadata Timeline</h3>
        <table>
          <thead><tr><th>Timestamp (UTC)</th><th>Type</th><th>Evidence</th><th>Actor/Source</th><th>Event</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  } else if (activeTab === 'custody') {
    const integ = currentCase.integrity || {};
    const tsim = integ.tamper_simulation || {};
    const isTampered = Boolean(tsim[item.evidence_id]);
    const proof = (currentCase.merkle_proofs || {})[item.evidence_id] || {};
    const cRows = (currentCase.custody_log || []).map(c => `
      <tr>
        <td>#${c.seq}</td>
        <td class="mono">${c.evidence_id}</td>
        <td><strong>${c.action}</strong></td>
        <td>${c.actor}</td>
        <td class="mono">${c.link.slice(0, 16)}…</td>
        <td class="mono">${c.signature.slice(0, 16)}…</td>
        <td>${c.notes}</td>
      </tr>
    `).join('');
    el.innerHTML = `
      <div class="card">
        <h3>
          <span>Interactive Tamper Simulator & RFC 6962 Merkle Inclusion Proof (${item.evidence_id})</span>
          <button class="${isTampered ? 'ok' : 'danger'}" onclick="toggleTamper('${item.evidence_id}', ${isTampered})">
            ${isTampered ? 'Restore Sealed Copy Byte' : 'Simulate 1-Bit Tamper on Sealed Copy'}
          </button>
        </h3>
        <div class="mono" style="margin-bottom:8px;">
          Recorded SHA-256: ${proof.recorded_sha256 || ''}<br/>
          Current On-Disk SHA-256: ${proof.current_sha256 || ''}<br/>
          File Intact: ${proof.file_intact} | Read-Only (0o444): ${proof.readonly_intact} | Merkle Inclusion Verified: ${proof.verified}
        </div>
      </div>
      <div class="card">
        <h3>Ed25519-Signed Hash-Chained Custody Log (custody.jsonl)</h3>
        <table>
          <thead><tr><th>Seq</th><th>Evidence</th><th>Action</th><th>Signer</th><th>Chain Link</th><th>Ed25519 Sig</th><th>Notes</th></tr></thead>
          <tbody>${cRows}</tbody>
        </table>
      </div>
    `;
  } else {
    const lims = (currentCase.limitations_of_analysis || []).map(l => `<li>${l}</li>`).join('');
    el.innerHTML = `
      <div class="limits-panel">
        <h3 style="margin-top:0;color:#fbbf24;">Limits of This Analysis & Scientific Disclaimers</h3>
        <ul class="why-list" style="font-size:13.5px;">${lims}</ul>
      </div>
    `;
  }
}

init();
</script>
</body>
</html>
"""


@router.get("/forensics", response_class=HTMLResponse)
def forensics_dashboard_page() -> HTMLResponse:
    return HTMLResponse(content=FORENSICS_DASHBOARD_HTML)
