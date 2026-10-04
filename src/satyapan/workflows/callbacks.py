"""Callback logging and clearance evaluation. TASK T13.

Spec: docs/tasks/T13-callback-checker-flows.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from satyapan.contracts.case import CallbackRecord, Case, ClearanceRequirement
from satyapan.contracts.enums import CallbackOutcome, ClearanceMethod, Role
from satyapan.master.store import MasterData


class CallbackNumberError(ValueError):
    """Raised when someone logs a callback to a number that is NOT the trusted one."""


@dataclass
class ClearanceStatus:
    satisfied: bool
    done: list[ClearanceMethod] = field(default_factory=list)
    missing: list[ClearanceMethod] = field(default_factory=list)


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
    raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")


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
    raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")
