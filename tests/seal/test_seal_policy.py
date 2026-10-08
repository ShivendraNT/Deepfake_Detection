"""Seal signals stay inside the raise-only lattice (property tests over the real engine).

1. A seal signal never lowers a band (adding VOICE_SEALED changes nothing at all).
2. VOICE_UNSEALED_CLAIMED_EXEC alone never takes a case above VERIFY (band = max(floor, VERIFY)),
   and on top of other signals it raises to at most VERIFY.
3. VOICE_SEALED never clears a HOLD: band, queue and clearance requirements are unchanged.
4. SEAL_PRESENCE_CONFLICT follows HOLD_IF_MONEY_ELSE_VERIFY and counts as one strong group.
5. The detector-side rules: 15 s of unsealed speech, enrolled claimed exec only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from satyapan.contracts import (
    SIGNAL_TABLE,
    Band,
    ReasonCode,
    SealEpoch,
    SealEpochStatus,
    SealVerification,
    Signal,
    SignalGroup,
    SignalSource,
    Strength,
    TargetRule,
)
from satyapan.policy import bmax, decide, rank
from satyapan.policy.config import PolicyConfig
from satyapan.policy.engine import has_money_movement
from satyapan.seal.signals import MIN_UNSEALED_SPEECH_S, voice_seal_signals
from tests.invariants.strategies import base_cases, signals, with_extras

PROVENANCE = (
    ReasonCode.VOICE_SEALED,
    ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC,
    ReasonCode.SEAL_PRESENCE_CONFLICT,
)


def _sig(code: ReasonCode, n: int = 0) -> Signal:
    return Signal.make(
        code, source=SignalSource.DETERMINISTIC, evidence_ids=["ev_x"], id=f"sig_seal{n}"
    )


def test_table_entries_are_deterministic_and_never_lower() -> None:
    for code in PROVENANCE:
        spec = SIGNAL_TABLE[code]
        assert spec.group == SignalGroup.PROVENANCE
        assert spec.allowed_sources == frozenset({SignalSource.DETERMINISTIC})
    assert SIGNAL_TABLE[ReasonCode.VOICE_SEALED].target == TargetRule.NONE
    assert SIGNAL_TABLE[ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC].target == TargetRule.VERIFY
    assert SIGNAL_TABLE[ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC].strength == Strength.WEAK


@given(base=base_cases(), sigs=st.lists(signals(), max_size=6), code=st.sampled_from(PROVENANCE))
def test_seal_signals_never_lower(master, base, sigs, code) -> None:  # type: ignore[no-untyped-def]
    before = decide(with_extras(base, sigs, [], None), master)
    after = decide(with_extras(base, [*sigs, _sig(code)], [], None), master)
    assert rank(after.band) >= rank(before.band)
    assert after.floor_band == before.floor_band


@given(base=base_cases(), sigs=st.lists(signals(), max_size=6))
def test_sealed_is_pure_information(master, base, sigs) -> None:  # type: ignore[no-untyped-def]
    """VOICE_SEALED never changes band, queue or clearance (so it can never clear a HOLD)."""
    before = decide(with_extras(base, sigs, [], None), master)
    after = decide(with_extras(base, [*sigs, _sig(ReasonCode.VOICE_SEALED)], [], None), master)
    assert after.band == before.band
    assert after.queue == before.queue
    assert after.clearance == before.clearance
    assert ReasonCode.VOICE_SEALED not in after.reason_codes  # info code, not a reason


@given(base=base_cases())
def test_unsealed_alone_never_exceeds_verify(master, base) -> None:  # type: ignore[no-untyped-def]
    only = decide(
        with_extras(base, [_sig(ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC)], [], None), master
    )
    assert only.band == bmax(only.floor_band, Band.VERIFY)
    if rank(only.floor_band) <= rank(Band.VERIFY):
        assert only.band == Band.VERIFY


@given(base=base_cases(), sigs=st.lists(signals(), max_size=6))
def test_unsealed_raises_to_at_most_verify(master, base, sigs) -> None:  # type: ignore[no-untyped-def]
    """Unsealed itself targets VERIFY. Under policy 1.1 (ADR-021) it is a deterministic,
    independent group, so it may CORROBORATE an ask that was capped at VERIFY (e.g. "skip the
    approval" + a claimed CFO whose voice is not sealed -> HOLD, which is intended, ADR-023).
    It can never push a case above what the asks would justify without the corroboration cap."""
    before = decide(with_extras(base, sigs, [], None), master)
    extra = _sig(ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC)
    after = decide(with_extras(base, [*sigs, extra], [], None), master)
    uncapped = decide(
        with_extras(base, sigs, [], None), master, PolicyConfig(ask_corroboration=False)
    )
    assert rank(after.band) >= rank(bmax(before.band, Band.VERIFY))
    assert rank(after.band) <= rank(bmax(uncapped.band, Band.VERIFY))
    if not any(s.group == SignalGroup.ASK for s in sigs):
        assert after.band == bmax(before.band, Band.VERIFY)


@given(base=base_cases())
def test_presence_conflict_target(master, base) -> None:  # type: ignore[no-untyped-def]
    case = with_extras(base, [_sig(ReasonCode.SEAL_PRESENCE_CONFLICT)], [], None)
    d = decide(case, master)
    want = Band.HOLD if has_money_movement(case) else Band.VERIFY
    assert d.band == bmax(d.floor_band, want)


def test_sealed_does_not_clear_a_hold(master) -> None:  # type: ignore[no-untyped-def]
    from tests.helpers import make_case
    from tests.invariants.strategies import TXNS

    case = make_case(txn=TXNS[4])  # N2 large new beneficiary
    hold_sigs = [
        Signal.make(ReasonCode.ASK_CREDENTIAL, source=SignalSource.DETERMINISTIC, id="sig_a2")
    ]
    held = decide(with_extras(case, hold_sigs, [], None), master)
    assert held.band == Band.HOLD
    sealed = decide(
        with_extras(case, [*hold_sigs, _sig(ReasonCode.VOICE_SEALED)], [], None), master
    )
    assert sealed.band == Band.HOLD and sealed.clearance == held.clearance


# ------------------------------------------------------------------ detector-side rules


def _verification(sealed: bool, employee: str | None, unsealed_epochs: int = 0) -> SealVerification:
    epochs = [
        SealEpoch(epoch=i, start_s=5.0 * i, cells=900, status=SealEpochStatus.SEALED, z=6.0)
        for i in range(6)
    ] + [
        SealEpoch(epoch=6 + i, start_s=30.0 + 5 * i, cells=900, status=SealEpochStatus.UNSEALED)
        for i in range(unsealed_epochs)
    ]
    return SealVerification(
        session_id="seal_x" if employee else None,
        employee_id=employee,
        sealed=sealed,
        decided_by="acquisition_1" if sealed else "not_sealed",
        acquisition_threshold=6.2,
        epochs=epochs,
        speech_seconds=40.0,
        params_id="vs1",
        verifier_version="t",
    )


def _codes(sigs: list[Signal]) -> list[ReasonCode]:
    return [s.code for s in sigs]


def test_rules_sealed_unsealed_and_threshold() -> None:
    sealed = _verification(True, "emp_rajesh")
    assert _codes(
        voice_seal_signals(
            [sealed], claimed_employee_id="emp_rajesh", claimed_enrolled=True, speech_seconds=40
        )
    ) == [ReasonCode.VOICE_SEALED]
    unsealed = _verification(False, None)
    assert _codes(
        voice_seal_signals(
            [unsealed], claimed_employee_id="emp_rajesh", claimed_enrolled=True, speech_seconds=40
        )
    ) == [ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC]
    # below 15 s of speech, or claimed person not enrolled, or nobody claimed: nothing fires
    short = MIN_UNSEALED_SPEECH_S - 0.5
    assert (
        voice_seal_signals(
            [unsealed],
            claimed_employee_id="emp_rajesh",
            claimed_enrolled=True,
            speech_seconds=short,
        )
        == []
    )
    assert (
        voice_seal_signals(
            [unsealed], claimed_employee_id="emp_rajesh", claimed_enrolled=False, speech_seconds=40
        )
        == []
    )
    assert (
        voice_seal_signals(
            [unsealed], claimed_employee_id=None, claimed_enrolled=True, speech_seconds=40
        )
        == []
    )


def test_rules_wrong_identity_and_spliced_gap() -> None:
    meera = _verification(True, "emp_meera")  # sealed by another enrolled exec
    sigs = voice_seal_signals(
        [meera], claimed_employee_id="emp_rajesh", claimed_enrolled=True, speech_seconds=40
    )
    assert _codes(sigs) == [ReasonCode.VOICE_SEALED, ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC]
    assert sigs[0].detail["sealed_by"] == "emp_meera"
    spliced = _verification(True, "emp_rajesh", unsealed_epochs=3)  # 15 s of unsealed speech
    sigs = voice_seal_signals(
        [spliced], claimed_employee_id="emp_rajesh", claimed_enrolled=True, speech_seconds=40
    )
    assert _codes(sigs) == [ReasonCode.VOICE_SEALED, ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC]
    assert sigs[1].detail["partly_sealed"] is True


def test_presence_conflict_signal() -> None:
    from datetime import timedelta

    from satyapan.contracts import SealSessionKind
    from satyapan.seal.registry import SealRegistry
    from satyapan.seal.signals import presence_conflict_signal
    from tests.seal.seal_fixtures import NOW, enrolled
    from tests.seal.test_seal_registry_intent import _start

    store, auth = enrolled()
    reg = SealRegistry(passkeys=store)
    s, keys = _start(reg, auth, kind=SealSessionKind.MEETING, seed=b"pc")
    t = NOW + timedelta(seconds=21)
    reg.disclose(s.id, 3, keys[3].hex(), t)
    sig = presence_conflict_signal(
        reg,
        claimed_employee_id="emp_rajesh",
        meeting_binding="meet:xyz-uvwq-rst",
        sealed_here=False,
        now=t,
    )
    assert sig is not None and sig.code == ReasonCode.SEAL_PRESENCE_CONFLICT
    assert (
        presence_conflict_signal(
            reg,
            claimed_employee_id="emp_rajesh",
            meeting_binding="meet:xyz-uvwq-rst",
            sealed_here=True,
            now=t,
        )
        is None
    )
    assert datetime(2026, 1, 1, tzinfo=UTC) < t  # sanity: aware datetimes
