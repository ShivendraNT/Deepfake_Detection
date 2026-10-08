"""INVARIANT 7 (ADR-021): one ask type alone, with no corroboration, never reaches HOLD.

Brief: "Avoid automatic blocking or accusations based on a single weak signal." An ask is a
lexicon hit. Unless the trusted floor shows a risky action (new/changed payee, odd amount,
trust-anchor change, data hand-over) or another independent signal raises, it is at most
VERIFY. Repeating the same ask type (many spans, many messages) does not change that.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from satyapan.contracts import SIGNAL_TABLE, Band, Signal, SignalGroup, SignalSource
from satyapan.policy import decide
from satyapan.policy.engine import CORROBORATING_ACTIONS
from tests.invariants.strategies import base_cases, with_extras

ASK_CODES = sorted(c for c, spec in SIGNAL_TABLE.items() if spec.group == SignalGroup.ASK)


@given(base=base_cases(), code=st.sampled_from(ASK_CODES), copies=st.integers(1, 5))
def test_single_uncorroborated_ask_never_holds(master, base, code, copies) -> None:  # type: ignore[no-untyped-def]
    sigs = [
        Signal.make(code, source=SignalSource.DETERMINISTIC, evidence_ids=[f"ev_{i}"])
        for i in range(copies)
    ]
    d = decide(with_extras(base, sigs, [], None), master)
    if d.action_type not in CORROBORATING_ACTIONS and d.floor_band != Band.HOLD:
        assert d.band != Band.HOLD
