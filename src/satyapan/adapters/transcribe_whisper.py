"""Local Whisper transcriber (mlx-whisper large-v3-turbo on Apple Silicon). TASK T11.

See docs/tasks/T11-live-transcript.md. Install: `uv sync --extra asr-mac` (macOS only).
Audio is converted to 16 kHz mono WAV with ffmpeg first (subprocess, no network).
"""

from __future__ import annotations

from satyapan.adapters.base import TranscriptResult

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


class WhisperTranscriber:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        raise NotImplementedError("T11: see docs/tasks/T11-live-transcript.md")
