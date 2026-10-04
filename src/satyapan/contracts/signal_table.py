"""Signal -> (group, target rule, strength, allowed sources). CONTRACT FILE.

This is the "signal -> target band" table from docs/ARCHITECTURE.md §6, as data.
Detectors never choose a group, target or strength themselves: `Signal.make(code, ...)`
fills them from this table. That way two teammates cannot disagree about what a code means.

Safety notes (enforced by tests/invariants):
- No entry has a target that LOWERS a band. The lowest target is NONE (informational).
- STYLE codes may come from ML or LLM; they are capped at VERIFY by the policy engine anyway.
- Deterministic codes (email, document, asks, watchlist) may NOT come from an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass

from satyapan.contracts.enums import ReasonCode, SignalGroup, SignalSource, Strength, TargetRule

_DET = frozenset({SignalSource.DETERMINISTIC})
_ML = frozenset({SignalSource.ML})
_STYLE_SOURCES = frozenset({SignalSource.ML, SignalSource.LLM})


@dataclass(frozen=True)
class SignalSpec:
    group: SignalGroup
    target: TargetRule
    strength: Strength
    allowed_sources: frozenset[SignalSource]


SIGNAL_TABLE: dict[ReasonCode, SignalSpec] = {
    # --- sender_auth (C3, deterministic) ---
    ReasonCode.EMAIL_AUTH_PASS: SignalSpec(
        SignalGroup.SENDER_AUTH, TargetRule.NONE, Strength.WEAK, _DET
    ),
    ReasonCode.EMAIL_DMARC_FAIL: SignalSpec(
        SignalGroup.SENDER_AUTH, TargetRule.VERIFY_HOLD_IF_FLOOR_GE_VERIFY, Strength.STRONG, _DET
    ),
    ReasonCode.EMAIL_LOOKALIKE_DOMAIN: SignalSpec(
        SignalGroup.SENDER_AUTH, TargetRule.VERIFY_HOLD_IF_FLOOR_GE_VERIFY, Strength.STRONG, _DET
    ),
    ReasonCode.EMAIL_BANK_NOT_BANK_IN: SignalSpec(
        SignalGroup.SENDER_AUTH, TargetRule.VERIFY, Strength.STRONG, _DET
    ),
    ReasonCode.EMAIL_REPLYTO_MISMATCH: SignalSpec(
        SignalGroup.SENDER_AUTH, TargetRule.VERIFY, Strength.WEAK, _DET
    ),
    ReasonCode.EMAIL_FREEMAIL_CORPORATE: SignalSpec(
        SignalGroup.SENDER_AUTH, TargetRule.VERIFY, Strength.WEAK, _DET
    ),
    # --- document (C4, deterministic) ---
    ReasonCode.DOC_NO_ISSUES: SignalSpec(
        SignalGroup.DOCUMENT, TargetRule.NONE, Strength.WEAK, _DET
    ),
    ReasonCode.DOC_ACCOUNT_MISMATCH: SignalSpec(
        SignalGroup.DOCUMENT, TargetRule.VERIFY, Strength.STRONG, _DET
    ),
    ReasonCode.DOC_PDF_EDITED: SignalSpec(
        SignalGroup.DOCUMENT, TargetRule.VERIFY, Strength.WEAK, _DET
    ),
    # --- media (C6, ML) ---
    ReasonCode.VOICE_NO_SIGNS: SignalSpec(SignalGroup.MEDIA, TargetRule.NONE, Strength.WEAK, _ML),
    ReasonCode.VOICE_INCONCLUSIVE: SignalSpec(
        SignalGroup.MEDIA, TargetRule.NONE, Strength.WEAK, _ML
    ),
    ReasonCode.VOICE_LIKELY_SYNTHETIC: SignalSpec(
        SignalGroup.MEDIA, TargetRule.PLUS_ONE, Strength.STRONG, _ML
    ),
    # --- ask (C5, deterministic) ---
    ReasonCode.ASK_NEW_ACCOUNT: SignalSpec(SignalGroup.ASK, TargetRule.VERIFY, Strength.WEAK, _DET),
    ReasonCode.ASK_CREDENTIAL: SignalSpec(SignalGroup.ASK, TargetRule.HOLD, Strength.STRONG, _DET),
    ReasonCode.ASK_REMOTE_ACCESS: SignalSpec(
        SignalGroup.ASK, TargetRule.HOLD, Strength.STRONG, _DET
    ),
    ReasonCode.ASK_SECRECY: SignalSpec(
        SignalGroup.ASK, TargetRule.HOLD_IF_MONEY_ELSE_VERIFY, Strength.STRONG, _DET
    ),
    ReasonCode.ASK_BYPASS: SignalSpec(
        SignalGroup.ASK, TargetRule.HOLD_IF_MONEY_ELSE_VERIFY, Strength.STRONG, _DET
    ),
    ReasonCode.ASK_UNUSUAL_PAYMENT_METHOD: SignalSpec(
        SignalGroup.ASK, TargetRule.VERIFY, Strength.WEAK, _DET
    ),
    ReasonCode.ASK_PAYEE_CHANGE: SignalSpec(
        SignalGroup.ASK, TargetRule.VERIFY, Strength.WEAK, _DET
    ),
    # --- style (C8 / LLM): raise-only, capped at VERIFY, never counted as a strong group ---
    ReasonCode.STYLE_PRESSURE: SignalSpec(
        SignalGroup.STYLE, TargetRule.VERIFY, Strength.WEAK, _STYLE_SOURCES
    ),
    # --- watchlist (R4, deterministic) ---
    ReasonCode.WATCHLIST_HIT: SignalSpec(
        SignalGroup.WATCHLIST, TargetRule.PLUS_ONE, Strength.WEAK, _DET
    ),
}

# Codes that only the policy engine may emit (they are never Signals).
DECISION_ONLY_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.MULTI_GROUP_STRONG,
        ReasonCode.GREY_FLAG,
        ReasonCode.OOB_DENIED,
        ReasonCode.OOB_APPROVED,
    }
)

# Money-movement asks (used by TargetRule.HOLD_IF_MONEY_ELSE_VERIFY).
MONEY_ASK_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.ASK_NEW_ACCOUNT,
        ReasonCode.ASK_UNUSUAL_PAYMENT_METHOD,
        ReasonCode.ASK_PAYEE_CHANGE,
    }
)
