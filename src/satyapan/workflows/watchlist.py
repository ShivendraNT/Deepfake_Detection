"""Sender / call watchlist (region R4): flagged counterparties start one band higher for 30 days.
TASK T13 — docs/tasks/T13-callback-checker-flows.md."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from satyapan.contracts.case import Case
from satyapan.contracts.enums import ReasonCode, SignalSource
from satyapan.contracts.evidence import Signal

_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*\.[a-z]{2,}$")
_DOMAIN_KEYS = frozenset(
    {"domain", "sender", "sender_domain", "from", "from_domain", "mail_from", "source_domain"}
)


@dataclass
class Watchlist:
    """key -> expiry. Keys: "domain:<sender domain>" or "call:<call_id>"."""

    entries: dict[str, datetime] = field(default_factory=dict)
    days: int = 30

    def add(self, key: str, now: datetime) -> None:
        self.entries[key] = now + timedelta(days=self.days)

    def add_from_case(self, case: Case, now: datetime) -> None:
        """Add every sender domain found in case.evidence artifacts/signals detail and every
        linked call id."""
        for signal in case.signals:
            for key, value in signal.detail.items():
                if not isinstance(value, str) or not value:
                    continue
                if key in _DOMAIN_KEYS and _DOMAIN_RE.match(value.casefold()):
                    self.add(f"domain:{value.casefold()}", now)
                elif value.startswith("call:"):
                    self.add(value, now)
        for call_id in case.linked_call_ids:
            self.add(f"call:{call_id}", now)

    def signals_for(self, case: Case, sender_domains: list[str], now: datetime) -> list[Signal]:
        """One WATCHLIST_HIT signal (source DETERMINISTIC) if any unexpired key matches."""
        wanted = {f"domain:{d.casefold()}" for d in sender_domains}
        wanted |= {f"call:{c}" for c in case.linked_call_ids}
        hits = sorted(k for k, expiry in self.entries.items() if k in wanted and now < expiry)
        if not hits:
            return []
        return [
            Signal.make(
                ReasonCode.WATCHLIST_HIT,
                source=SignalSource.DETERMINISTIC,
                detail={"matched": hits[0], "hits": ", ".join(hits)},
            )
        ]


DEFAULT_WATCHLIST = Watchlist()
