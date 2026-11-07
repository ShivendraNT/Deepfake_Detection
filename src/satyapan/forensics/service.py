"""Lab service: cases, evidence intake, the analysis queue, progress events and custody.

Forensic-integrity rules enforced here:
  * the SHA-256 (plus MD5 / SHA-1) is computed on the raw upload before anything parses it;
  * the original is stored write-once (read-only, named by its hash) and never modified;
  * before every analysis the stored file is re-hashed and compared with the intake hash;
    a mismatch stops the analysis and is written to the custody log;
  * every intake, analysis, re-analysis and report is a row in the hash-chained custody log.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from satyapan.contracts.enums import CustodyEvent
from satyapan.forensics.engine import analyze_bytes
from satyapan.forensics.filetype import hashes, sniff
from satyapan.forensics.links import compute_links
from satyapan.forensics.models import (
    EvidenceAnalysis,
    EvidenceRole,
    EvidenceStatus,
    LabCase,
    LabEvidence,
    ProgressEvent,
    utcnow,
)
from satyapan.forensics.registry import ModelRegistry, registry
from satyapan.forensics.store import LabStore
from satyapan.vault.hashing import canonical_json

MAX_UPLOAD_BYTES = 512 * 1024 * 1024


def new_case_id(now: datetime | None = None) -> str:
    now = now or utcnow()
    return f"case_{now:%Y%m%d}_{secrets.token_hex(3)}"


class LabService:
    def __init__(self, store: LabStore | None = None, models: ModelRegistry | None = None,
                 workers: int = 2) -> None:  # fmt: skip
        self.store = store or LabStore()
        self.models = models or registry()
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lab-analysis")
        self._events: dict[str, list[ProgressEvent]] = {}
        self._ev_lock = threading.Lock()
        self._pending: set[str] = set()

    # ------------------------------------------------------------------ events
    def emit(self, evidence_id: str, stage: str, message: str, progress: float,
             status: str = "running") -> None:  # fmt: skip
        ev = ProgressEvent(evidence_id=evidence_id, stage=stage, message=message,
                           progress=round(max(0.0, min(1.0, progress)), 3), status=status)  # fmt: skip
        with self._ev_lock:
            self._events.setdefault(evidence_id, []).append(ev)
            if len(self._events[evidence_id]) > 400:
                self._events[evidence_id] = self._events[evidence_id][-400:]

    def events(self, evidence_id: str, since: int = 0) -> list[ProgressEvent]:
        with self._ev_lock:
            return list(self._events.get(evidence_id, [])[since:])

    # ------------------------------------------------------------------ cases
    def create_case(self, actor: str = "examiner", **fields: Any) -> LabCase:
        now = utcnow()
        case = LabCase(id=fields.pop("id", None) or new_case_id(now), created_at=now, **fields)
        self.store.put_case(case)
        self.store.custody.append(case_id=case.id, event=CustodyEvent.STATUS_CHANGE, actor=actor,
                                  payload={"action": "case_opened", "title": case.title,
                                           "fir": case.fir_number})  # fmt: skip
        return case

    # ------------------------------------------------------------------ intake
    def _next_exhibit(self, case_id: str, role: EvidenceRole) -> str:
        prefix = "R" if role == EvidenceRole.REFERENCE else "Q"
        n = sum(1 for e in self.store.case_evidence(case_id) if e.exhibit.startswith(prefix))
        return f"{prefix}{n + 1}"

    def add_evidence(self, case_id: str, data: bytes, filename: str, *, actor: str = "examiner",
                     role: EvidenceRole = EvidenceRole.QUESTIONED, description: str = "",
                     received_from: str = "", analyze: bool = True) -> tuple[LabEvidence, bool]:  # fmt: skip
        """Returns (evidence, duplicate). The hash is taken before the bytes are parsed."""
        if self.store.case(case_id) is None:
            raise KeyError(case_id)
        if not data:
            raise ValueError("empty file")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(f"file larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        h = hashes(data)  # FIRST: fingerprint the raw bytes
        existing = self.store.find_sha(case_id, h.sha256)
        if existing is not None:
            return existing, True
        sn = sniff(data)
        safe_name = (filename or "evidence.bin").replace("\\", "/").rsplit("/", 1)[-1][:200]
        ev = LabEvidence(
            id=f"ev_{h.sha256[:12]}_{secrets.token_hex(2)}", case_id=case_id,
            exhibit=self._next_exhibit(case_id, role), filename=safe_name,
            size_bytes=h.size_bytes, md5=h.md5, sha1=h.sha1, sha256=h.sha256, kind=sn.kind,
            mime=sn.mime, role=role, description=description[:2000],
            received_from=received_from[:500], received_at=utcnow(),
        )  # fmt: skip
        path = self.store.write_once(case_id, h.sha256, data)
        self.store.put_evidence(ev)
        self.store.custody.append(
            case_id=case_id, event=CustodyEvent.INTAKE, actor=actor, evidence_id=ev.id,
            payload={"exhibit": ev.exhibit, "filename": safe_name, "sha256": h.sha256,
                     "md5": h.md5, "sha1": h.sha1, "size": h.size_bytes, "format": sn.format,
                     "role": role.value, "received_from": received_from[:200],
                     "stored": str(path.relative_to(self.store.root))},
        )  # fmt: skip
        self.emit(ev.id, "intake", f"received {safe_name}: SHA-256 {h.sha256[:16]}…", 0.0, "ok")
        if analyze:
            self.enqueue(ev.id, actor)
        return ev, False

    # ------------------------------------------------------------------ analysis
    def enqueue(self, evidence_id: str, actor: str = "examiner") -> None:
        if evidence_id in self._pending:
            return
        self._pending.add(evidence_id)
        ev = self.store.evidence(evidence_id)
        if ev is not None:
            ev.status = EvidenceStatus.QUEUED
            self.store.put_evidence(ev)
        self.emit(evidence_id, "queue", "queued for analysis", 0.0, "running")
        self.pool.submit(self._run_safe, evidence_id, actor)

    def _run_safe(self, evidence_id: str, actor: str) -> None:
        try:
            self.analyze_now(evidence_id, actor)
        except Exception as exc:  # noqa: BLE001 - surfaced as an event + status
            ev = self.store.evidence(evidence_id)
            if ev is not None:
                ev.status = EvidenceStatus.ERROR
                ev.headline = f"analysis failed: {type(exc).__name__}: {exc}"[:300]
                self.store.put_evidence(ev)
            self.emit(evidence_id, "done", f"analysis failed: {exc}", 1.0, "error")
        finally:
            self._pending.discard(evidence_id)

    def analyze_now(self, evidence_id: str, actor: str = "examiner") -> EvidenceAnalysis:
        ev = self.store.evidence(evidence_id)
        if ev is None:
            raise KeyError(evidence_id)
        path = self.store.evidence_path(ev.case_id, ev.sha256)
        data = path.read_bytes()
        now_sha = hashlib.sha256(data).hexdigest()
        if now_sha != ev.sha256:
            self.store.custody.append(
                case_id=ev.case_id, event=CustodyEvent.STATUS_CHANGE, actor="system",
                evidence_id=ev.id, payload={"action": "INTEGRITY_FAILURE", "expected": ev.sha256,
                                            "found": now_sha})  # fmt: skip
            ev.status = EvidenceStatus.ERROR
            ev.headline = "INTEGRITY FAILURE: stored file no longer matches its intake hash"
            self.store.put_evidence(ev)
            raise RuntimeError(ev.headline)
        self.emit(
            ev.id, "integrity", f"SHA-256 re-verified: {now_sha[:16]}… matches intake", 0.01, "ok"
        )
        ev.status = EvidenceStatus.ANALYZING
        self.store.put_evidence(ev)

        def progress(stage: str, message: str, frac: float, status: str) -> None:
            self.emit(ev.id, stage, message, 0.02 + 0.95 * frac, status)

        art = self.store.artifact_dir(ev.id)
        art.mkdir(parents=True, exist_ok=True)
        analysis, feats = analyze_bytes(data, ev.filename, art, models=self.models,
                                        evidence_id=ev.id, case_id=ev.case_id, path=path,
                                        role=ev.role.value, progress=progress)  # fmt: skip
        self.store.put_analysis(analysis, feats)
        self.emit(ev.id, "links", "comparing with other exhibits in the case", 0.98)
        self.refresh_links(ev)
        v = analysis.verdict
        ev.status = EvidenceStatus.DONE
        ev.verdict = v.label if v else None
        ev.risk_index = v.risk_index if v else None
        ev.headline = v.headline if v else None
        self.store.put_evidence(ev)
        digest = hashlib.sha256(
            canonical_json(analysis.model_dump(mode="json")).encode()
        ).hexdigest()
        self.store.custody.append(
            case_id=ev.case_id, event=CustodyEvent.ANALYSIS, actor=actor, evidence_id=ev.id,
            payload={"engine": analysis.engine_version, "verdict": v.label.value if v else None,
                     "risk_index": v.risk_index if v else None, "analysis_sha256": digest,
                     "techniques": len(analysis.techniques),
                     "input_sha256": now_sha},
        )  # fmt: skip
        self.emit(ev.id, "done", v.headline if v else "analysis complete", 1.0, "done")
        return analysis

    def refresh_links(self, ev: LabEvidence) -> None:
        peers = []
        for p in self.store.case_evidence(ev.case_id):
            if p.id == ev.id:
                continue
            f = self.store.features(p.id)
            if f:
                peers.append(
                    {"id": p.id, "exhibit": p.exhibit, "kind": p.kind.value, "features": f}
                )
        me = {"id": ev.id, "exhibit": ev.exhibit, "kind": ev.kind.value,
              "features": self.store.features(ev.id)}  # fmt: skip

        def load_rgb(eid: str) -> Any:
            import io

            import numpy as np
            from PIL import Image, ImageOps

            e = self.store.evidence(eid)
            assert e is not None
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(
                self.store.evidence_path(e.case_id, e.sha256).read_bytes()))).convert("RGB")  # fmt: skip
            return np.asarray(img)

        links = compute_links(me, peers, self.store.artifact_dir(ev.id), load_rgb)
        self.store.replace_links(ev.case_id, ev.id, links)

    # ------------------------------------------------------------------ views
    def case_view(self, case_id: str) -> dict[str, Any]:
        case = self.store.case(case_id)
        if case is None:
            raise KeyError(case_id)
        evs = self.store.case_evidence(case_id)
        counts: dict[str, int] = {}
        for e in evs:
            k = e.verdict.value if e.verdict else e.status.value
            counts[k] = counts.get(k, 0) + 1
        from satyapan.forensics.narrative import case_findings

        links = self.store.links(case_id)
        analyses = {e.id: self.store.analysis(e.id) for e in evs if e.verdict is not None}
        return {
            "case": case.model_dump(mode="json"),
            "evidence": [e.model_dump(mode="json") for e in evs],
            "links": [ln.model_dump(mode="json") for ln in links],
            "counts": counts,
            "reports": self.store.reports(case_id),
            "findings": case_findings(
                evs, analyses, links, self.store.custody.verify_chain().ok
            ),  # fmt: skip
        }

    def custody_view(self, case_id: str) -> dict[str, Any]:
        rows = self.store.custody.rows(case_id)
        chain = self.store.custody.verify_chain()
        return {"rows": [r.model_dump(mode="json") for r in rows],
                "chain": chain.model_dump(mode="json"), "head": self.store.custody.head()}  # fmt: skip

    def evidence_file(self, evidence_id: str) -> tuple[LabEvidence, Path]:
        ev = self.store.evidence(evidence_id)
        if ev is None:
            raise KeyError(evidence_id)
        return ev, self.store.evidence_path(ev.case_id, ev.sha256)


_SERVICE: LabService | None = None
_SERVICE_LOCK = threading.Lock()


def service() -> LabService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = LabService()
        return _SERVICE


def set_service(svc: LabService | None) -> None:
    global _SERVICE
    with _SERVICE_LOCK:
        _SERVICE = svc


def artifact_path(svc: LabService, evidence_id: str, name: str) -> Path:
    if "/" in name or "\\" in name or name.startswith("."):
        raise KeyError(name)
    p = svc.store.artifact_dir(evidence_id) / name
    if not p.exists():
        raise KeyError(name)
    return p


__all__ = ["LabService", "service", "set_service", "artifact_path", "Path"]
