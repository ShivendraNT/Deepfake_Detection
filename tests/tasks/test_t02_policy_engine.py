"""T02 acceptance: policy engine unit tests (DONE — pre-implemented).
The 3 property tests live in tests/invariants/ (monotonicity, LLM cap, floor isolation)."""

from __future__ import annotations

import pytest

from satyapan.contracts import (
    ActionType,
    Band,
    CaseKind,
    ClearanceMethod,
    MasterChange,
    Queue,
    ReasonCode,
    Role,
    Signal,
    SignalSource,
)
from satyapan.policy import DEFAULT_CONFIG, bmax, compute_floor, decide, plus_one
from satyapan.policy.targets import target_band
from tests.helpers import make_case, payment

pytestmark = pytest.mark.task("T02")

DET, ML, LLM = SignalSource.DETERMINISTIC, SignalSource.ML, SignalSource.LLM

FLOOR_CASES = [
    # (txn kwargs, expected band, expected action)
    ({"vendor_id": "V001", "amount": 200_000}, Band.PASS, ActionType.K1),
    ({"vendor_id": "V001", "amount": 300_000}, Band.PASS, ActionType.K1),  # == 1.25 x 240k
    ({"vendor_id": "V001", "amount": 300_001}, Band.VERIFY, ActionType.K2),
    (
        {"vendor_id": "V003", "amount": 50_000, "account": "99990000003333", "ifsc": "FAKA0000333"},
        Band.VERIFY,
        ActionType.K2,
    ),  # dormant
    (
        {"vendor_id": None, "amount": 25_000, "account": "99991234567890", "ifsc": "FAKZ0000001"},
        Band.PASS,
        ActionType.N1,
    ),
    (
        {"vendor_id": None, "amount": 25_001, "account": "99991234567890", "ifsc": "FAKZ0000001"},
        Band.VERIFY,
        ActionType.N2,
    ),
    (
        {
            "vendor_id": "V002",
            "amount": 100_000,
            "account": "99997777009917",
            "ifsc": "FAKD0000991",
        },
        Band.VERIFY,
        ActionType.C1,
    ),
    (
        {
            "vendor_id": "V002",
            "amount": 100_000,
            "account": "99990000002222",
            "ifsc": "FAKD0000991",
        },
        Band.VERIFY,
        ActionType.C1,
    ),  # right account, wrong IFSC
    (
        {
            "vendor_id": "V004",
            "amount": 10_000,
            "account": None,
            "ifsc": None,
            "upi": "tapti.supplies@fakeupi",
        },
        Band.PASS,
        ActionType.K1,
    ),
    (
        {
            "vendor_id": "V004",
            "amount": 10_000,
            "account": None,
            "ifsc": None,
            "upi": "tapti.other@fakeupi",
        },
        Band.VERIFY,
        ActionType.C1,
    ),
    (
        {"vendor_id": "V005", "amount": 10_000, "account": "99991111111111", "ifsc": "FAKB0000555"},
        Band.PASS,
        ActionType.N1,
    ),  # inactive vendor + new details -> treated as new payee
    (
        {"vendor_id": None, "amount": 200_000, "account": "99990000001111", "ifsc": "FAKA0000111"},
        Band.PASS,
        ActionType.K1,
    ),  # matched by payee details
    (
        {"vendor_id": "V999", "amount": 30_000, "account": "99991234567890", "ifsc": "FAKZ0000001"},
        Band.VERIFY,
        ActionType.N2,
    ),  # unknown vendor id
]


@pytest.mark.parametrize(("kw", "band", "action"), FLOOR_CASES)
def test_floor_table(master, kw, band, action) -> None:
    got = compute_floor(CaseKind.PAYMENT, payment(**kw), None, master, DEFAULT_CONFIG)
    assert got == (band, action)


def test_floor_t1_d1_none(master) -> None:
    mc = MasterChange(
        target="vendor_phone", vendor_id="V004", old_value="a", new_value="b", requested_via="email"
    )
    assert compute_floor(CaseKind.MASTER_CHANGE, None, mc, master, DEFAULT_CONFIG) == (
        Band.HOLD,
        ActionType.T1,
    )
    assert compute_floor(CaseKind.DATA_REQUEST, None, None, master, DEFAULT_CONFIG) == (
        Band.PASS,
        ActionType.D1,
    )
    assert compute_floor(CaseKind.LIVE_CALL, None, None, master, DEFAULT_CONFIG) == (
        Band.PASS,
        ActionType.NONE,
    )


TARGET_CASES = [
    # (code, source, floor, money, expected)
    (ReasonCode.EMAIL_DMARC_FAIL, DET, Band.PASS, True, Band.VERIFY),
    (ReasonCode.EMAIL_DMARC_FAIL, DET, Band.VERIFY, True, Band.HOLD),
    (ReasonCode.EMAIL_LOOKALIKE_DOMAIN, DET, Band.PASS, True, Band.VERIFY),
    (ReasonCode.EMAIL_LOOKALIKE_DOMAIN, DET, Band.VERIFY, True, Band.HOLD),
    (ReasonCode.EMAIL_BANK_NOT_BANK_IN, DET, Band.VERIFY, True, Band.VERIFY),
    (ReasonCode.EMAIL_REPLYTO_MISMATCH, DET, Band.PASS, True, Band.VERIFY),
    (ReasonCode.EMAIL_AUTH_PASS, DET, Band.VERIFY, True, Band.PASS),
    (ReasonCode.DOC_ACCOUNT_MISMATCH, DET, Band.PASS, True, Band.VERIFY),
    (ReasonCode.DOC_PDF_EDITED, DET, Band.PASS, True, Band.VERIFY),
    (ReasonCode.VOICE_LIKELY_SYNTHETIC, ML, Band.PASS, True, Band.VERIFY),
    (ReasonCode.VOICE_LIKELY_SYNTHETIC, ML, Band.VERIFY, True, Band.HOLD),
    (ReasonCode.VOICE_INCONCLUSIVE, ML, Band.VERIFY, True, Band.PASS),
    (ReasonCode.ASK_CREDENTIAL, DET, Band.PASS, False, Band.HOLD),
    (ReasonCode.ASK_REMOTE_ACCESS, DET, Band.PASS, False, Band.HOLD),
    (ReasonCode.ASK_SECRECY, DET, Band.PASS, True, Band.HOLD),
    (ReasonCode.ASK_SECRECY, DET, Band.PASS, False, Band.VERIFY),
    (ReasonCode.ASK_BYPASS, DET, Band.PASS, True, Band.HOLD),
    (ReasonCode.ASK_NEW_ACCOUNT, DET, Band.PASS, False, Band.VERIFY),
    (ReasonCode.STYLE_PRESSURE, LLM, Band.PASS, True, Band.VERIFY),
    (ReasonCode.STYLE_PRESSURE, ML, Band.VERIFY, True, Band.VERIFY),
    (ReasonCode.WATCHLIST_HIT, DET, Band.PASS, True, Band.VERIFY),
    (ReasonCode.WATCHLIST_HIT, DET, Band.VERIFY, True, Band.HOLD),
]


@pytest.mark.parametrize(("code", "source", "floor", "money", "expected"), TARGET_CASES)
def test_signal_targets(code, source, floor, money, expected) -> None:
    assert target_band(Signal.make(code, source=source), floor, money) == expected


def test_bands_helpers() -> None:
    assert bmax() == Band.PASS
    assert bmax(Band.PASS, Band.HOLD, Band.VERIFY) == Band.HOLD
    assert plus_one(Band.HOLD) == Band.HOLD


def test_two_strong_groups_hold(master) -> None:
    sigs = [
        Signal.make(ReasonCode.EMAIL_BANK_NOT_BANK_IN, source=DET),
        Signal.make(ReasonCode.DOC_ACCOUNT_MISMATCH, source=DET),
    ]
    d = decide(make_case(signals=sigs), master)
    assert d.band == Band.HOLD and ReasonCode.MULTI_GROUP_STRONG in d.reason_codes


def test_two_strong_same_group_not_hold(master) -> None:
    sigs = [
        Signal.make(ReasonCode.EMAIL_BANK_NOT_BANK_IN, source=DET),
        Signal.make(ReasonCode.EMAIL_DMARC_FAIL, source=DET),
    ]
    d = decide(make_case(signals=sigs), master)
    assert d.band == Band.VERIFY


def test_reason_codes_floor_first_and_info_separate(master) -> None:
    sigs = [
        Signal.make(ReasonCode.EMAIL_AUTH_PASS, source=DET),
        Signal.make(ReasonCode.EMAIL_REPLYTO_MISMATCH, source=DET),
    ]
    d = decide(make_case(signals=sigs), master)
    assert d.reason_codes[0] == ReasonCode.FLOOR_K1_KNOWN_IN_PATTERN
    assert ReasonCode.EMAIL_AUTH_PASS in d.info_codes
    assert ReasonCode.EMAIL_AUTH_PASS not in d.reason_codes


def test_hold_goes_to_checker_queue_and_only_checker_clears(master) -> None:
    sigs = [Signal.make(ReasonCode.ASK_CREDENTIAL, source=DET)]
    d = decide(make_case(signals=sigs), master)
    assert d.queue == Queue.CHECKER_REVIEW
    assert d.clearance.who == [Role.CHECKER]
    assert ClearanceMethod.OOB_CONFIRM not in d.clearance.methods


def test_c1_clearance_needs_callback_and_bank_name(master) -> None:
    d = decide(
        make_case(txn=payment(vendor_id="V002", account="99997777009917", ifsc="FAKD0000991")),
        master,
    )
    assert d.clearance.mode == "all"
    assert set(d.clearance.methods) == {
        ClearanceMethod.CALLBACK_MASTER_NUMBER,
        ClearanceMethod.BANK_NAME_MATCH,
    }


def test_n2_above_t_high_needs_callback_and_oob(master) -> None:
    txn = payment(
        vendor_id=None,
        amount=4_850_000,
        account="99998888004821",
        ifsc="FAKM0000482",
        requested_by="emp_rajesh",
    )
    d = decide(make_case(txn=txn), master)
    assert d.clearance.mode == "all"
    assert ClearanceMethod.OOB_CONFIRM in d.clearance.methods
    assert d.clearance.callback_number == master.employee("emp_rajesh").phone_on_file


def test_k2_verify_any_of(master) -> None:
    d = decide(
        make_case(txn=payment(vendor_id="V001", amount=900_000, requested_by="emp_rajesh")), master
    )
    assert d.band == Band.VERIFY and d.clearance.mode == "any"
    assert d.clearance.callback_number == "+91-00000-10001"


def test_pass_has_no_clearance(master) -> None:
    d = decide(make_case(), master)
    assert d.band == Band.PASS and d.clearance.mode == "none"


def test_decision_records_policy_version(master) -> None:
    assert decide(make_case(), master).policy_version == DEFAULT_CONFIG.policy_version
