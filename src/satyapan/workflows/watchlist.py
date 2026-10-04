"""Sender / call watchlist (region R4): flagged counterparties start one band higher for 30 days.
TASK T13 — docs/tasks/T13-callback-checker-flows.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from satyapan.contracts.case import Case
from satyapan.contracts.evidence import Signal


@dataclass
class Watchlist:
    """key -> expiry. Keys: "domain:<sender domain>" or "call:<call_id>"."""

    entries: dict[str, datetime] = field(default_factory=dict)
    days: int = 30

    def add(self, key: str, now: datetime) -> None:
        raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")

    def add_from_case(self, case: Case, now: datetime) -> None:
        """Add every sender domain found in case.evidence artifacts/signals detail and every
        linked call id."""
        raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")

    def signals_for(self, case: Case, sender_domains: list[str], now: datetime) -> list[Signal]:
        """One WATCHLIST_HIT signal (source DETERMINISTIC) if any unexpired key matches."""
        raise NotImplementedError("T13: see docs/tasks/T13-callback-checker-flows.md")
