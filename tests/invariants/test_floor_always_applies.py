"""INVARIANT 4: the vendor-master floor always applies: band >= floor, whatever else happens."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from satyapan.contracts import ActionType, Band, GreyReason, OOBResult
from satyapan.policy import decide, rank
from tests.helpers import make_case, payment
from tests.invariants.strategies import base_cases, signals, with_extras


@given(
    base=base_cases(),
    sigs=st.lists(signals(), max_size=8),
    grey=st.lists(st.sampled_from(list(GreyReason)), max_size=2),
    oob=st.sampled_from([None, *OOBResult]),
)
def test_band_never_below_floor(master, base, sigs, grey, oob) -> None:  # type: ignore[no-untyped-def]
    d = decide(with_extras(base, sigs, grey, oob), master)
    assert rank(d.band) >= rank(d.floor_band)


def test_bank_change_is_verify_even_with_oob_approved_and_all_green(master) -> None:
    case = make_case(txn=payment(vendor_id="V002", account="99997777009917", ifsc="FAKD0000991"))
    case = with_extras(case, [], [], OOBResult.APPROVED)
    d = decide(case, master)
    assert d.action_type == ActionType.C1 and d.band == Band.VERIFY


def test_callback_number_comes_from_master_not_message(master) -> None:
    case = make_case(txn=payment(vendor_id="V002", account="99997777009917", ifsc="FAKD0000991"))
    d = decide(case, master)
    assert d.clearance.callback_number == master.vendor("V002").phone_on_file
    assert d.clearance.callback_number_source == "vendor_master_old"
