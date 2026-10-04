"""Policy configuration. PRE-IMPLEMENTED (T02). Values from docs/ARCHITECTURE.md §6."""

from __future__ import annotations

from dataclasses import dataclass

POLICY_VERSION = "1.0.0"


@dataclass(frozen=True)
class PolicyConfig:
    de_minimis_inr: int = 25_000  # N1 vs N2
    t_high_inr: int = 1_000_000  # ₹10 lakh: N2 above this needs callback AND OOB
    pattern_multiplier: float = 1.25  # K1 if amount <= 1.25 x max of last 12 months
    dormant_days: int = 180  # K2 if last paid more than this many days ago
    watchlist_days: int = 30
    oob_ttl_minutes: int = 10
    override_review_hours: int = 48
    policy_version: str = POLICY_VERSION


DEFAULT_CONFIG = PolicyConfig()
