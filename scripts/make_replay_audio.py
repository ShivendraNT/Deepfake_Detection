"""Generate the DEMO REPLAY call audio with an offline synthetic voice (Piper TTS).

The voice is a public synthetic voice (rhasspy/piper-voices, en_US "ryan"), not a real person,
so it is fine under docs/DATA_POLICY.md. Audio is git-ignored: run this once per laptop.

    make demo-audio        # = uv run --with piper-tts python scripts/make_replay_audio.py

Writes .cache/replay/cfo_call_en.wav (16 kHz mono PCM16, git-ignored). The backend serves it at
/companion/replay/cfo_call_en.wav and Satya plays it through the real pipeline, always labelled
"DEMO REPLAY — NOT LIVE CAPTURE".
"""

from __future__ import annotations

import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".cache" / "replay"  # media never lives under data/ (tests/contracts)
VOICE_DIR = ROOT / ".cache" / "piper"
VOICE = "en_US-ryan-medium"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/{file}"

# The deepfake-CFO script (fictional people and accounts). Pauses between sentences let the
# utterance segmenter cut naturally, like a real caller.
SCRIPT = [
    "Hi Priya, this is Rajesh. I am stuck in a board meeting, so I can't talk long.",
    "We are closing a confidential acquisition today. "
    "I need you to transfer forty eight lakh rupees to a new escrow account.",
    "I will send you the account details on chat. "
    "Please don't loop in Arjun, keep this between us.",
    "Skip the usual approval. I will sign it off later.",
]


def _voice() -> Path:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    model = VOICE_DIR / f"{VOICE}.onnx"
    for file in (f"{VOICE}.onnx", f"{VOICE}.onnx.json"):
        target = VOICE_DIR / file
        if not target.exists():
            print(f"downloading {file} …")
            urllib.request.urlretrieve(VOICE_URL.format(file=file), target)  # noqa: S310
    return model


def _synth(model: Path, text: str, out: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "piper", "-m", str(model), "-f", str(out)],
        input=text.encode(),
        check=True,
        capture_output=True,
    )


def _to_16k(path: Path) -> list[int]:
    import numpy as np

    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if rate != 16000:
        n = int(round(len(data) * 16000 / rate))
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data)
    return [int(x) for x in np.clip(data, -32768, 32767)]


def main() -> None:
    model = _voice()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[int] = [0] * 8000  # 0.5 s lead-in
    for index, sentence in enumerate(SCRIPT):
        part = OUT_DIR / f"_part{index}.wav"
        _synth(model, sentence, part)
        samples += _to_16k(part) + [0] * 14400  # 0.9 s pause between sentences
        part.unlink()
    out = OUT_DIR / "cfo_call_en.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(int(s).to_bytes(2, "little", signed=True) for s in samples))
    print(f"wrote {out.relative_to(ROOT)} ({len(samples) / 16000:.1f} s)")


if __name__ == "__main__":
    main()
