"""The signal table and enums are consistent. These must always pass."""

from __future__ import annotations

from satyapan.contracts import (
    ASK_TO_REASON,
    BAND_ORDER,
    DECISION_ONLY_CODES,
    FLOOR_REASON,
    SIGNAL_TABLE,
    AskType,
    Band,
    ReasonCode,
    SignalGroup,
    SignalSource,
    TargetRule,
)


def test_band_order() -> None:
    assert BAND_ORDER[Band.PASS] < BAND_ORDER[Band.VERIFY] < BAND_ORDER[Band.HOLD]


def test_every_reason_code_has_exactly_one_home() -> None:
    floor_codes = set(FLOOR_REASON.values())
    for code in ReasonCode:
        homes = [code in SIGNAL_TABLE, code in DECISION_ONLY_CODES, code in floor_codes]
        assert sum(homes) == 1, f"{code} must be in exactly one of signal table/decision/floor"


def test_every_ask_type_has_a_reason_code_in_table() -> None:
    assert set(ASK_TO_REASON) == set(AskType)
    for code in ASK_TO_REASON.values():
        assert SIGNAL_TABLE[code].group == SignalGroup.ASK


def test_deterministic_codes_never_accept_llm() -> None:
    for code, spec in SIGNAL_TABLE.items():
        if spec.group in (
            SignalGroup.SENDER_AUTH,
            SignalGroup.DOCUMENT,
            SignalGroup.ASK,
            SignalGroup.WATCHLIST,
        ):
            assert SignalSource.LLM not in spec.allowed_sources, code


def test_style_is_weak_and_at_most_verify() -> None:
    for spec in SIGNAL_TABLE.values():
        if spec.group == SignalGroup.STYLE:
            assert spec.strength == "weak"
            assert spec.target in (TargetRule.NONE, TargetRule.VERIFY)


def test_no_target_rule_can_lower() -> None:
    # There is no "PASS"/"LOWER" target: NONE is the minimum and means "no effect".
    assert {t.value for t in TargetRule} == {
        "NONE",
        "VERIFY",
        "HOLD",
        "VERIFY_HOLD_IF_FLOOR_GE_VERIFY",
        "PLUS_ONE",
        "HOLD_IF_MONEY_ELSE_VERIFY",
    }
