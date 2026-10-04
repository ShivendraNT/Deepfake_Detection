"""Small helpers shared by tests. Import with `from tests.helpers import ...`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from satyapan.contracts import Case, CaseKind, PaymentAction, PaymentRail, Signal

ROOT = Path(__file__).resolve().parents[1]
DEMO_DAY = datetime.fromisoformat("2026-10-05T10:00:00+05:30")


def require_artifact(rel_path: str, task: str) -> Path:
    """For tasks whose output is a FILE (results, figures, deck): skip until it exists."""
    p = ROOT / rel_path
    if not p.exists():
        raise NotImplementedError(f"{task}: expected artifact {rel_path} does not exist yet")
    return p


def require_not_stub(rel_path: str, task: str) -> str:
    """For JS/TS/HTML files: skip while the file still contains the marker `STUB(<task>)`."""
    p = ROOT / rel_path
    text = p.read_text(encoding="utf-8")
    if f"STUB({task})" in text:
        raise NotImplementedError(f"{task}: {rel_path} is still a stub")
    return text


def payment(
    *,
    vendor_id: str | None = "V001",
    amount: int = 100_000,
    account: str | None = "99990000001111",
    ifsc: str | None = "FAKA0000111",
    upi: str | None = None,
    requested_by: str | None = None,
    **extra: Any,
) -> PaymentAction:
    return PaymentAction(
        id="txn_test",
        vendor_id=vendor_id,
        beneficiary_name="Test Payee",
        account_number=account,
        ifsc=ifsc,
        upi_id=upi,
        amount_inr=amount,
        rail=PaymentRail.UPI if upi else PaymentRail.NEFT,
        requested_by_employee_id=requested_by,
        created_by="emp_priya",
        created_at=DEMO_DAY,
        **extra,
    )


def make_case(
    *,
    kind: CaseKind = CaseKind.PAYMENT,
    txn: PaymentAction | None = None,
    signals: list[Signal] | None = None,
    **extra: Any,
) -> Case:
    if kind == CaseKind.PAYMENT and txn is None:
        txn = payment()
    return Case(
        id="case_test",
        title="test",
        kind=kind,
        created_at=DEMO_DAY,
        created_by="emp_priya",
        txn=txn,
        signals=signals or [],
        **extra,
    )


def api_ok(response: Any, task: str) -> Any:
    """For API tests: HTTP 501 = 'task not implemented yet' -> skip (via NotImplementedError)."""
    if response.status_code == 501:
        raise NotImplementedError(f"{task}: endpoint returned 501 ({response.json().get('hint')})")
    return response
