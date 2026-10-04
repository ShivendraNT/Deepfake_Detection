"""Pydantic contract behaviour. These must always pass."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from satyapan.contracts import (
    LIVE_EVENT_ADAPTER,
    AskEvent,
    Case,
    Evidence,
    OverrideRecord,
    ReasonCode,
    ReportPack,
    Signal,
    SignalSource,
)
from tests.helpers import DEMO_DAY, payment


def test_signal_make_fills_from_table() -> None:
    s = Signal.make(
        ReasonCode.EMAIL_DMARC_FAIL, source=SignalSource.DETERMINISTIC, evidence_ids=["ev_1"]
    )
    assert s.group == "sender_auth" and s.strength == "strong"
    assert s.id.startswith("sig_")


def test_signal_rejects_hand_typed_wrong_group() -> None:
    with pytest.raises(ValidationError):
        Signal(
            id="sig_x",
            code=ReasonCode.EMAIL_DMARC_FAIL,
            group="style",
            target="VERIFY",
            strength="weak",
            source="deterministic",
        )


def test_llm_cannot_emit_deterministic_code() -> None:
    with pytest.raises(ValidationError):
        Signal.make(ReasonCode.ASK_CREDENTIAL, source=SignalSource.LLM)


def test_decision_only_codes_cannot_be_signals() -> None:
    with pytest.raises((ValidationError, KeyError)):
        Signal.make(ReasonCode.OOB_DENIED, source=SignalSource.HUMAN)


def test_payment_needs_payee() -> None:
    with pytest.raises(ValidationError):
        payment(account=None, ifsc=None, upi=None)


def test_ifsc_format_enforced() -> None:
    with pytest.raises(ValidationError):
        payment(ifsc="FAKA1000111")  # 5th char must be 0


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        payment(colour="blue")


def test_payment_case_needs_txn() -> None:
    with pytest.raises(ValidationError):
        Case(id="case_x", title="t", kind="PAYMENT", created_at=DEMO_DAY, created_by="emp_priya")


def test_override_needs_two_distinct_approvers() -> None:
    with pytest.raises(ValidationError):
        OverrideRecord(
            approver_ids=["emp_a", "emp_a"],
            reason="payroll deadline today",
            at=DEMO_DAY,
            review_due_at=DEMO_DAY,
        )


def test_excerpt_capped() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            id="ev_1",
            case_id="case_1",
            channel="email",
            sha256="a" * 64,
            size_bytes=1,
            captured_at=DEMO_DAY,
            submitted_by="emp_priya",
            storage_uri="file://x",
            excerpt="x" * 301,
        )


def test_live_event_union_parses_by_type() -> None:
    ev = LIVE_EVENT_ADAPTER.validate_python(
        {
            "type": "ask",
            "call_id": "c1",
            "chunk_index": 2,
            "ask_type": "A4",
            "reason_code": "ASK_SECRECY",
            "span_text": "kisi ko mat batana",
        }
    )
    assert isinstance(ev, AskEvent)


def test_report_pack_is_manual_only() -> None:
    field = ReportPack.model_fields["submission"]
    assert field.default == "MANUAL_ONLY"
    with pytest.raises(ValidationError):
        ReportPack.model_validate({"submission": "AUTO"})
