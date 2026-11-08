"""The lab's case store: SQLite for records, write-once files for evidence, and the existing
hash-chained custody log (satyapan.vault.custody) for every action.

Layout under SATYAPAN_LAB_DIR (default ./lab_data):
    lab.db                       cases, evidence, analyses, links, reports
    custody.db                   append-only SHA-256 hash chain
    evidence/<case>/<sha256>     original bytes, read-only, named by their hash
    artifacts/<evidence>/...     heatmaps, spectrograms, crops produced by the analysis
    reports/<case>/<report>.pdf  generated reports
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import threading
from pathlib import Path
from typing import Any

from satyapan.forensics.models import (
    EvidenceAnalysis,
    EvidenceLink,
    LabCase,
    LabEvidence,
)
from satyapan.vault.custody import CustodyLog

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, body TEXT NOT NULL, created_at TEXT);
CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
    sha256 TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_evidence_case ON evidence(case_id);
CREATE TABLE IF NOT EXISTS analyses (evidence_id TEXT PRIMARY KEY, body TEXT NOT NULL,
    features TEXT NOT NULL DEFAULT '{}', updated_at TEXT);
CREATE TABLE IF NOT EXISTS links (case_id TEXT NOT NULL, source TEXT NOT NULL,
    target TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY (source, target, kind));
CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
    body TEXT NOT NULL, created_at TEXT);
"""


def lab_dir() -> Path:
    return Path(os.environ.get("SATYAPAN_LAB_DIR", "lab_data")).resolve()


class LabStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or lab_dir()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.root / "lab.db"), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._db.commit()
        self._lock = threading.RLock()
        self._custody_lock = threading.Lock()
        self.custody = CustodyLog(self.root / "custody.db")

    def log(self, **kw: Any) -> Any:
        """Append a custody row. Serialised: the chain's next sequence number and previous hash
        are read and written as one step even when two analyses finish together."""
        with self._custody_lock:
            return self.custody.append(**kw)

    # ------------------------------------------------------------------ paths
    def evidence_path(self, case_id: str, sha256: str) -> Path:
        return self.root / "evidence" / case_id / sha256

    def artifact_dir(self, evidence_id: str) -> Path:
        return self.root / "artifacts" / evidence_id

    def report_path(self, case_id: str, report_id: str) -> Path:
        return self.root / "reports" / case_id / f"{report_id}.pdf"

    def write_once(self, case_id: str, sha256: str, data: bytes) -> Path:
        path = self.evidence_path(case_id, sha256)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
            os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        return path

    # ------------------------------------------------------------------ cases
    def put_case(self, case: LabCase) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO cases VALUES (?,?,?)",
                             (case.id, case.model_dump_json(), case.created_at.isoformat()))  # fmt: skip
            self._db.commit()

    def case(self, case_id: str) -> LabCase | None:
        row = self._db.execute("SELECT body FROM cases WHERE id=?", (case_id,)).fetchone()
        return LabCase.model_validate_json(row[0]) if row else None

    def cases(self) -> list[LabCase]:
        rows = self._db.execute("SELECT body FROM cases ORDER BY created_at DESC").fetchall()
        return [LabCase.model_validate_json(r[0]) for r in rows]

    def delete_case(self, case_id: str) -> None:
        """Only used to reset the demo case; real cases are never deleted through the API."""
        import shutil

        with self._lock:
            ids = [r[0] for r in self._db.execute("SELECT id FROM evidence WHERE case_id=?",
                                                   (case_id,))]  # fmt: skip
            for eid in ids:
                self._db.execute("DELETE FROM analyses WHERE evidence_id=?", (eid,))
                shutil.rmtree(self.artifact_dir(eid), ignore_errors=True)
            self._db.execute("DELETE FROM evidence WHERE case_id=?", (case_id,))
            self._db.execute("DELETE FROM links WHERE case_id=?", (case_id,))
            self._db.execute("DELETE FROM reports WHERE case_id=?", (case_id,))
            self._db.execute("DELETE FROM cases WHERE id=?", (case_id,))
            self._db.commit()
            ev_dir = self.root / "evidence" / case_id
            if ev_dir.exists():
                for f in ev_dir.iterdir():
                    os.chmod(f, stat.S_IWUSR | stat.S_IRUSR)
                shutil.rmtree(ev_dir, ignore_errors=True)
            shutil.rmtree(self.root / "reports" / case_id, ignore_errors=True)

    # ------------------------------------------------------------------ evidence
    def put_evidence(self, ev: LabEvidence) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?)",
                             (ev.id, ev.case_id, ev.sha256, ev.model_dump_json(),
                              ev.received_at.isoformat()))  # fmt: skip
            self._db.commit()

    def evidence(self, evidence_id: str) -> LabEvidence | None:
        row = self._db.execute("SELECT body FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        return LabEvidence.model_validate_json(row[0]) if row else None

    def case_evidence(self, case_id: str) -> list[LabEvidence]:
        rows = self._db.execute(
            "SELECT body FROM evidence WHERE case_id=? ORDER BY created_at", (case_id,)
        ).fetchall()
        return [LabEvidence.model_validate_json(r[0]) for r in rows]

    def find_sha(self, case_id: str, sha256: str) -> LabEvidence | None:
        row = self._db.execute("SELECT body FROM evidence WHERE case_id=? AND sha256=?",
                               (case_id, sha256)).fetchone()  # fmt: skip
        return LabEvidence.model_validate_json(row[0]) if row else None

    # ------------------------------------------------------------------ analyses
    def put_analysis(self, a: EvidenceAnalysis, features: dict[str, Any]) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO analyses VALUES (?,?,?,?)",
                             (a.evidence_id, a.model_dump_json(), json.dumps(features),
                              (a.finished_at or a.started_at).isoformat()))  # fmt: skip
            self._db.commit()

    def analysis(self, evidence_id: str) -> EvidenceAnalysis | None:
        row = self._db.execute("SELECT body FROM analyses WHERE evidence_id=?",
                               (evidence_id,)).fetchone()  # fmt: skip
        return EvidenceAnalysis.model_validate_json(row[0]) if row else None

    def features(self, evidence_id: str) -> dict[str, Any]:
        row = self._db.execute("SELECT features FROM analyses WHERE evidence_id=?",
                               (evidence_id,)).fetchone()  # fmt: skip
        return json.loads(row[0]) if row else {}

    # ------------------------------------------------------------------ links
    def replace_links(self, case_id: str, source: str, links: list[EvidenceLink]) -> None:
        with self._lock:
            self._db.execute("DELETE FROM links WHERE source=?", (source,))
            for ln in links:
                self._db.execute("INSERT OR REPLACE INTO links VALUES (?,?,?,?,?)",
                                 (case_id, ln.source, ln.target, ln.kind.value,
                                  ln.model_dump_json()))  # fmt: skip
            self._db.commit()

    def links(self, case_id: str) -> list[EvidenceLink]:
        rows = self._db.execute("SELECT body FROM links WHERE case_id=?", (case_id,)).fetchall()
        return [EvidenceLink.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------------------ reports
    def put_report(self, case_id: str, report_id: str, body: dict[str, Any]) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?)",
                             (report_id, case_id, json.dumps(body), body.get("created_at")))  # fmt: skip
            self._db.commit()

    def reports(self, case_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT body FROM reports WHERE case_id=? ORDER BY created_at DESC",
                                (case_id,)).fetchall()  # fmt: skip
        return [json.loads(r[0]) for r in rows]

    def report(self, report_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT body FROM reports WHERE id=?", (report_id,)).fetchone()
        return json.loads(row[0]) if row else None
