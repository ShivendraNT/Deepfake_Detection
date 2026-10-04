"""Signal -> target band. PRE-IMPLEMENTED (T02).

The ONLY place where a TargetRule becomes a Band. Raise-only: the result is always >= PASS
and is combined with the floor using bmax(), so no signal can lower anything.
"""

from __future__ import annotations

from satyapan.contracts.enums import Band, SignalGroup, SignalSource, TargetRule
from satyapan.contracts.evidence import Signal
from satyapan.policy.bands import bmin, plus_one, rank


def target_band(signal: Signal, floor_band: Band, money_movement: bool) -> Band:
    """Band this one signal asks for. LLM- or style-sourced signals are capped at VERIFY."""
    rule = signal.target
    if rule == TargetRule.NONE:
        t = Band.PASS
    elif rule == TargetRule.VERIFY:
        t = Band.VERIFY
    elif rule == TargetRule.HOLD:
        t = Band.HOLD
    elif rule == TargetRule.VERIFY_HOLD_IF_FLOOR_GE_VERIFY:
        t = Band.HOLD if rank(floor_band) >= rank(Band.VERIFY) else Band.VERIFY
    elif rule == TargetRule.PLUS_ONE:
        t = plus_one(floor_band)
    elif rule == TargetRule.HOLD_IF_MONEY_ELSE_VERIFY:
        t = Band.HOLD if money_movement else Band.VERIFY
    else:  # pragma: no cover - exhaustive
        raise ValueError(f"unknown target rule {rule}")

    if is_capped(signal):
        t = bmin(t, Band.VERIFY)  # cap: LLM/style can never cause HOLD
    return t


def is_capped(signal: Signal) -> bool:
    """LLM output and style cues are untrusted *interpretations*: raise-only, max VERIFY."""
    return signal.source == SignalSource.LLM or signal.group == SignalGroup.STYLE


def counts_as_strong_group(signal: Signal) -> bool:
    """Only strong, non-capped signals count toward the '>= 2 strong groups -> HOLD' rule.

    Note: excluding LLM-sourced signals here (not only style) closes a hole in the v3
    pseudo-code where two LLM-sourced 'strong' signals could reach HOLD (ADR-004).
    """
    return signal.strength == "strong" and not is_capped(signal)
