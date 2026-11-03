"""M1 tests: ForensicLocker case folders, read-only originals, working-copy isolation,
Ed25519-signed hash-chained custody log, RFC 6962 Merkle proofs, and tamper simulator."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from satyapan.forensics.locker import (
    ForensicLocker,
    is_readonly,
    root_from_path,
    sha256_bytes,
    sha256_file,
)


def test_case_layout_and_readonly_intake(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_m1_001"
    locker = ForensicLocker(
        case_dir,
        collector="examiner_arjun",
        case_meta={"title": "Extortion Video Case", "agency": "Cyber Crime Unit"},
    )
    assert (case_dir / "originals").is_dir()
    assert (case_dir / "working").is_dir()
    assert (case_dir / "artifacts").is_dir()
    assert locker.case_meta()["title"] == "Extortion Video Case"

    src = tmp_path / "suspect_photo.jpg"
    payload = b"\xff\xd8\xff\xe0" + b"forensic-test-bytes-" * 64 + b"\xff\xd9"
    src.write_bytes(payload)

    item = locker.intake(src, source_type="image", media_type="image/jpeg", device="phone-seized-1")
    assert item.evidence_id == "EV0001"
    assert item.sha256 == sha256_bytes(payload)
    assert item.size_bytes == len(payload)

    orig_path = Path(item.stored_path)
    assert orig_path.exists()
    assert orig_path.parent == (case_dir / "originals").resolve()
    assert is_readonly(orig_path)

    # Attempting to open the sealed original for writing must fail with PermissionError
    with pytest.raises(PermissionError):
        orig_path.write_bytes(b"overwrite")

    # Deduplication on identical file + device
    item_dup = locker.intake(
        src, source_type="image", media_type="image/jpeg", device="phone-seized-1"
    )
    assert item_dup.evidence_id == "EV0001"
    assert len(locker.items()) == 1


def test_working_copy_isolation_and_guard(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m1_work", collector="examiner_meera")
    item = locker.intake_bytes(
        b"raw-audio-bytes-1234567890",
        "call_recording.wav",
        source_type="audio",
        media_type="audio/wav",
    )
    orig_path = Path(item.stored_path)

    # Guard must reject direct analysis on originals/
    with pytest.raises(PermissionError, match="Forensic violation"):
        locker.assert_is_working_copy(orig_path)

    work_path = locker.checkout_working_copy(item.evidence_id, purpose="voice_and_splice_check")
    assert work_path.exists()
    assert work_path.parent == (tmp_path / "case_m1_work" / "working").resolve()
    assert sha256_file(work_path) == item.sha256
    assert locker.assert_is_working_copy(work_path) == work_path.resolve()

    # Modifying working copy does NOT affect sealed original or verify_all()
    work_path.write_bytes(b"scratch-working-modification")
    assert sha256_file(orig_path) == item.sha256
    assert is_readonly(orig_path)
    rep = locker.verify_all()
    assert rep.ok is True

    # Custody log recorded both intake and working_copy
    entries = locker.custody_entries()
    assert [e.action for e in entries] == ["intake", "working_copy"]


def test_signed_custody_chain_and_merkle_proofs(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m1_merkle", collector="examiner_priya")
    items = []
    for idx in range(5):  # odd number of leaves to exercise RFC 6962 split without leaf duplication
        it = locker.intake_bytes(
            f"evidence-payload-{idx}".encode(),
            f"item_{idx}.bin",
            source_type="document",
        )
        items.append(it)

    rep = locker.verify_all()
    assert rep.ok is True
    assert rep.anchor_ok is True
    assert rep.merkle_ok is True

    for it in items:
        proof = locker.audit_proof(it.evidence_id)
        assert proof["verified"] is True
        assert proof["file_intact"] is True
        assert proof["readonly_intact"] is True
        assert proof["record_included"] is True
        assert root_from_path(proof["leaf_hash"], proof["path"]) == locker.merkle_root()


def test_custody_tamper_and_signature_detection(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_m1_tamper"
    locker = ForensicLocker(case_dir, collector="examiner_rajesh")
    item1 = locker.intake_bytes(b"first-file-content-abcdef", "img1.jpg", source_type="image")
    locker.intake_bytes(b"second-file-content-123456", "img2.jpg", source_type="image")

    # 1. Simulate 1-bit file tamper on sealed copy
    assert locker.simulate_tamper(item1.evidence_id) is True
    rep_bad = locker.verify_all()
    assert rep_bad.ok is False
    assert item1.evidence_id in rep_bad.file_mismatches
    proof_bad = locker.audit_proof(item1.evidence_id)
    assert proof_bad["verified"] is False
    assert proof_bad["file_intact"] is False

    # Restore file tamper
    assert locker.restore_tamper(item1.evidence_id) is True
    assert locker.verify_all().ok is True

    # 2. Tamper with a custody log line (change actor without re-signing)
    lines = locker.custody_file.read_text(encoding="utf-8").splitlines()
    row0 = json.loads(lines[0])
    row0["actor"] = "attacker_forged"
    lines[0] = json.dumps(row0, sort_keys=True)
    locker.custody_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rep_chain = locker.verify_all()
    assert rep_chain.ok is False
    assert 1 in rep_chain.chain_breaks
    assert rep_chain.anchor_ok is False


def test_writable_original_detected_by_verify(tmp_path: Path) -> None:
    locker = ForensicLocker(tmp_path / "case_m1_perm", collector="examiner_1")
    item = locker.intake_bytes(b"immutable-bytes", "evidence.png", source_type="image")
    orig = Path(item.stored_path)
    orig.chmod(stat.S_IRUSR | stat.S_IWUSR)

    rep = locker.verify_all()
    assert rep.ok is False
    assert item.evidence_id in rep.writable_originals
    with pytest.raises(PermissionError, match="not read-only"):
        locker.checkout_working_copy(item.evidence_id)
