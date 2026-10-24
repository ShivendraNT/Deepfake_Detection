"""Live-call event contract between the extension (T07/T10) and the backend (T11). CONTRACT FILE.

Events travel as JSON lines / server-sent events. Each has a "type" discriminator.
A recorded stream for UI development lives in extension/replay/sample_events.jsonl.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from satyapan.contracts.common import Model
from satyapan.contracts.enums import AskType, Band, ReasonCode, VideoLabel, VoiceLabel


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


class VideoEvent(Model):
    """Video deepfake check for the other person's face (docs/VIDEO_DEEPFAKE.md).

    `cues` names which checks looked unusual in the latest window ("blend", "pulse", "light",
    "lipsync"); `coverage` says whether the face was usable; `problem` says why not
    ("no_face", "face_too_small", "bad_lighting", "too_short"). Never a raw score for makers.
    """

    type: Literal["video"] = "video"
    call_id: str
    window_index: int
    label: VideoLabel
    consecutive_over_hi: int = 0
    cues: list[str] = Field(default_factory=list)
    coverage: Literal["usable", "degraded", "incomplete"] = "usable"
    problem: str | None = None
    score: float | None = None  # stripped for maker role


class TranscriptSpan(Model):
    """A highlight inside `TranscriptEvent.text` (character offsets, end exclusive).

    kind "ask": an A1-A7 ask that became a deterministic signal (the policy decides its effect).
    kind "cue": an informational context cue (RUSH, AUTHORITY, UNREACHABLE, AMOUNT) that is
    shown to the user and NEVER changes a band.
    """

    kind: Literal["ask", "cue"]
    code: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class TranscriptEvent(Model):
    type: Literal["transcript"] = "transcript"
    call_id: str
    chunk_index: int
    t_start_s: float
    text: str
    language: str = "unknown"
    # Finale additions (all optional so recorded streams stay valid).
    t_end_s: float | None = None
    spans: list[TranscriptSpan] = Field(default_factory=list)
    latency_ms: float | None = None  # speech engine time for this utterance


class AskEvent(Model):
    type: Literal["ask"] = "ask"
    call_id: str
    chunk_index: int
    ask_type: AskType
    reason_code: ReasonCode
    span_text: str
    t_s: float | None = None  # seconds into the call where the ask was heard


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
    # Finale: machine-readable status, e.g. "asr_unavailable", "decode_failed".
    code: str | None = None


LiveEvent = Annotated[
    VoiceEvent | VideoEvent | TranscriptEvent | AskEvent | BandEvent | StatusEvent,
    Field(discriminator="type"),
]
LIVE_EVENT_ADAPTER: TypeAdapter[LiveEvent] = TypeAdapter(LiveEvent)
