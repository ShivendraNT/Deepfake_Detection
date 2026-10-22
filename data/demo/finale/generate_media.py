"""Generate the F12 demo voice fixtures on demand.

The repository does not commit audio. This script writes clean, deterministic, synthetic
16 kHz mono 16-bit PCM WAV files with speech-like harmonic content, so the offline replay and
VAD paths can be exercised without any real person's voice.

Run from the repo root:
    uv run python data/demo/finale/generate_media.py
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2
DEFAULT_DURATION_SECONDS = 6.0
MIN_VALID_DURATION_SECONDS = 4.0

DEMO_FILENAMES = ("rajesh_cfo_call_en.wav", "rajesh_cfo_call_hi.wav")


def _sample_at(index: int, total_samples: int, sample_rate: int) -> int:
    """One speech-like PCM16 sample: a low fundamental, harmonics and a syllable envelope."""
    if total_samples <= 0 or sample_rate <= 0:
        return 0

    t = index / sample_rate
    fade_samples = max(1, int(0.05 * sample_rate))
    fade = min(1.0, index / fade_samples, (total_samples - 1 - index) / fade_samples)
    if fade <= 0.0:
        return 0

    # Harmonics around a 120 Hz voice-like fundamental.
    voice = (
        0.42 * math.sin(2.0 * math.pi * 120.0 * t)
        + 0.22 * math.sin(2.0 * math.pi * 240.0 * t + 0.35)
        + 0.12 * math.sin(2.0 * math.pi * 360.0 * t + 0.75)
        + 0.06 * math.sin(2.0 * math.pi * 720.0 * t + 1.10)
    )
    # Slow syllable/breath envelope so the file is not a flat test tone.
    syllable = 0.70 + 0.30 * math.sin(2.0 * math.pi * 3.2 * t)
    value = max(-1.0, min(1.0, voice * syllable * fade))
    return int(value * 32767)


def generate_demo_wav(
    output_path: Path,
    duration_seconds: float = DEFAULT_DURATION_SECONDS,
    sample_rate: int = SAMPLE_RATE,
) -> Path:
    """Write a deterministic 16 kHz mono 16-bit PCM WAV and return its path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_samples = max(0, int(round(duration_seconds * sample_rate)))
    frames = bytearray()
    for index in range(total_samples):
        frames += struct.pack("<h", _sample_at(index, total_samples, sample_rate))

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))

    return output_path


def validate_wav(path: Path) -> dict[str, int | float | bool]:
    """Validate the demo WAV contract and return its measured properties."""
    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()

    duration_s = frame_count / sample_rate if sample_rate > 0 else 0.0
    valid = (
        sample_rate == SAMPLE_RATE
        and channels == CHANNELS
        and sample_width == SAMPLE_WIDTH_BYTES
        and duration_s >= MIN_VALID_DURATION_SECONDS
    )
    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_s": duration_s,
        "valid": valid,
    }


def ensure_demo_wavs(directory: Path | None = None) -> list[Path]:
    """Generate any missing (or invalid) demo takes and return both paths."""
    base_dir = Path(directory) if directory is not None else Path(__file__).resolve().parent
    base_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for filename in DEMO_FILENAMES:
        path = base_dir / filename
        if not path.exists() or not validate_wav(path)["valid"]:
            generate_demo_wav(path, DEFAULT_DURATION_SECONDS, SAMPLE_RATE)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for demo_path in ensure_demo_wavs():
        info = validate_wav(demo_path)
        print(
            f"{demo_path.name}: {info['duration_s']:.1f}s, "
            f"{info['sample_rate']} Hz, {info['channels']} channel(s), valid={info['valid']}"
        )
