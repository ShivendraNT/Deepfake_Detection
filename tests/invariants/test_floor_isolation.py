"""INVARIANT 3: the floor depends only on trusted inputs (txn + master + config)."""

from __future__ import annotations

import inspect

from hypothesis import given
from hypothesis import strategies as st

from satyapan.contracts import GreyReason, OOBResult
from satyapan.policy import compute_floor, decide
from tests.invariants.strategies import base_cases, signals, with_extras


def test_floor_signature_has_no_untrusted_inputs() -> None:
    params = list(inspect.signature(compute_floor).parameters)
    assert params == ["kind", "txn", "master_change", "master", "cfg"]


@given(
    base=base_cases(),
    sigs=st.lists(signals(), max_size=8),
    grey=st.lists(st.sampled_from(list(GreyReason)), max_size=2),
    oob=st.sampled_from([None, *OOBResult]),
)
def test_untrusted_inputs_never_move_the_floor(master, base, sigs, grey, oob) -> None:  # type: ignore[no-untyped-def]
    bare = decide(with_extras(base, [], [], None), master)
    noisy = decide(with_extras(base, sigs, grey, oob), master)
    assert (noisy.floor_band, noisy.action_type) == (bare.floor_band, bare.action_type)
