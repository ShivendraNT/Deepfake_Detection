"""Status changes, clearing, override. TASK T13 — docs/tasks/T13-callback-checker-flows.md.

Uses satyapan.policy.permissions (pre-implemented) for every role check.
"""

from __future__ import annotations

from datetime import datetime

from satyapan.contracts.case import Case
from satyapan.contracts.enums import CaseStatus, Role
from satyapan.master.store import MasterData


def clear_case(case: Case, *, actor_id: str, role: Role, master: MasterData, now: datetime) -> Case:
    """Set status CLEARED if can_clear(role, case.decision.band) and evaluate_clearance(...)
    is satisfied. Else raise PermissionError (role) or ValueError (requirements missing).
    The band itself is never changed."""
    raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")


def set_status(case: Case, new_status: CaseStatus, *, actor_id: str, role: Role) -> Case:
    """Allowed only if can_set_status(role, new_status). CONFIRMED_FRAUD can never be undone
    to OPEN/CLEARED. Setting SUSPECTED_FRAUD or CONFIRMED_FRAUD adds the sender domain and
    linked call ids to the watchlist (watchlist.add_from_case)."""
    raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")


def acknowledge_security(case: Case, *, actor_id: str, role: Role) -> Case:
    """Only Role.SECURITY. Sets case.security_acknowledged_by = actor_id."""
    raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")


def request_override(
    case: Case, *, approver_ids: list[str], reason: str, master: MasterData, now: datetime
) -> Case:
    """Urgent legitimate payment override: two DISTINCT active senior approvers
    (master.senior_approvers()), reason >= 10 chars. Sets override (review_due_at = now + 48 h)
    and status OVERRIDDEN. Not allowed when status is SUSPECTED_FRAUD or CONFIRMED_FRAUD."""
    raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")
