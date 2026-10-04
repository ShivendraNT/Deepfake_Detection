"""Hypothesis strategies for policy invariants."""

from __future__ import annotations

from hypothesis import strategies as st

from satyapan.contracts import (
    SIGNAL_TABLE,
    Case,
    CaseKind,
    CaseStatus,
    GreyReason,
    MasterChange,
    OOBRequest,
    OOBResult,
    Signal,
    SignalGroup,
    SignalSource,
)
from tests.helpers import DEMO_DAY, make_case, payment

# One txn per floor action type (see data/demo master):
# K1, K2 (amount), K2 (dormant), N1, N2, C1, inactive vendor, UPI.
TXNS = [
    payment(vendor_id="V001", amount=200_000),  # K1
    payment(vendor_id="V001", amount=900_000),  # K2 out of pattern
    payment(
        vendor_id="V003", amount=50_000, account="99990000003333", ifsc="FAKA0000333"
    ),  # K2 dormant
    payment(vendor_id=None, amount=10_000, account="99991234567890", ifsc="FAKZ0000001"),  # N1
    payment(
        vendor_id=None,
        amount=5_000_000,
        account="99991234567890",
        ifsc="FAKZ0000001",
        requested_by="emp_rajesh",
    ),  # N2 > T_high
    payment(vendor_id="V002", amount=100_000, account="99997777009917", ifsc="FAKD0000991"),  # C1
    payment(
        vendor_id="V005", amount=40_000, account="99991111111111", ifsc="FAKB0000555"
    ),  # inactive
    payment(vendor_id="V004", amount=12_000, account=None, ifsc=None, upi="tapti.supplies@fakeupi"),
]

_CHANGE = MasterChange(
    target="vendor_phone",
    vendor_id="V004",
    old_value="+91-00000-10004",
    new_value="+91-00000-99999",
    requested_via="email",
)


@st.composite
def signals(draw: st.DrawFn, only_capped: bool = False) -> Signal:
    codes = [
        c
        for c, spec in SIGNAL_TABLE.items()
        if not only_capped
        or spec.group == SignalGroup.STYLE
        or SignalSource.LLM in spec.allowed_sources
    ]
    code = draw(st.sampled_from(sorted(codes)))
    spec = SIGNAL_TABLE[code]
    source = draw(st.sampled_from(sorted(spec.allowed_sources)))
    if only_capped and spec.group != SignalGroup.STYLE:
        source = SignalSource.LLM
    return Signal.make(
        code, source=source, evidence_ids=["ev_x"], id=f"sig_{draw(st.integers(0, 10**9))}"
    )


@st.composite
def base_cases(draw: st.DrawFn) -> Case:
    kind = draw(
        st.sampled_from(
            ["PAYMENT", "PAYMENT", "PAYMENT", "MASTER_CHANGE", "DATA_REQUEST", "LIVE_CALL"]
        )
    )
    if kind == "PAYMENT":
        return make_case(txn=draw(st.sampled_from(TXNS)))
    if kind == "MASTER_CHANGE":
        return make_case(kind=CaseKind.MASTER_CHANGE, master_change=_CHANGE)
    return make_case(kind=CaseKind(kind))


def with_extras(
    case: Case, sigs: list[Signal], grey: list[GreyReason], oob: OOBResult | None
) -> Case:
    oob_req = None
    if oob is not None:
        oob_req = OOBRequest(
            id="oob_x",
            case_id=case.id,
            requester_employee_id="emp_rajesh",
            sent_to_email="rajesh@demo-industries.example",
            message_text="?",
            binding_hash="b" * 64,
            nonce="n",
            token_sha256="c" * 64,
            created_at=DEMO_DAY,
            expires_at=DEMO_DAY,
            result=oob,
        )
    return case.model_copy(
        update={"signals": sigs, "grey_reasons": grey, "oob": oob_req, "status": CaseStatus.OPEN}
    )
