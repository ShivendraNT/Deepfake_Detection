"""INVARIANTS 5-6: OOB DENIED -> HOLD + SUSPECTED_FRAUD; grey -> >= VERIFY + checker queue."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from satyapan.contracts import Band, CaseStatus, GreyReason, OOBResult, Queue
from satyapan.policy import apply_decision, decide, rank
from tests.invariants.strategies import base_cases, signals, with_extras


@given(base=base_cases(), sigs=st.lists(signals(), max_size=6))
def test_oob_denied_always_hold(master, base, sigs) -> None:  # type: ignore[no-untyped-def]
    case = with_extras(base, sigs, [], OOBResult.DENIED)
    d = decide(case, master)
    assert d.band == Band.HOLD and d.suggested_status == CaseStatus.SUSPECTED_FRAUD
    assert apply_decision(case, d).status == CaseStatus.SUSPECTED_FRAUD


@given(base=base_cases(), grey=st.lists(st.sampled_from(list(GreyReason)), min_size=1, max_size=3))
def test_grey_forces_verify_and_checker_queue(master, base, grey) -> None:  # type: ignore[no-untyped-def]
    d = decide(with_extras(base, [], grey, None), master)
    assert rank(d.band) >= rank(Band.VERIFY) and d.queue == Queue.CHECKER_REVIEW and d.grey


def test_confirmed_fraud_is_never_downgraded(master) -> None:
    from tests.helpers import make_case

    case = make_case().model_copy(update={"status": CaseStatus.CONFIRMED_FRAUD})
    case = with_extras(case, [], [], OOBResult.DENIED).model_copy(
        update={"status": CaseStatus.CONFIRMED_FRAUD}
    )
    assert apply_decision(case, decide(case, master)).status == CaseStatus.CONFIRMED_FRAUD
