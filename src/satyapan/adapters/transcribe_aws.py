"""Amazon Transcribe batch adapter (hi-IN / en-IN) for uploaded voice notes. TASK T17.

See docs/tasks/T17-voice-uploads.md. Fallback: WhisperTranscriber (local).
"""

from __future__ import annotations

from satyapan.adapters.base import TranscriptResult
from satyapan.settings import Settings


class AwsTranscriber:
    """Uploads audio to the evidence bucket, starts a batch job with
    IdentifyLanguage over ["hi-IN", "en-IN"], polls with a deadline, returns the transcript."""

    def __init__(self, settings: Settings) -> None:
        raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")
