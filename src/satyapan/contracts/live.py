"""Live-call event contract between the extension (T07/T10) and the backend (T11). CONTRACT FILE.

Events travel as JSON lines / server-sent events. Each has a "type" discriminator.
A recorded stream for UI development lives in extension/replay/sample_events.jsonl.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from satyapan.contracts.common import Model
from satyapan.contracts.enums import AskType, Band, ReasonCode, VoiceLabel


class VoiceWindowResult(Model):
    """One 5-second window scored on-device by the extension."""

    call_id: str
    window_index: int = Field(ge=0)
    t_start_s: float = Field(ge=0)
    t_end_s: float = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    speech_seconds: float = Field(ge=0)
    model_version: str


class VoiceEvent(Model):
    type: Literal["voice"] = "voice"
    call_id: str
    window_index: int
    label: VoiceLabel
    consecutive_over_hi: int = 0
    score: float | None = None  # stripped for maker role


class TranscriptEvent(Model):
    type: Literal["transcript"] = "transcript"
    call_id: str
    chunk_index: int
    t_start_s: float
    text: str
    language: str = "unknown"


class AskEvent(Model):
    type: Literal["ask"] = "ask"
    call_id: str
    chunk_index: int
    ask_type: AskType
    reason_code: ReasonCode
    span_text: str


class BandEvent(Model):
    type: Literal["band"] = "band"
    call_id: str
    band: Band
    reason_codes: list[ReasonCode]
    suggested_line: str | None = (
        None  # template text, e.g. "I'll process it once it's in the system."
    )


class StatusEvent(Model):
    type: Literal["status"] = "status"
    call_id: str
    message: str


LiveEvent = Annotated[
    VoiceEvent | TranscriptEvent | AskEvent | BandEvent | StatusEvent,
    Field(discriminator="type"),
]
LIVE_EVENT_ADAPTER: TypeAdapter[LiveEvent] = TypeAdapter(LiveEvent)
