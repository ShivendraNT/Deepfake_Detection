"""Local Whisper transcriber (mlx-whisper large-v3-turbo on Apple Silicon). TASK T11.

See docs/tasks/T11-live-transcript.md. Install: `uv sync --extra asr-mac` (macOS only).
Audio is converted to 16 kHz mono WAV with ffmpeg first (subprocess, no network).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from satyapan.adapters.base import TranscriptResult

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
FFMPEG_TIMEOUT_S = 30

_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/mpeg": "mp3"}


class WhisperTranscriber:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        try:
            import mlx_whisper  # lazy: only on Apple Silicon with the asr-mac extra
        except ImportError as exc:
            raise RuntimeError(
                "mlx-whisper is not installed; run `uv sync --extra asr-mac` (macOS only)"
            ) from exc
        self._mlx: Any = mlx_whisper
        self.model = model

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        ext = _EXT.get(mime.split(";")[0].strip(), "webm")
        with tempfile.TemporaryDirectory(prefix="satyapan_asr_") as tmp:
            src, wav = Path(tmp) / f"in.{ext}", Path(tmp) / "out.wav"
            src.write_bytes(audio)
            cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src)]
            cmd += ["-ar", "16000", "-ac", "1", str(wav)]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT_S)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError(f"ffmpeg could not decode {mime} audio") from exc
            out = self._mlx.transcribe(str(wav), path_or_hf_repo=self.model, language=language_hint)
        segments = out.get("segments") or []
        return TranscriptResult(
            text=str(out.get("text", "")).strip(),
            language=str(out.get("language") or "unknown"),
            duration_s=float(segments[-1]["end"]) if segments else 0.0,
            engine=f"mlx-whisper:{self.model}",
        )
