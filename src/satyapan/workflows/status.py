"""Status changes, clearing, override. TASK T13 — docs/tasks/T13-callback-checker-flows.md.

Uses satyapan.policy.permissions (pre-implemented) for every role check.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from satyapan.contracts.case import Case, OverrideRecord
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import CaseStatus, Role
from satyapan.master.store import MasterData
from satyapan.policy.permissions import can_clear, can_set_status
from satyapan.workflows.callbacks import evaluate_clearance
from satyapan.workflows.watchlist import DEFAULT_WATCHLIST

_FRAUD_STATUSES = (CaseStatus.SUSPECTED_FRAUD, CaseStatus.CONFIRMED_FRAUD)


def clear_case(case: Case, *, actor_id: str, role: Role, master: MasterData, now: datetime) -> Case:
    """Set status CLEARED if can_clear(role, case.decision.band) and evaluate_clearance(...)
    is satisfied. Else raise PermissionError (role) or ValueError (requirements missing).
    The band itself is never changed."""
    if case.decision is None:
        raise ValueError(f"{case.id} has no decision yet")
    if not can_clear(role, case.decision.band):
        raise PermissionError(f"{role} cannot clear a {case.decision.band} case")
    status = evaluate_clearance(case, case.decision.clearance, master)
    if not status.satisfied:
        missing = ", ".join(m.value for m in status.missing)
        raise ValueError(
            f"clearance not met: {missing}" if missing else "clearance denied by callback outcome"
        )
    return case.model_copy(update={"status": CaseStatus.CLEARED})


def set_status(case: Case, new_status: CaseStatus, *, actor_id: str, role: Role) -> Case:
    """Allowed only if can_set_status(role, new_status). CONFIRMED_FRAUD can never be undone
    to OPEN/CLEARED. Setting SUSPECTED_FRAUD or CONFIRMED_FRAUD adds the sender domain and
    linked call ids to the watchlist (watchlist.add_from_case)."""
    if not can_set_status(role, new_status):
        raise PermissionError(f"{role} may not set status {new_status.value}")
    if case.status is CaseStatus.CONFIRMED_FRAUD and new_status is not CaseStatus.CONFIRMED_FRAUD:
        raise PermissionError("CONFIRMED_FRAUD is final; it can never be undone")
    if (
        new_status is CaseStatus.CLEARED
        and case.decision is not None
        and not can_clear(role, case.decision.band)
    ):
        raise PermissionError(f"{role} cannot clear a {case.decision.band} case")
    updated = case.model_copy(update={"status": new_status})
    if new_status in _FRAUD_STATUSES:
        DEFAULT_WATCHLIST.add_from_case(updated, utcnow())
    return updated


def acknowledge_security(case: Case, *, actor_id: str, role: Role) -> Case:
    """Only Role.SECURITY. Sets case.security_acknowledged_by = actor_id."""
    if role is not Role.SECURITY:
        raise PermissionError("only the security lead may acknowledge a case")
    return case.model_copy(update={"security_acknowledged_by": actor_id})


def request_override(
    case: Case, *, approver_ids: list[str], reason: str, master: MasterData, now: datetime
) -> Case:
    """Urgent legitimate payment override: two DISTINCT active senior approvers
    (master.senior_approvers()), reason >= 10 chars. Sets override (review_due_at = now + 48 h)
    and status OVERRIDDEN. Not allowed when status is SUSPECTED_FRAUD or CONFIRMED_FRAUD."""
    if case.status in _FRAUD_STATUSES:
        raise PermissionError(f"no override on a {case.status.value} case")
    if len(reason.strip()) < 10:
        raise ValueError("override reason must be at least 10 characters")
    if len(set(approver_ids)) < 2:
        raise ValueError("override needs two DISTINCT senior approvers")
    seniors = {e.employee_id for e in master.senior_approvers()}
    not_senior = [a for a in approver_ids if a not in seniors]
    if not_senior:
        raise ValueError(f"not an active senior approver: {', '.join(sorted(set(not_senior)))}")
    override = OverrideRecord(
        approver_ids=list(approver_ids),
        reason=reason,
        at=now,
        review_due_at=now + timedelta(hours=48),
    )
    return case.model_copy(update={"override": override, "status": CaseStatus.OVERRIDDEN})
