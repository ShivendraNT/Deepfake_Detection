"""Audio decoding to 16 kHz mono float32 via ffmpeg (subprocess). TASK T17."""

from __future__ import annotations

from typing import Any

SAMPLE_RATE = 16_000
WINDOW_SECONDS = 5.0


def decode_to_16k_mono(data: bytes, mime: str) -> Any:
    """Run `ffmpeg -i pipe:0 -ac 1 -ar 16000 -f f32le pipe:1` and return a numpy float32 array.
    Raise ValueError on decode failure (caller -> GreyReason.PARSE_FAILURE)."""
    raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")


def split_windows(samples: Any, window_s: float = WINDOW_SECONDS) -> list[Any]:
    """Non-overlapping 5 s windows (hop 5 s). Drop a final window shorter than 1 s."""
    raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")


def estimate_speech_seconds(samples: Any) -> float:
    """Simple energy VAD: count 30 ms frames with RMS > 0.01, times 0.03."""
    raise NotImplementedError("T17: see docs/tasks/T17-voice-uploads.md")
