"""INVARIANT 2: no LLM- or style-only path reaches HOLD (unless the trusted floor is HOLD)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from satyapan.contracts import Band, ReasonCode, Signal, SignalSource
from satyapan.policy import bmax, decide
from tests.helpers import make_case
from tests.invariants.strategies import base_cases, signals, with_extras


@given(base=base_cases(), sigs=st.lists(signals(only_capped=True), min_size=1, max_size=10))
def test_llm_and_style_capped_at_verify(master, base, sigs) -> None:  # type: ignore[no-untyped-def]
    d = decide(with_extras(base, sigs, [], None), master)
    assert d.band == bmax(d.floor_band, Band.VERIFY) or d.band == d.floor_band
    if d.floor_band != Band.HOLD:
        assert d.band != Band.HOLD


def test_many_style_signals_do_not_count_as_strong_groups(master) -> None:
    sigs = [Signal.make(ReasonCode.STYLE_PRESSURE, source=SignalSource.LLM) for _ in range(5)]
    d = decide(make_case(signals=sigs), master)
    assert d.band == Band.VERIFY
    assert ReasonCode.MULTI_GROUP_STRONG not in d.reason_codes
