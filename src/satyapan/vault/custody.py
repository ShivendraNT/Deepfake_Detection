"""Append-only custody log with a SHA-256 hash chain in SQLite. PRE-IMPLEMENTED (T09 core).

What this proves: "integrity since capture" and "tamper-evident custody log" — nothing about
where a file originally came from. The chain head is anchored externally (S3 Object Lock,
see anchor.py, T09) because a chain in our own DB alone is self-attested.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from satyapan.contracts.common import utcnow
from satyapan.contracts.custody import GENESIS_HASH, ChainVerification, CustodyRow
from satyapan.contracts.enums import CustodyEvent
from satyapan.vault.hashing import canonical_json, chain_hash

_SCHEMA = """
CREATE TABLE IF NOT EXISTS custody (
    seq INTEGER PRIMARY KEY,
    case_id TEXT NOT NULL,
    evidence_id TEXT,
    event TEXT NOT NULL,
    actor TEXT NOT NULL,
    at TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL
);
"""


def _hashable(row: CustodyRow) -> dict[str, Any]:
    d = row.model_dump(mode="json", exclude={"row_hash"})
    return d


class CustodyLog:
    """Usage:
    log = CustodyLog()                       # in-memory (tests)
    log = CustodyLog("vault_data/custody.db")  # on disk
    log.append(case_id="case_s07", event=CustodyEvent.INTAKE, actor="emp_priya",
               evidence_id="ev_1", payload={"sha256": "..."})
    assert log.verify_chain().ok
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def head(self) -> str:
        cur = self._db.execute("SELECT row_hash FROM custody ORDER BY seq DESC LIMIT 1")
        got = cur.fetchone()
        return str(got[0]) if got else GENESIS_HASH

    def last_seq(self) -> int:
        cur = self._db.execute("SELECT COALESCE(MAX(seq), 0) FROM custody")
        return int(cur.fetchone()[0])

    def append(
        self,
        *,
        case_id: str,
        event: CustodyEvent,
        actor: str,
        payload: dict[str, Any] | None = None,
        evidence_id: str | None = None,
        at: datetime | None = None,
    ) -> CustodyRow:
        prev = self.head()
        draft = CustodyRow(
            seq=self.last_seq() + 1,
            case_id=case_id,
            evidence_id=evidence_id,
            event=event,
            actor=actor,
            at=at or utcnow(),
            payload=json.loads(canonical_json(payload or {})),
            prev_hash=prev,
            row_hash="0" * 64,
        )
        row = draft.model_copy(update={"row_hash": chain_hash(prev, _hashable(draft))})
        self._db.execute(
            "INSERT INTO custody VALUES (?,?,?,?,?,?,?,?,?)",
            (
                row.seq,
                row.case_id,
                row.evidence_id,
                row.event.value,
                row.actor,
                row.at.isoformat(),
                canonical_json(row.payload),
                row.prev_hash,
                row.row_hash,
            ),
        )
        self._db.commit()
        return row

    def rows(self, case_id: str | None = None) -> list[CustodyRow]:
        q = (
            "SELECT seq, case_id, evidence_id, event, actor, at, payload, prev_hash, row_hash "
            "FROM custody"
        )
        args: tuple[Any, ...] = ()
        if case_id is not None:
            q += " WHERE case_id = ?"
            args = (case_id,)
        q += " ORDER BY seq"
        out = []
        for r in self._db.execute(q, args):
            out.append(
                CustodyRow(
                    seq=r[0],
                    case_id=r[1],
                    evidence_id=r[2],
                    event=CustodyEvent(r[3]),
                    actor=r[4],
                    at=datetime.fromisoformat(r[5]),
                    payload=json.loads(r[6]),
                    prev_hash=r[7],
                    row_hash=r[8],
                )
            )
        return out

    def verify_chain(self) -> ChainVerification:
        prev = GENESIS_HASH
        rows = self.rows()
        for row in rows:
            if row.prev_hash != prev:
                return ChainVerification(
                    ok=False,
                    rows_checked=row.seq,
                    broken_at_seq=row.seq,
                    reason="prev_hash mismatch",
                )
            if chain_hash(prev, _hashable(row)) != row.row_hash:
                return ChainVerification(
                    ok=False,
                    rows_checked=row.seq,
                    broken_at_seq=row.seq,
                    reason="row_hash mismatch",
                )
            prev = row.row_hash
        return ChainVerification(ok=True, rows_checked=len(rows))

    # Test helper: simulate an attacker editing the DB directly.
    def _tamper_for_tests(self, seq: int, actor: str) -> None:
        self._db.execute("UPDATE custody SET actor = ? WHERE seq = ?", (actor, seq))
        self._db.commit()
