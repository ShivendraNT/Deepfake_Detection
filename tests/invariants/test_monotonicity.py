"""INVARIANT 1: monotone. Removing signals never raises the band; adding never lowers it."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from satyapan.policy import decide, rank
from tests.invariants.strategies import base_cases, signals, with_extras


@given(base=base_cases(), sigs=st.lists(signals(), max_size=8), data=st.data())
def test_subset_never_higher(master, base, sigs, data) -> None:  # type: ignore[no-untyped-def]
    mask = data.draw(st.lists(st.booleans(), min_size=len(sigs), max_size=len(sigs)))
    subset = [s for s, keep in zip(sigs, mask, strict=True) if keep]
    full = decide(with_extras(base, sigs, [], None), master)
    part = decide(with_extras(base, subset, [], None), master)
    assert rank(part.band) <= rank(full.band)


@given(base=base_cases(), sigs=st.lists(signals(), max_size=6), extra=signals())
def test_adding_a_signal_never_lowers(master, base, sigs, extra) -> None:  # type: ignore[no-untyped-def]
    before = decide(with_extras(base, sigs, [], None), master)
    after = decide(with_extras(base, [*sigs, extra], [], None), master)
    assert rank(after.band) >= rank(before.band)
