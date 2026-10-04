"""Only humans with the right role move a case. The system never confirms fraud."""

from __future__ import annotations

from satyapan.contracts import Band, CaseStatus, Role
from satyapan.policy import can_clear, can_set_status, can_view_scores


def test_maker_cannot_clear_hold() -> None:
    assert not can_clear(Role.MAKER, Band.HOLD)
    assert can_clear(Role.CHECKER, Band.HOLD)
    assert can_clear(Role.MAKER, Band.VERIFY)


def test_confirmed_fraud_only_checker_or_security() -> None:
    allowed = {r for r in Role if can_set_status(r, CaseStatus.CONFIRMED_FRAUD)}
    assert allowed == {Role.CHECKER, Role.SECURITY}


def test_system_never_confirms_fraud_but_may_suspect() -> None:
    assert not can_set_status(Role.SYSTEM, CaseStatus.CONFIRMED_FRAUD)
    assert can_set_status(Role.SYSTEM, CaseStatus.SUSPECTED_FRAUD)


def test_scores_only_for_reviewers() -> None:
    assert {r for r in Role if can_view_scores(r)} == {Role.CHECKER, Role.SECURITY}
