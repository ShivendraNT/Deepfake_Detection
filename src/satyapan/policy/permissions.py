"""Who may do what. PRE-IMPLEMENTED (T02). Used by workflows (T12/T13) and API views.

Rules from docs/ARCHITECTURE.md §6 "Clearance":
- The maker can clear VERIFY, never HOLD.
- Only the checker clears HOLD (after their own callback, with security acknowledgement).
- CONFIRMED_FRAUD can be set only by the checker or security lead — never by the maker,
  never by the system.
- SUSPECTED_FRAUD can be set by checker/security, or by the system when OOB-Confirm is DENIED.
- Raw scores are visible only to checker/security (oracle-abuse mitigation).
"""

from __future__ import annotations

from satyapan.contracts.enums import Band, CaseStatus, Role

_CLEAR: dict[Band, frozenset[Role]] = {
    Band.PASS: frozenset({Role.MAKER, Role.CHECKER, Role.SECURITY}),
    Band.VERIFY: frozenset({Role.MAKER, Role.CHECKER}),
    Band.HOLD: frozenset({Role.CHECKER}),
}

_SET_STATUS: dict[CaseStatus, frozenset[Role]] = {
    CaseStatus.OPEN: frozenset({Role.CHECKER, Role.SECURITY}),
    CaseStatus.CLEARED: frozenset({Role.MAKER, Role.CHECKER}),  # band rules apply on top
    CaseStatus.SUSPECTED_FRAUD: frozenset({Role.CHECKER, Role.SECURITY, Role.SYSTEM}),
    CaseStatus.CONFIRMED_FRAUD: frozenset({Role.CHECKER, Role.SECURITY}),
    CaseStatus.OVERRIDDEN: frozenset({Role.CHECKER}),  # plus two senior approvers (T13)
}


def can_clear(role: Role, band: Band) -> bool:
    return role in _CLEAR[band]


def can_set_status(role: Role, status: CaseStatus) -> bool:
    return role in _SET_STATUS[status]


def can_view_scores(role: Role) -> bool:
    return role in (Role.CHECKER, Role.SECURITY)
