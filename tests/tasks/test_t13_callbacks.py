"""T13 acceptance: callback logging, clearance, role rules, override, watchlist."""

from __future__ import annotations

from datetime import timedelta

import pytest

from satyapan.contracts import CallbackOutcome, CaseStatus, ClearanceMethod, Role
from satyapan.workflows.callbacks import CallbackNumberError, evaluate_clearance, record_callback
from satyapan.workflows.status import acknowledge_security, clear_case, request_override, set_status
from satyapan.workflows.watchlist import Watchlist
from tests.helpers import DEMO_DAY

pytestmark = pytest.mark.task("T13")


def _cb(
    case,
    master,
    *,
    number="+91-00000-10002",
    role=Role.MAKER,
    by="emp_priya",  # type: ignore[no-untyped-def]
    outcome=CallbackOutcome.CONFIRMED,
    name="Narmada Demo Logistics LLP",
):
    return record_callback(
        case,
        master=master,
        performed_by=by,
        performed_as=role,
        number_dialed=number,
        outcome=outcome,
        confirmed_by_name="Accounts head",
        bank_shown_payee_name=name,
        now=DEMO_DAY,
    )


def test_callback_must_use_master_number(repo, master) -> None:
    case = repo.get("case_s07")
    assert _cb(case, master, number="+91 00000 10002").number_source == "vendor_master_old"
    with pytest.raises(CallbackNumberError):
        _cb(case, master, number="+91-98765-43210")  # number from the attacker's email


def test_c1_needs_callback_and_bank_name_match(repo, master) -> None:
    case = repo.get("case_s07")
    req = case.decision.clearance
    ok = case.model_copy(
        update={
            "callbacks": [
                _cb(case, master, name="Narmada Demo Logistics Limited Liability Partnership")
            ]
        }
    )
    ok2 = case.model_copy(
        update={"callbacks": [_cb(case, master, name="NARMADA DEMO LOGISTICS LLP")]}
    )
    bad = case.model_copy(update={"callbacks": [_cb(case, master, name="Narmada Traders")]})
    assert evaluate_clearance(ok2, req, master).satisfied
    st = evaluate_clearance(bad, req, master)
    assert not st.satisfied and ClearanceMethod.BANK_NAME_MATCH in st.missing
    assert isinstance(evaluate_clearance(ok, req, master).satisfied, bool)


def test_denied_callback_never_clears(repo, master) -> None:
    case = repo.get("case_s07")
    case = case.model_copy(
        update={"callbacks": [_cb(case, master, outcome=CallbackOutcome.DENIED)]}
    )
    assert not evaluate_clearance(case, case.decision.clearance, master).satisfied


def test_maker_cannot_clear_hold(repo, master) -> None:
    case = repo.get("case_s08")
    with pytest.raises(PermissionError):
        clear_case(case, actor_id="emp_priya", role=Role.MAKER, master=master, now=DEMO_DAY)


def test_checker_clears_hold_after_callback_and_security_ack(repo, master) -> None:
    case = repo.get("case_s08")
    cb = _cb(
        case,
        master,
        number="+91-00000-10001",
        role=Role.CHECKER,
        by="emp_arjun",
        name="Kaveri Demo Packaging Pvt Ltd",
    )
    case = case.model_copy(update={"callbacks": [cb]})
    with pytest.raises(ValueError):
        clear_case(case, actor_id="emp_arjun", role=Role.CHECKER, master=master, now=DEMO_DAY)
    case = acknowledge_security(case, actor_id="emp_meera", role=Role.SECURITY)
    case = clear_case(case, actor_id="emp_arjun", role=Role.CHECKER, master=master, now=DEMO_DAY)
    assert case.status == CaseStatus.CLEARED and case.decision.band == "HOLD"  # band unchanged


def test_status_permissions(repo) -> None:
    case = repo.get("case_s08")
    with pytest.raises(PermissionError):
        set_status(case, CaseStatus.CONFIRMED_FRAUD, actor_id="emp_priya", role=Role.MAKER)
    assert (
        set_status(case, CaseStatus.CONFIRMED_FRAUD, actor_id="emp_arjun", role=Role.CHECKER).status
        == CaseStatus.CONFIRMED_FRAUD
    )


def test_override_two_distinct_senior_approvers(repo, master) -> None:
    case = repo.get("case_s05")
    done = request_override(
        case,
        approver_ids=["emp_rajesh", "emp_sunil"],
        reason="Payroll vendor deadline today",
        master=master,
        now=DEMO_DAY,
    )
    assert done.status == CaseStatus.OVERRIDDEN
    assert done.override.review_due_at - DEMO_DAY == timedelta(hours=48)
    for bad in (["emp_rajesh", "emp_rajesh"], ["emp_priya", "emp_rajesh"]):
        with pytest.raises(ValueError):
            request_override(
                case,
                approver_ids=bad,
                reason="Payroll vendor deadline",
                master=master,
                now=DEMO_DAY,
            )


def test_no_override_on_suspected_fraud(repo, master) -> None:
    case = repo.get("case_s12")  # CONFIRMED_FRAUD
    with pytest.raises((ValueError, PermissionError)):
        request_override(
            case,
            approver_ids=["emp_rajesh", "emp_sunil"],
            reason="please release it",
            master=master,
            now=DEMO_DAY,
        )


def test_watchlist_expires_after_30_days(repo) -> None:
    wl = Watchlist()
    wl.add("domain:kaveri-packagimg.example", DEMO_DAY)
    case = repo.get("case_s01")
    assert [s.code for s in wl.signals_for(case, ["kaveri-packagimg.example"], DEMO_DAY)] == [
        "WATCHLIST_HIT"
    ]
    assert wl.signals_for(case, ["kaveri-packagimg.example"], DEMO_DAY + timedelta(days=31)) == []
