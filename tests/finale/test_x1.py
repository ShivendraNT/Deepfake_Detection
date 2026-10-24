"""F04 acceptance: X1 cross-channel signal (ARCHITECTURE §7, PLAN §1).

Rule: within 30 minutes in the same payment case, an A1/A7 ask from a call or message
AND a payment to a new or changed beneficiary raises to VERIFY; an A4 (secrecy) or A5
(bypass) ask in the same window raises to HOLD.

All fixtures are fake (`FAK...`, `9999...`, `*.example`). No network.
X1 is deterministic, raise-only and never carries a raw score.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from satyapan.contracts import (
    SIGNAL_TABLE,
    Band,
    Case,
    CaseKind,
    Channel,
    Evidence,
    MasterChange,
    ReasonCode,
    Signal,
    SignalGroup,
    SignalSource,
    Strength,
    TargetRule,
)
from satyapan.pipeline import (
    CROSS_CHANNEL_WINDOW_SECONDS,
    derive_cross_channel_signals,
    recompute,
)
from satyapan.policy import decide
from satyapan.policy.bands import rank
from tests.helpers import payment

DET = SignalSource.DETERMINISTIC
BASE = datetime.fromisoformat("2026-10-05T10:00:00+05:30")

_SEQUENCE = ReasonCode.CROSS_CHANNEL_SEQUENCE
_URGENT = ReasonCode.CROSS_CHANNEL_URGENT_BYPASS


# --------------------------------------------------------------------------- helpers
def _evidence(ev_id: str, at: datetime, channel: Channel = Channel.WHATSAPP_TEXT) -> Evidence:
    return Evidence(
        id=ev_id,
        case_id="case_x1",
        channel=channel,
        filename=f"{ev_id}.txt",
        media_type="text/plain",
        sha256="a" * 64,
        size_bytes=12,
        captured_at=at,
        submitted_by="emp_priya",
        storage_uri=f"file://vault_data/{ev_id}.txt",
    )


def _ask(code: ReasonCode, ev_id: str) -> Signal:
    return Signal.make(code, source=DET, evidence_ids=[ev_id], detector="ask_extractor")


def _txn(
    at: datetime = BASE,
    *,
    vendor_id: str | None = None,
    amount: int = 10_000,
    account: str = "99991234567890",
    ifsc: str = "FAKZ0000001",
) -> Any:
    """New beneficiary by default (vendor_id=None) with fake details, at `at`."""
    return payment(vendor_id=vendor_id, amount=amount, account=account, ifsc=ifsc).model_copy(
        update={"created_at": at}
    )


def _case(
    *,
    txn: Any = None,
    evidence: list[Evidence] | None = None,
    signals: list[Signal] | None = None,
    kind: CaseKind = CaseKind.PAYMENT,
    master_change: MasterChange | None = None,
) -> Case:
    return Case(
        id="case_x1",
        title="X1 test case",
        kind=kind,
        created_at=BASE,
        created_by="emp_priya",
        txn=txn,
        master_change=master_change,
        evidence=evidence or [],
        signals=signals or [],
    )


def _codes(case: Case) -> set[ReasonCode]:
    assert case.decision is not None
    return set(case.decision.reason_codes)


# --------------------------------------------------------------------------- timing window
def test_sequence_within_window_triggers_x1() -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=10))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_PAYEE_CHANGE, ev.id)])

    derived = derive_cross_channel_signals(case)

    assert [s.code for s in derived] == [_SEQUENCE]
    assert derived[0].group == SignalGroup.CROSS_CHANNEL


def test_sequence_on_the_boundary_triggers_x1() -> None:
    ev = _evidence("ev_ask", BASE - timedelta(seconds=CROSS_CHANNEL_WINDOW_SECONDS))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_NEW_ACCOUNT, ev.id)])

    assert [s.code for s in derive_cross_channel_signals(case)] == [_SEQUENCE]


def test_sequence_older_than_window_does_not_trigger() -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=31))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_PAYEE_CHANGE, ev.id)])

    assert derive_cross_channel_signals(case) == []


def test_recompute_is_idempotent(master: Any) -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=5))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_PAYEE_CHANGE, ev.id)])

    once = recompute(case, master)
    twice = recompute(once, master)

    x1 = [s for s in twice.signals if s.code == _SEQUENCE]
    assert len(x1) == 1


# --------------------------------------------------------------------------- beneficiary rule
def test_changed_beneficiary_against_master_triggers_x1(master: Any) -> None:
    # case_s07 shape: V002 pays 99997777009917, but the master has 99990000002222 (C1).
    ev = _evidence("ev_ask", BASE - timedelta(minutes=10))
    txn = _txn(vendor_id="V002", amount=180_000, account="99997777009917", ifsc="FAKD0000991")
    case = _case(txn=txn, evidence=[ev], signals=[_ask(ReasonCode.ASK_NEW_ACCOUNT, ev.id)])

    derived = derive_cross_channel_signals(case, master)

    assert [s.code for s in derived] == [_SEQUENCE]


def test_known_unchanged_beneficiary_does_not_trigger(master: Any) -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=10))
    txn = _txn(vendor_id="V001", amount=200_000, account="99990000001111", ifsc="FAKA0000111")
    case = _case(txn=txn, evidence=[ev], signals=[_ask(ReasonCode.ASK_PAYEE_CHANGE, ev.id)])

    assert derive_cross_channel_signals(case, master) == []


def test_ask_without_beneficiary_ask_does_not_trigger() -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=10))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_SECRECY, ev.id)])

    assert derive_cross_channel_signals(case) == []


# --------------------------------------------------------------------------- A4 / A5 escalation
@pytest.mark.parametrize("code", [ReasonCode.ASK_SECRECY, ReasonCode.ASK_BYPASS])
def test_secrecy_or_bypass_escalates_to_hold(code: ReasonCode, master: Any) -> None:
    ev_ask = _evidence("ev_ask", BASE - timedelta(minutes=8))
    ev_urgent = _evidence("ev_urgent", BASE - timedelta(minutes=6))
    case = _case(
        txn=_txn(),
        evidence=[ev_ask, ev_urgent],
        signals=[_ask(ReasonCode.ASK_PAYEE_CHANGE, ev_ask.id), _ask(code, ev_urgent.id)],
    )

    derived = derive_cross_channel_signals(case)
    assert [s.code for s in derived] == [_URGENT]

    result = recompute(case, master)
    assert result.decision is not None
    assert result.decision.band == Band.HOLD
    assert _URGENT in _codes(result)


def test_urgency_outside_window_does_not_escalate() -> None:
    ev_ask = _evidence("ev_ask", BASE - timedelta(minutes=8))
    ev_urgent = _evidence("ev_urgent", BASE - timedelta(minutes=40))
    case = _case(
        txn=_txn(),
        evidence=[ev_ask, ev_urgent],
        signals=[
            _ask(ReasonCode.ASK_PAYEE_CHANGE, ev_ask.id),
            _ask(ReasonCode.ASK_SECRECY, ev_urgent.id),
        ],
    )

    assert [s.code for s in derive_cross_channel_signals(case)] == [_SEQUENCE]


# --------------------------------------------------------------------------- targets / raise-only
def test_x1_target_rules_are_verify_and_hold() -> None:
    sequence = SIGNAL_TABLE[_SEQUENCE]
    urgent = SIGNAL_TABLE[_URGENT]
    assert (sequence.group, sequence.target, sequence.strength) == (
        SignalGroup.CROSS_CHANNEL,
        TargetRule.VERIFY,
        Strength.STRONG,
    )
    assert (urgent.group, urgent.target, urgent.strength) == (
        SignalGroup.CROSS_CHANNEL,
        TargetRule.HOLD,
        Strength.STRONG,
    )


@pytest.mark.parametrize("code", [_SEQUENCE, _URGENT])
def test_x1_alone_never_lowers_a_band(code: ReasonCode, master: Any) -> None:
    """Every baseline floor: adding X1 is monotone (rank can only stay or rise)."""
    change = MasterChange(
        target="vendor_phone",
        vendor_id="V004",
        old_value="+91-00000-10004",
        new_value="+91-00000-99999",
        requested_via="email",
    )
    baselines = [
        _case(
            txn=_txn(vendor_id="V001", amount=200_000, account="99990000001111", ifsc="FAKA0000111")
        ),
        _case(
            txn=_txn(vendor_id="V001", amount=900_000, account="99990000001111", ifsc="FAKA0000111")
        ),
        _case(txn=_txn(amount=5_000_000)),
        _case(
            txn=_txn(vendor_id="V002", amount=100_000, account="99997777009917", ifsc="FAKD0000991")
        ),
        _case(kind=CaseKind.MASTER_CHANGE, master_change=change),
        _case(kind=CaseKind.DATA_REQUEST),
        _case(kind=CaseKind.LIVE_CALL),
    ]

    x1 = Signal.make(code, source=DET, evidence_ids=["ev_x"], detector="cross_channel")
    for baseline in baselines:
        before = decide(baseline, master)
        after = decide(baseline.model_copy(update={"signals": [x1]}), master)
        assert rank(after.band) >= rank(before.band)
        assert rank(after.floor_band) == rank(before.floor_band)


def test_x1_alone_can_raise_a_pass_floor(master: Any) -> None:
    case = _case(txn=_txn(amount=10_000))  # N1 -> PASS
    assert decide(case, master).band == Band.PASS

    verified = decide(
        case.model_copy(update={"signals": [Signal.make(_SEQUENCE, source=DET)]}), master
    )
    held = decide(case.model_copy(update={"signals": [Signal.make(_URGENT, source=DET)]}), master)

    assert verified.band == Band.VERIFY
    assert held.band == Band.HOLD


# --------------------------------------------------------------------------- determinism, no scores
def test_x1_is_deterministic_and_has_no_score() -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=3))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_NEW_ACCOUNT, ev.id)])

    signal = derive_cross_channel_signals(case)[0]

    assert signal.source == SignalSource.DETERMINISTIC
    assert signal.score is None
    assert signal.detector == "cross_channel"
    assert signal.evidence_ids == [ev.id]
    assert all(not isinstance(v, float) for v in signal.detail.values())
    assert signal.detail["window_seconds"] == 1800


def test_recompute_adds_x1_without_touching_the_floor(master: Any) -> None:
    ev = _evidence("ev_ask", BASE - timedelta(minutes=4))
    case = _case(txn=_txn(), evidence=[ev], signals=[_ask(ReasonCode.ASK_PAYEE_CHANGE, ev.id)])

    before = decide(case, master)
    result = recompute(case, master)

    assert result.decision is not None
    assert result.decision.floor_band == before.floor_band
    assert result.decision.action_type == before.action_type
    assert _SEQUENCE in _codes(result)
    assert result.decision.band == Band.VERIFY
