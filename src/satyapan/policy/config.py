"""Policy configuration. PRE-IMPLEMENTED (T02). Values from docs/ARCHITECTURE.md §6."""

from __future__ import annotations

from dataclasses import dataclass

POLICY_VERSION = "1.1.0"  # 1.1: ask corroboration + 30-day de-minimis window (ADR-021/022)


@dataclass(frozen=True)
class PolicyConfig:
    de_minimis_inr: int = 25_000  # N1 vs N2
    t_high_inr: int = 1_000_000  # ₹10 lakh: N2 above this needs callback AND OOB
    pattern_multiplier: float = 1.25  # K1 if amount <= 1.25 x max of last 12 months
    dormant_days: int = 180  # K2 if last paid more than this many days ago
    watchlist_days: int = 30
    # ADR-021: one ask type alone (a lexicon hit) is a single weak signal -> at most VERIFY,
    # unless corroborated (second ask type, another raising signal group, or a risky action
    # in the trusted floor). False = policy 1.0.0 behaviour (kept only for before/after runs).
    ask_corroboration: bool = True
    # ADR-022: N1 vs N2 uses today's amount PLUS what this new payee already received in the
    # last N days (payer's own payment register). 0 = per-payment only (policy 1.0.0).
    de_minimis_window_days: int = 30
    oob_ttl_minutes: int = 10
    override_review_hours: int = 48
    policy_version: str = POLICY_VERSION


DEFAULT_CONFIG = PolicyConfig()
