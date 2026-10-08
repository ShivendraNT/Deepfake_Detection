from __future__ import annotations

import subprocess

import numpy as np

SAMPLE_RATE = 16_000
WINDOW_SECONDS = 5.0
MIN_WINDOW_SECONDS = 1.0
FRAME_SECONDS = 0.030
VAD_ENERGY_THRESHOLD = 0.01


def decode_to_16k_mono(data: bytes, mime: str) -> np.ndarray:
    """Run `ffmpeg -i pipe:0 -ac 1 -ar 16000 -f f32le pipe:1` and return a numpy float32 array.
    Raise ValueError on decode failure (caller -> GreyReason.PARSE_FAILURE)."""
    if not data:
        raise ValueError("Empty audio data")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-f",
        "f32le",
        "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=60)
    except Exception as exc:
        raise ValueError(f"ffmpeg execution failed: {exc}") from exc

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore").strip()
        raise ValueError(f"ffmpeg failed to decode ({mime}): {err}")

    if not proc.stdout:
        raise ValueError("ffmpeg produced empty audio stream")

    return np.frombuffer(proc.stdout, dtype=np.float32)


def split_windows(samples: np.ndarray, window_s: float = WINDOW_SECONDS) -> list[np.ndarray]:
    """Non-overlapping 5 s windows (hop 5 s). Drop a final window shorter than 1 s."""
    hop = int(window_s * SAMPLE_RATE)
    min_samples = int(MIN_WINDOW_SECONDS * SAMPLE_RATE)
    windows: list[np.ndarray] = []
    n = len(samples)
    for start in range(0, n, hop):
        chunk = samples[start : start + hop]
        if len(chunk) >= min_samples:
            windows.append(chunk)
    return windows


def estimate_speech_seconds(samples: np.ndarray) -> float:
    """Simple energy VAD: count 30 ms frames with RMS > 0.01, times 0.03."""
    frame_samples = int(FRAME_SECONDS * SAMPLE_RATE)
    if len(samples) < frame_samples:
        return 0.0
    n_frames = len(samples) // frame_samples
    trimmed = samples[: n_frames * frame_samples].reshape(n_frames, frame_samples)
    rms = np.sqrt(np.mean(trimmed**2, axis=1))
    active_frames = int(np.sum(rms > VAD_ENERGY_THRESHOLD))
    return float(active_frames * FRAME_SECONDS)
