"""Custody chain is tamper-evident (vault core, pre-implemented)."""

from __future__ import annotations

from satyapan.contracts import CustodyEvent
from satyapan.vault.custody import CustodyLog
from satyapan.vault.hashing import sha256_bytes


def _log() -> CustodyLog:
    log = CustodyLog()
    for i in range(5):
        log.append(
            case_id="case_1",
            event=CustodyEvent.INTAKE,
            actor="emp_priya",
            evidence_id=f"ev_{i}",
            payload={"sha256": sha256_bytes(bytes([i]))},
        )
    return log


def test_chain_verifies() -> None:
    log = _log()
    assert log.verify_chain().ok and log.verify_chain().rows_checked == 5


def test_editing_a_row_breaks_the_chain() -> None:
    log = _log()
    log._tamper_for_tests(3, "attacker")
    v = log.verify_chain()
    assert not v.ok and v.broken_at_seq == 3


def test_sha256_known_vector() -> None:
    assert (
        sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
