"""Live call sessions. TASK T11 — docs/tasks/T11-live-transcript.md.

No LLM in the loop: alert text comes from templates (latency budget §5.5 in ARCHITECTURE).
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field

from satyapan.adapters.base import Transcriber
from satyapan.asks.extractor import DETECTOR_NAME, ask_signals, extract_asks
from satyapan.context import strip_context
from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import ASK_TO_REASON, Band, CaseKind, Lang, ReasonCode
from satyapan.contracts.evidence import AskSpan
from satyapan.contracts.live import (
    AskEvent,
    BandEvent,
    LiveEvent,
    TranscriptEvent,
    VoiceEvent,
    VoiceWindowResult,
)
from satyapan.explain.templates import SUGGESTED_LINES
from satyapan.master.store import MasterData
from satyapan.policy.engine import apply_decision, decide
from satyapan.voice.rules import VoiceThresholds, classify_windows, voice_signal

CHUNK_SECONDS = 10.0
_VOICE_CODES = {
    ReasonCode.VOICE_LIKELY_SYNTHETIC,
    ReasonCode.VOICE_INCONCLUSIVE,
    ReasonCode.VOICE_NO_SIGNS,
}


@dataclass
class LiveSession:
    call_id: str
    case: Case
    transcript: list[str] = field(default_factory=list)
    asks: list[AskSpan] = field(default_factory=list)
    voice_windows: list[VoiceWindowResult] = field(default_factory=list)
    last_band: Band = Band.PASS
    # Routes run handle_chunk/handle_voice in worker threads; one call's updates never interleave.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


@dataclass
class EventBus:
    """Per-call asyncio queues for server-sent events.

    publish() may run in a worker thread (the routes run Whisper off the event loop), and
    asyncio.Queue is not thread-safe, so each queue remembers the loop it was created on and
    events are handed to that loop with call_soon_threadsafe.
    """

    queues: dict[str, list[asyncio.Queue[LiveEvent]]] = field(default_factory=dict)
    _loops: dict[int, asyncio.AbstractEventLoop | None] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def publish(self, call_id: str, event: LiveEvent) -> None:
        with self._lock:
            targets = [(q, self._loops.get(id(q))) for q in self.queues.get(call_id, [])]
        for q, loop in targets:
            if loop is None or _running_loop() is loop:
                q.put_nowait(event)
            elif not loop.is_closed():
                loop.call_soon_threadsafe(q.put_nowait, event)

    def subscribe(self, call_id: str) -> asyncio.Queue[LiveEvent]:
        q: asyncio.Queue[LiveEvent] = asyncio.Queue()
        with self._lock:
            self.queues.setdefault(call_id, []).append(q)
            self._loops[id(q)] = _running_loop()
        return q

    def unsubscribe(self, call_id: str, q: asyncio.Queue[LiveEvent]) -> None:
        with self._lock:
            subs = self.queues.get(call_id, [])
            if q in subs:
                subs.remove(q)
            if not subs:
                self.queues.pop(call_id, None)
            self._loops.pop(id(q), None)


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


@dataclass
class LiveService:
    master: MasterData
    transcriber: Transcriber
    thresholds: VoiceThresholds
    bus: EventBus = field(default_factory=EventBus)
    sessions: dict[str, LiveSession] = field(default_factory=dict)
    # ADR-021: drop spoken warnings ("never share your OTP") before ask extraction.
    context_filter: bool = True

    def start(self, call_id: str, maker_id: str) -> LiveSession:
        """Create a LIVE_CALL Case (id f"case_live_{call_id}") and a session."""
        case = Case(
            id=f"case_live_{call_id}",
            title=f"Live call {call_id}",
            kind=CaseKind.LIVE_CALL,
            created_at=utcnow(),
            created_by=maker_id,
            linked_call_ids=[call_id],
        )
        session = LiveSession(call_id=call_id, case=case)
        self.sessions[call_id] = session
        return session

    def handle_chunk(
        self, call_id: str, chunk_index: int, audio: bytes, mime: str
    ) -> list[LiveEvent]:
        """transcribe -> TranscriptEvent; extract_asks -> one AskEvent per NEW ask type;
        update case.signals with ask_signals; re-decide; if band changed -> BandEvent with
        reason codes and SUGGESTED_LINES[EN]. Publish every event on the bus and return them."""
        session = self.sessions[call_id]
        with session.lock:
            return self._handle_chunk(session, chunk_index, audio, mime)

    def _handle_chunk(
        self, session: LiveSession, chunk_index: int, audio: bytes, mime: str
    ) -> list[LiveEvent]:
        call_id = session.call_id
        res = self.transcriber.transcribe(audio, mime)
        session.transcript.append(res.text)
        events: list[LiveEvent] = [
            TranscriptEvent(
                call_id=call_id,
                chunk_index=chunk_index,
                t_start_s=chunk_index * CHUNK_SECONDS,
                text=res.text,
                language=res.language,
            )
        ]

        seen = {s.ask_type for s in session.asks}
        ask_text = strip_context(res.text).cleaned if self.context_filter else res.text
        for span in extract_asks(ask_text):
            if span.ask_type not in seen:
                seen.add(span.ask_type)
                events.append(
                    AskEvent(
                        call_id=call_id,
                        chunk_index=chunk_index,
                        ask_type=span.ask_type,
                        reason_code=ASK_TO_REASON[span.ask_type],
                        span_text=span.text,
                    )
                )
            session.asks.append(span)

        # Asks only accumulate: rebuild the ask signals from every span seen in the call.
        others = [s for s in session.case.signals if s.detector != DETECTOR_NAME]
        new_asks = ask_signals(session.asks, evidence_id=f"ev_live_{call_id}")
        session.case = session.case.model_copy(update={"signals": others + new_asks})

        events += self._redecide(session)
        return self._publish(call_id, events)

    def handle_voice(self, call_id: str, windows: list[VoiceWindowResult]) -> list[LiveEvent]:
        """Append windows; classify_windows over ALL scores so far; replace the session's voice
        signal; emit VoiceEvent (score stripped) and BandEvent if the band changed."""
        session = self.sessions[call_id]
        if not windows:
            return []
        with session.lock:
            return self._handle_voice(session, windows)

    def _handle_voice(
        self, session: LiveSession, windows: list[VoiceWindowResult]
    ) -> list[LiveEvent]:
        call_id = session.call_id
        by_index = {w.window_index: w for w in session.voice_windows}
        by_index.update({w.window_index: w for w in windows})
        session.voice_windows = [by_index[i] for i in sorted(by_index)]

        verdict = classify_windows(
            [w.score for w in session.voice_windows],
            self.thresholds,
            speech_seconds=sum(w.speech_seconds for w in session.voice_windows),
        )
        signal = voice_signal(verdict, self.thresholds, [f"ev_live_{call_id}_voice"])
        others = [s for s in session.case.signals if s.code not in _VOICE_CODES]
        grey = list(dict.fromkeys([*session.case.grey_reasons, *verdict.grey_reasons]))
        session.case = session.case.model_copy(
            update={"signals": [*others, signal], "grey_reasons": grey}
        )

        events: list[LiveEvent] = [
            VoiceEvent(
                call_id=call_id,
                window_index=session.voice_windows[-1].window_index,
                label=verdict.label,
                consecutive_over_hi=verdict.max_consecutive_over_hi,
                score=None,  # makers never see raw scores
            )
        ]
        events += self._redecide(session)
        return self._publish(call_id, events)

    def _redecide(self, session: LiveSession) -> list[LiveEvent]:
        decision = decide(session.case, self.master)
        session.case = apply_decision(session.case, decision)
        if decision.band == session.last_band:
            return []
        session.last_band = decision.band
        return [
            BandEvent(
                call_id=session.call_id,
                band=decision.band,
                reason_codes=decision.reason_codes,
                suggested_line=SUGGESTED_LINES[Lang.EN],
            )
        ]

    def _publish(self, call_id: str, events: list[LiveEvent]) -> list[LiveEvent]:
        for e in events:
            self.bus.publish(call_id, e)
        return events
