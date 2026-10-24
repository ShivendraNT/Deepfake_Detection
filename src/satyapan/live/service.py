"""Live call sessions. TASK T11 — docs/tasks/T11-live-transcript.md.

No LLM in the loop: alert text comes from templates (latency budget §5.5 in ARCHITECTURE).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from satyapan.adapters.base import Transcriber
from satyapan.asks.extractor import DETECTOR_NAME, ask_signals, normalise
from satyapan.asks.phrasebook import extract_cues, extract_live_asks
from satyapan.context import strip_context
from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import ASK_TO_REASON, Band, CaseKind, Lang, ReasonCode
from satyapan.contracts.evidence import AskSpan
from satyapan.contracts.live import (
    AskEvent,
    BandEvent,
    LiveEvent,
    StatusEvent,
    TranscriptEvent,
    TranscriptSpan,
    VideoEvent,
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
    client_voice: bool = False  # the client scores its own voice windows (extension)
    next_voice_index: int = 0  # server-scored windows (desktop app: scored here)
    last_band: Band = Band.PASS
    language: str | None = None  # speech language hint ("en", "hi"; None/"auto" = detect)
    # Video check (finale): per-call face stream; windows keep numbers only, never frames.
    video_stream: Any = None
    video_windows: list[Any] = field(default_factory=list)
    video_unavailable_sent: bool = False
    text_flagged: bool = False  # scam-text model fired on the transcript so far (kept once raised)
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
    # Finale: returns the VideoAnalyzer, or None when the video check is unavailable here.
    video_factory: Callable[[], Any] | None = None
    # Voice-clone model for clients that send only audio (the desktop capture window): every
    # utterance chunk is cut into 5 s windows and scored here, on this laptop.
    voice_factory: Callable[[], Any] | None = None
    # Returns the scam-text model (TextRiskModel), or None.
    text_factory: Callable[[], Any] | None = None

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
        self,
        call_id: str,
        chunk_index: int,
        audio: bytes,
        mime: str,
        t_start_s: float | None = None,
        t_end_s: float | None = None,
    ) -> list[LiveEvent]:
        """transcribe -> TranscriptEvent (with ask/cue highlight spans); live asks -> one
        AskEvent per NEW ask type; update case.signals with ask_signals; re-decide; if the band
        changed -> BandEvent with reason codes and SUGGESTED_LINES[EN]. Publish and return.

        Chunks are utterances cut at pauses by the capture window (finale), or fixed 10 s
        chunks from older clients (then t_start_s defaults to chunk_index * 10 s). A missing
        speech engine is reported as a StatusEvent, never hidden behind an empty transcript."""
        session = self.sessions[call_id]
        with session.lock:
            return self._handle_chunk(session, chunk_index, audio, mime, t_start_s, t_end_s)

    def _handle_chunk(
        self,
        session: LiveSession,
        chunk_index: int,
        audio: bytes,
        mime: str,
        t_start_s: float | None = None,
        t_end_s: float | None = None,
    ) -> list[LiveEvent]:
        call_id = session.call_id
        start_s = t_start_s if t_start_s is not None else chunk_index * CHUNK_SECONDS
        self._feed_video_audio(session, audio, start_s)
        voice_events = self._server_voice(session, audio, mime, start_s)
        t0 = time.perf_counter()
        try:
            hint = session.language if session.language not in (None, "auto") else None
            res = self.transcriber.transcribe(audio, mime, hint)
        except ValueError as exc:
            status = StatusEvent(call_id=call_id, message=str(exc), code="decode_failed")
            return voice_events + self._publish(call_id, [status])
        except RuntimeError as exc:
            status = StatusEvent(call_id=call_id, message=str(exc), code="asr_unavailable")
            return voice_events + self._publish(call_id, [status])
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        text = normalise(res.text)
        if not text:
            return voice_events
        session.transcript.append(text)

        # ADR-021: drop spoken warnings ("never share your OTP") before ask extraction.
        ask_text = strip_context(text).cleaned if self.context_filter else text
        spans = extract_live_asks(ask_text)

        events: list[LiveEvent] = [
            TranscriptEvent(
                call_id=call_id,
                chunk_index=chunk_index,
                t_start_s=start_s,
                t_end_s=t_end_s,
                text=text,
                language=res.language,
                spans=_highlights(text, spans),
                latency_ms=latency_ms,
            )
        ]

        seen = {s.ask_type for s in session.asks}
        for span in spans:
            if span.ask_type not in seen:
                seen.add(span.ask_type)
                events.append(
                    AskEvent(
                        call_id=call_id,
                        chunk_index=chunk_index,
                        ask_type=span.ask_type,
                        reason_code=ASK_TO_REASON[span.ask_type],
                        span_text=span.text,
                        t_s=start_s,
                    )
                )
            session.asks.append(span)

        # Asks only accumulate: rebuild the ask signals from every span seen in the call.
        others = [s for s in session.case.signals if s.detector != DETECTOR_NAME]
        new_asks = ask_signals(session.asks, evidence_id=f"ev_live_{call_id}")
        session.case = session.case.model_copy(update={"signals": others + new_asks})
        self._score_transcript(session)

        events += self._redecide(session)
        return voice_events + self._publish(call_id, events)

    def _server_voice(
        self, session: LiveSession, audio: bytes, mime: str, start_s: float
    ) -> list[LiveEvent]:
        """Score this chunk's 5 s windows with the voice-clone model (desktop clients).

        Skipped when the client already sends its own windows, when no model is installed
        (the health card says so), or when the chunk does not decode (the transcript path
        reports that). Only labels leave this function: makers never see a score."""
        scorer = self.voice_factory() if self.voice_factory and not session.client_voice else None
        if scorer is None:
            return []
        from satyapan.voice.audio_io import (
            SAMPLE_RATE,
            decode_to_16k_mono,
            estimate_speech_seconds,
            split_windows,
        )

        try:
            windows = split_windows(decode_to_16k_mono(audio, mime))
            scores = scorer.score_windows(windows) if windows else []
        except Exception:  # noqa: BLE001 - a broken chunk or model never breaks the call
            return []
        results, t = [], start_s
        for w, score in zip(windows, scores, strict=True):
            t_end = t + len(w) / SAMPLE_RATE
            results.append(
                VoiceWindowResult(
                    call_id=session.call_id,
                    window_index=session.next_voice_index,
                    t_start_s=t,
                    t_end_s=t_end,
                    score=float(min(1.0, max(0.0, score))),
                    speech_seconds=estimate_speech_seconds(w),
                    model_version=self.thresholds.model_version,
                )
            )
            session.next_voice_index += 1
            t = t_end
        return self._handle_voice(session, results) if results else []

    def handle_voice(self, call_id: str, windows: list[VoiceWindowResult]) -> list[LiveEvent]:
        """Append windows; classify_windows over ALL scores so far; replace the session's voice
        signal; emit VoiceEvent (score stripped) and BandEvent if the band changed."""
        session = self.sessions[call_id]
        if not windows:
            return []
        with session.lock:
            session.client_voice = True
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

    def handle_video(self, call_id: str, frames: list[tuple[float, Any]]) -> list[LiveEvent]:
        """Screen frames (t seconds, RGB array) of the other person's video. Windows that
        finish are scored, the video signal is replaced (ML, media group, raise-only) and the
        policy re-decides. Frames are dropped as soon as they are measured."""
        session = self.sessions[call_id]
        if not frames:
            return []
        with session.lock:
            return self._handle_video(session, frames)

    def _handle_video(
        self, session: LiveSession, frames: list[tuple[float, Any]]
    ) -> list[LiveEvent]:
        from satyapan.video.rules import VIDEO_CODES, video_signal

        call_id = session.call_id
        analyzer = self.video_factory() if self.video_factory is not None else None
        if analyzer is None:
            if session.video_unavailable_sent:
                return []
            session.video_unavailable_sent = True
            status = StatusEvent(
                call_id=call_id,
                message="The face check is not installed on this laptop (uv sync --extra "
                "video, then make video-models). Listening continues.",
                code="video_unavailable",
            )
            return self._publish(call_id, [status])
        if session.video_stream is None:
            session.video_stream = analyzer.new_stream()
        results = session.video_stream.add_frames(frames)
        if not results:
            return []
        session.video_windows.extend(results)
        verdict = analyzer.verdict(session.video_windows)
        last = results[-1]
        signal = video_signal(
            verdict, analyzer.thresholds, [f"ev_live_{call_id}_video"], cues=last.cues
        )
        others = [s for s in session.case.signals if s.code not in VIDEO_CODES]
        session.case = session.case.model_copy(update={"signals": [*others, signal]})
        problem = last.coverage.problem()
        events: list[LiveEvent] = [
            VideoEvent(
                call_id=call_id,
                window_index=last.index,
                label=verdict.label,
                consecutive_over_hi=verdict.max_consecutive_over_hi,
                cues=list(last.cues),
                coverage="usable" if problem is None else "incomplete",
                problem=problem,
                score=None,  # makers never see raw scores
            )
        ]
        events += self._redecide(session)
        return self._publish(call_id, events)

    def _score_transcript(self, session: LiveSession) -> None:
        """Scam-text model on the whole call so far. Raise-only: once it fires it stays."""
        if session.text_flagged or self.text_factory is None:
            return
        model = self.text_factory()
        if model is None:
            return
        from satyapan.textrisk.rules import text_signal

        text = " ".join(session.transcript)
        if len(text.split()) < 30:
            return
        sig = text_signal(model, text, [f"ev_live_{session.call_id}"])
        if sig is not None:
            session.text_flagged = True
            session.case = session.case.model_copy(update={"signals": [*session.case.signals, sig]})

    @staticmethod
    def _feed_video_audio(session: LiveSession, audio: bytes, start_s: float) -> None:
        """Give the face check the call audio for its lip-sync cue (same capture clock).
        Only plain PCM WAV utterances from the capture window; anything else is skipped."""
        if session.video_stream is None or audio[:4] != b"RIFF":
            return
        from satyapan.adapters.transcribe_local import SAMPLE_RATE, decode_wav

        try:
            session.video_stream.add_audio(decode_wav(audio), start_s, SAMPLE_RATE)
        except ValueError:
            return

    def stop_video(self, call_id: str) -> None:
        session = self.sessions.get(call_id)
        if session is not None and session.video_stream is not None:
            with session.lock:
                session.video_stream.close()
                session.video_stream = None

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


def _highlights(text: str, asks: list[AskSpan]) -> list[TranscriptSpan]:
    """Map ask spans (found on the context-filtered text) and cues back onto `text`.

    Offsets are searched case-insensitively in the display text; a span whose words were
    removed by the context filter is simply not highlighted (it did not become a signal)."""
    lower = text.lower()
    out: list[TranscriptSpan] = []
    taken: list[tuple[int, int]] = []

    def place(needle: str) -> tuple[int, int] | None:
        start = 0
        key = needle.lower()
        while key:
            i = lower.find(key, start)
            if i < 0:
                return None
            j = i + len(key)
            if all(j <= a or i >= b for a, b in taken):
                return i, j
            start = i + 1
        return None

    for span in asks:
        where = place(span.text)
        if where:
            taken.append(where)
            out.append(
                TranscriptSpan(kind="ask", code=span.ask_type.value, start=where[0], end=where[1])
            )
    for cue in extract_cues(text):
        if all(cue.end <= a or cue.start >= b for a, b in taken):
            taken.append((cue.start, cue.end))
            out.append(TranscriptSpan(kind="cue", code=cue.code, start=cue.start, end=cue.end))
    out.sort(key=lambda s: s.start)
    return out
