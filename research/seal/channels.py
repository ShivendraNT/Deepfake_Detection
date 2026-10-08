"""Real codec chains for the Voice Seal evaluation (ffmpeg libopus / pcm_mulaw / libmp3lame,
sox opencore AMR-NB). Every chain is an actual encode + decode, not a simulation of a codec.

Packet loss is modelled pessimistically as zeroed 20 ms frames WITHOUT concealment; noise is
white Gaussian at a fixed SNR. Both use a seeded numpy Generator passed in by the caller, so a
re-run reproduces the same audio (seeds are recorded in the results manifest).
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np
from scipy.io import wavfile

SR = 16_000
Chain = Callable[[np.ndarray, np.random.Generator], np.ndarray]


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_wav16(path: Path, x: np.ndarray) -> None:
    wavfile.write(path, SR, np.round(np.clip(x, -1, 1) * 32767).astype(np.int16))


def decode16k(path: Path) -> np.ndarray:
    """Decode any file with ffmpeg to 16 kHz mono float64."""
    r = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(SR),
            "-f",
            "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float64)


def _ffmpeg_roundtrip(x: np.ndarray, enc_args: list[str], ext: str) -> np.ndarray:
    with tempfile.TemporaryDirectory() as d:
        src, mid = Path(d) / "in.wav", Path(d) / f"mid.{ext}"
        write_wav16(src, x)
        _run(
            ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src), *enc_args, str(mid)]
        )
        return decode16k(mid)


def _sox_amr(x: np.ndarray, mode: int) -> np.ndarray:
    with tempfile.TemporaryDirectory() as d:
        src, mid, dst = Path(d) / "in.wav", Path(d) / "mid.amr-nb", Path(d) / "out.wav"
        write_wav16(src, x)
        _run(["sox", str(src), "-r", "8000", "-c", "1", "-t", "amr-nb", "-C", str(mode), str(mid)])
        _run(["sox", "-t", "amr-nb", str(mid), "-r", str(SR), "-b", "16", str(dst)])
        return decode16k(dst)


def opus(x: np.ndarray, kbps: int, rate: int = 48_000) -> np.ndarray:
    args = ["-ar", str(rate), "-ac", "1", "-c:a", "libopus", "-b:a", f"{kbps}k"]
    return _ffmpeg_roundtrip(x, [*args, "-application", "voip"], "opus")


def g711(x: np.ndarray) -> np.ndarray:
    return _ffmpeg_roundtrip(x, ["-ar", "8000", "-ac", "1", "-c:a", "pcm_mulaw"], "wav")


def mp3(x: np.ndarray, kbps: int) -> np.ndarray:
    return _ffmpeg_roundtrip(
        x, ["-ar", "16000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", f"{kbps}k"], "mp3"
    )


def amr_nb(x: np.ndarray, mode: int = 7) -> np.ndarray:
    """mode 7 = 12.2 kbps (normal mobile call), mode 0 = 4.75 kbps (worst mode)."""
    return _sox_amr(x, mode)


def frame_loss(x: np.ndarray, rate: float, rng: np.random.Generator) -> np.ndarray:
    y = x.copy()
    n = int(0.02 * SR)
    for i in range(0, len(y), n):
        if rng.random() < rate:
            y[i : i + n] = 0
    return y


def add_noise(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    noise = rng.standard_normal(len(x))
    noise *= np.sqrt(np.mean(x**2) / (10 ** (snr_db / 10)) / np.mean(noise**2))
    return x + noise


# name -> (description, chain). Order = table order in results/seal_codec_eval.csv.
CHAINS: dict[str, tuple[str, Chain]] = {
    "clean": ("No codec", lambda x, rng: x),
    "opus32_meet": ("Opus 32 kbps 48 kHz (Meet-like)", lambda x, rng: opus(x, 32)),
    "opus24": ("Opus 24 kbps 48 kHz", lambda x, rng: opus(x, 24)),
    "opus16_voicenote": (
        "Opus 16 kbps 16 kHz (WhatsApp-style note)",
        lambda x, rng: opus(x, 16, 16000),
    ),
    "opus12": ("Opus 12 kbps 16 kHz", lambda x, rng: opus(x, 12, 16000)),
    "opus8_nb": ("Opus 8 kbps narrowband", lambda x, rng: opus(x, 8, 8000)),
    "amrnb_12.2": ("AMR-NB 12.2 kbps (mobile call)", lambda x, rng: amr_nb(x, 7)),
    "amrnb_4.75": ("AMR-NB 4.75 kbps (worst mode)", lambda x, rng: amr_nb(x, 0)),
    "g711_mulaw": ("G.711 mu-law (PSTN)", lambda x, rng: g711(x)),
    "mp3_32": ("MP3 32 kbps", lambda x, rng: mp3(x, 32)),
    "opus24_loss5": (
        "Opus 24k + 5% frame loss, no PLC",
        lambda x, rng: frame_loss(opus(x, 24), 0.05, rng),
    ),
    "opus24_noise15": (
        "Opus 24k + white noise 15 dB SNR",
        lambda x, rng: add_noise(opus(x, 24), 15, rng),
    ),
    "opus24_amrnb12.2": (
        "Opus 24k -> AMR-NB 12.2 (dial-in)",
        lambda x, rng: amr_nb(opus(x, 24), 7),
    ),
    "gain-9_opus16": ("-9 dB gain + Opus 16k", lambda x, rng: opus(x * 10 ** (-9 / 20), 16, 16000)),
}
