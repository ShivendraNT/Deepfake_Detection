"""Live call sessions. TASK T11 — docs/tasks/T11-live-transcript.md.

No LLM in the loop: alert text comes from templates (latency budget §5.5 in ARCHITECTURE).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from satyapan.adapters.base import Transcriber
from satyapan.contracts.case import Case
from satyapan.contracts.evidence import AskSpan
from satyapan.contracts.live import LiveEvent, VoiceWindowResult
from satyapan.master.store import MasterData
from satyapan.voice.rules import VoiceThresholds


@dataclass
class LiveSession:
    call_id: str
    case: Case
    transcript: list[str] = field(default_factory=list)
    asks: list[AskSpan] = field(default_factory=list)
    voice_windows: list[VoiceWindowResult] = field(default_factory=list)
    last_band: str = "PASS"


@dataclass
class EventBus:
    """Per-call asyncio queues for server-sent events."""

    queues: dict[str, list[asyncio.Queue[LiveEvent]]] = field(default_factory=dict)

    def publish(self, call_id: str, event: LiveEvent) -> None:
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")

    def subscribe(self, call_id: str) -> asyncio.Queue[LiveEvent]:
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")


@dataclass
class LiveService:
    master: MasterData
    transcriber: Transcriber
    thresholds: VoiceThresholds
    bus: EventBus = field(default_factory=EventBus)
    sessions: dict[str, LiveSession] = field(default_factory=dict)

    def start(self, call_id: str, maker_id: str) -> LiveSession:
        """Create a LIVE_CALL Case (id f"case_live_{call_id}") and a session."""
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")

    def handle_chunk(
        self, call_id: str, chunk_index: int, audio: bytes, mime: str
    ) -> list[LiveEvent]:
        """transcribe -> TranscriptEvent; extract_asks -> one AskEvent per NEW ask type;
        update case.signals with ask_signals; re-decide; if band changed -> BandEvent with
        reason codes and SUGGESTED_LINES[EN]. Publish every event on the bus and return them."""
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")

    def handle_voice(self, call_id: str, windows: list[VoiceWindowResult]) -> list[LiveEvent]:
        """Append windows; classify_windows over ALL scores so far; replace the session's voice
        signal; emit VoiceEvent (score stripped) and BandEvent if the band changed."""
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")
