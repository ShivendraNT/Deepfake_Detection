"""T09 acceptance: storage adapter, intake (hash first), anchor job, fallback.
(The custody chain + tamper test are pre-implemented: tests/invariants/test_custody_chain.py)"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.contracts import Channel, CustodyEvent
from satyapan.settings import Settings
from satyapan.vault.anchor import anchor_head
from satyapan.vault.custody import CustodyLog
from satyapan.vault.hashing import sha256_bytes
from satyapan.vault.intake import intake
from satyapan.vault.storage import LocalStorage, get_storage

pytestmark = pytest.mark.task("T09")


def test_local_storage_roundtrip(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    uri = store.put("case_1/abc", b"hello", "text/plain")
    assert uri.startswith("file://") and store.get(uri) == b"hello"


@pytest.mark.parametrize("bad", ["../escape", "/abs/path", "a/../../b"])
def test_local_storage_rejects_traversal(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).put(bad, b"x", "text/plain")


def test_intake_hashes_stores_and_logs(tmp_path: Path) -> None:
    log, store = CustodyLog(), LocalStorage(tmp_path)
    data = b"From: x@y.example\r\n\r\nnot even a valid email"
    ev = intake(
        data,
        case_id="case_1",
        channel=Channel.EMAIL,
        filename="m.eml",
        media_type="message/rfc822",
        submitted_by="emp_priya",
        store=store,
        log=log,
    )
    sha = sha256_bytes(data)
    assert ev.sha256 == sha and ev.id == f"ev_{sha[:16]}" and ev.size_bytes == len(data)
    assert store.get(ev.storage_uri) == data
    rows = log.rows("case_1")
    assert rows[-1].event == CustodyEvent.INTAKE and rows[-1].payload["sha256"] == sha
    assert log.verify_chain().ok


def test_anchor_writes_head(tmp_path: Path) -> None:
    log, store = CustodyLog(), LocalStorage(tmp_path)
    log.append(case_id="case_1", event=CustodyEvent.INTAKE, actor="emp_priya")
    rec = anchor_head(log, store)
    assert rec.head_hash == log.head() and rec.seq == 1
    body = json.loads(store.get(rec.uri))
    assert body["head_hash"] == log.head()


def test_get_storage_local_by_default(tmp_path: Path) -> None:
    assert isinstance(get_storage(Settings(aws_mode=False, vault_dir=tmp_path)), LocalStorage)


def test_get_storage_falls_back_when_s3_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import satyapan.adapters.s3_store as s3

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("no credentials")

    monkeypatch.setattr(s3.S3Storage, "__init__", boom)
    store = get_storage(Settings(aws_mode=True, s3_bucket="demo-bucket", vault_dir=tmp_path))
    assert isinstance(store, LocalStorage)
