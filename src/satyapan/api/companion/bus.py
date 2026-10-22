"""Bounded in-process event bus for the desktop companion (T25).

The bus is intentionally small: a bounded replay history for reconnects (`Last-Event-ID`), plus
one queue per SSE subscriber. A slow subscriber drops its oldest event instead of growing
without limit, and the service records an explicit gap elsewhere. No network code lives here.
"""

from __future__ import annotations

import queue
import threading
from collections import deque

from satyapan.api.companion.models import CompanionEvent

HISTORY_CAPACITY = 256
SUBSCRIBER_CAPACITY = 128
DEFAULT_KEEPALIVE_SECONDS = 15


class CompanionBus:
    """Thread-safe fan-out with a bounded replay buffer and monotonic event ids."""

    def __init__(
        self,
        history_capacity: int = HISTORY_CAPACITY,
        subscriber_capacity: int = SUBSCRIBER_CAPACITY,
    ) -> None:
        if history_capacity < 1 or subscriber_capacity < 1:
            raise ValueError("capacities must be positive")
        self._history: deque[CompanionEvent] = deque(maxlen=history_capacity)
        self._subscribers: set[queue.Queue[CompanionEvent]] = set()
        self._lock = threading.Lock()
        self._sequence = 0
        self._subscriber_capacity = subscriber_capacity
        self.dropped_events = 0

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence

    def publish(self, event: CompanionEvent) -> CompanionEvent:
        """Assign the next monotonic id, append to history and fan out to subscribers."""
        with self._lock:
            self._sequence += 1
            event.event_id = f"evt_{self._sequence:08d}"
            self._history.append(event)
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (queue.Empty, queue.Full):
                    self.dropped_events += 1
        return event

    def history(self, after_event_id: str | None = None) -> list[CompanionEvent]:
        """Replay events after `after_event_id`; unknown/missing ids replay the whole buffer."""
        with self._lock:
            snapshot = list(self._history)
        if after_event_id is None:
            return snapshot
        for index, event in enumerate(snapshot):
            if event.event_id == after_event_id:
                return snapshot[index + 1 :]
        return snapshot

    def subscribe(self) -> queue.Queue[CompanionEvent]:
        q: queue.Queue[CompanionEvent] = queue.Queue(maxsize=self._subscriber_capacity)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[CompanionEvent]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def reset(self) -> None:
        """Test/demo helper: clear history and sequence. Subscribers stay attached."""
        with self._lock:
            self._history.clear()
            self._sequence = 0
            self.dropped_events = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "sequence": self._sequence,
                "history": len(self._history),
                "subscribers": len(self._subscribers),
                "dropped_events": self.dropped_events,
            }
