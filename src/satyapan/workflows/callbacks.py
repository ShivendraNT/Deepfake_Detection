"""Callback logging and clearance evaluation. TASK T13.

Spec: docs/tasks/T13-callback-checker-flows.md.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime

from satyapan.contracts.case import CallbackRecord, Case, ClearanceRequirement
from satyapan.contracts.enums import CallbackOutcome, ClearanceMethod, OOBResult, Role
from satyapan.master.store import MasterData
from satyapan.policy.clearance import resolve_callback_number


class CallbackNumberError(ValueError):
    """Raised when someone logs a callback to a number that is NOT the trusted one."""


@dataclass
class ClearanceStatus:
    satisfied: bool
    done: list[ClearanceMethod] = field(default_factory=list)
    missing: list[ClearanceMethod] = field(default_factory=list)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _norm_name(name: str) -> str:
    """Casefold, drop punctuation, expand the company suffixes our vendors use, collapse spaces."""
    s = re.sub(r"[^a-z0-9]+", " ", name.casefold())
    s = re.sub(r"\bpvt\b", "private", s)
    s = re.sub(r"\bltd\b", "limited", s)
    s = re.sub(r"\bllp\b", "limited liability partnership", s)
    return re.sub(r"\s+", " ", s).strip()


def record_callback(
    case: Case,
    *,
    master: MasterData,
    performed_by: str,
    performed_as: Role,
    number_dialed: str,
    outcome: CallbackOutcome,
    confirmed_by_name: str | None,
    bank_shown_payee_name: str | None,
    now: datetime,
) -> CallbackRecord:
    """Use satyapan.policy.clearance.resolve_callback_number(case, master, action) to get the
    trusted number. If number_dialed (digits only) != trusted number (digits only) ->
    raise CallbackNumberError. Return a CallbackRecord (id "cb_<hex>")."""
    if case.decision is None:
        raise ValueError(f"{case.id} has no decision yet")
    trusted, source = resolve_callback_number(case, master, case.decision.action_type)
    if trusted is None or source == "independent_source":
        raise CallbackNumberError(
            "no trusted callback number on file: obtain one from an independent source "
            "(vendor onboarding KYC) — never a number from the message, document or call"
        )
    if _digits(number_dialed) != _digits(trusted):
        raise CallbackNumberError(
            f"call back on the trusted number {trusted} ({source}), "
            "never on a number found in the message"
        )
    return CallbackRecord(
        id=f"cb_{secrets.token_hex(6)}",
        case_id=case.id,
        performed_by=performed_by,
        performed_as=performed_as,
        number_dialed=number_dialed,
        number_source=source,
        outcome=outcome,
        confirmed_by_name=confirmed_by_name,
        bank_shown_payee_name=bank_shown_payee_name,
        at=now,
    )


def _vendor_legal_name(case: Case, master: MasterData) -> str | None:
    if case.txn is not None:
        vendor = master.vendor(case.txn.vendor_id) or master.vendor_by_payee(
            case.txn.account_number, case.txn.ifsc, case.txn.upi_id
        )
    elif case.master_change is not None:
        vendor = master.vendor(case.master_change.vendor_id)
    else:
        vendor = None
    return vendor.legal_name if vendor is not None else None


def evaluate_clearance(
    case: Case, req: ClearanceRequirement, master: MasterData
) -> ClearanceStatus:
    """Which methods are done?
    - CALLBACK_MASTER_NUMBER: a CONFIRMED callback by maker or checker.
    - CHECKER_CALLBACK: a CONFIRMED callback performed_as CHECKER.
    - OOB_CONFIRM: case.oob.result == APPROVED.
    - BANK_NAME_MATCH: a callback (or txn) bank_shown_payee_name that matches the vendor's
      legal_name after normalising (casefold, drop punctuation, 'pvt'=='private', 'ltd'=='limited').
    - SECURITY_ACK: case.security_acknowledged_by is set.
    - SECOND_APPROVER: case.override has 2 approvers OR two distinct CONFIRMED callbacks.
    satisfied = all(done) if req.mode == "all" else any(done) (mode "none" -> True).
    A DENIED callback anywhere -> satisfied False."""
    confirmed = [c for c in case.callbacks if c.outcome is CallbackOutcome.CONFIRMED]
    denied = any(c.outcome is CallbackOutcome.DENIED for c in case.callbacks)
    legal_name = _vendor_legal_name(case, master)

    done: list[ClearanceMethod] = []
    for method in req.methods:
        if method is ClearanceMethod.CALLBACK_MASTER_NUMBER:
            met = any(c.performed_as in (Role.MAKER, Role.CHECKER) for c in confirmed)
        elif method is ClearanceMethod.CHECKER_CALLBACK:
            met = any(c.performed_as is Role.CHECKER for c in confirmed)
        elif method is ClearanceMethod.OOB_CONFIRM:
            met = case.oob is not None and case.oob.result is OOBResult.APPROVED
        elif method is ClearanceMethod.BANK_NAME_MATCH:
            met = legal_name is not None and any(
                c.bank_shown_payee_name is not None
                and _norm_name(c.bank_shown_payee_name) == _norm_name(legal_name)
                for c in confirmed
            )
        elif method is ClearanceMethod.SECURITY_ACK:
            met = case.security_acknowledged_by is not None
        elif method is ClearanceMethod.SECOND_APPROVER:
            met = (case.override is not None and len(set(case.override.approver_ids)) >= 2) or (
                len({c.performed_by for c in confirmed}) >= 2
            )
        else:  # pragma: no cover - exhaustive over the enum
            met = False
        if met:
            done.append(method)

    missing = [m for m in req.methods if m not in done]
    if denied:
        satisfied = False
    elif req.mode == "all":
        satisfied = not missing
    elif req.mode == "any":
        satisfied = bool(done)
    else:
        satisfied = True
    return ClearanceStatus(satisfied=satisfied, done=done, missing=missing)
