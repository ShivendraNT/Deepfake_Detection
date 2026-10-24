"""Relay the live call bus into the companion bus (F03).

`LiveService.bus` is a per-call `EventBus`. We wrap it once: every event is published to the
existing live SSE subscribers exactly as before, then handed to a companion sink synchronously.
That keeps ordering deterministic and means a chunk request cannot return before the companion
has seen its ask/band event.

What crosses the boundary: ask codes, voice *labels* (never scores), and the policy engine's
`BandEvent.band`. Transcript text never crosses: the companion does not need it and it is the
most sensitive part of a call.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from satyapan.contracts.live import LiveEvent
from satyapan.live.service import EventBus

log = logging.getLogger(__name__)

LiveSink = Callable[[str, LiveEvent], None]


class CompanionLiveBus(EventBus):
    """An `EventBus` that also forwards each event to the companion sink."""

    def __init__(self, sink: LiveSink) -> None:
        super().__init__()
        self._sink = sink

    def publish(self, call_id: str, event: LiveEvent) -> None:
        super().publish(call_id, event)
        try:
            self._sink(call_id, event)
        except Exception:  # noqa: BLE001 - companion failure must never break live capture
            log.exception("companion live fan-in failed for call %s", call_id)


def attach_live_bus(live: object, sink: LiveSink) -> None:
    """Replace `live.bus` with the forwarding bus once. Idempotent."""
    bus = getattr(live, "bus", None)
    if isinstance(bus, CompanionLiveBus):
        return
    live.bus = CompanionLiveBus(sink)  # type: ignore[attr-defined]


__all__ = ["CompanionLiveBus", "LiveSink", "attach_live_bus"]
