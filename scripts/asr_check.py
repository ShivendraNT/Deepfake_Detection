"""Pre-demo check for Satya's ears: is a local speech engine installed, is the model cached, and
is it fast enough to keep up with a live call on THIS laptop?

    make doctor            # = uv run python scripts/asr_check.py

The first run downloads the Whisper weights once (the only network use; never in a unit test).
If `.cache/replay/cfo_call_en.wav` exists (`make demo-audio`), it is transcribed sentence by
sentence, like the live pipeline does, and the asks Satya would flag are printed.
Exit code 0 = ready for a live call, 1 = not ready (the message says what to do).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from satyapan.adapters.transcribe_local import (
    SAMPLE_RATE,
    LocalTranscriber,
    UnavailableTranscriber,
    build_transcriber,
    decode_wav,
)
from satyapan.asks.phrasebook import extract_cues, extract_live_asks
from satyapan.context import strip_context
REPLAY = ROOT / ".cache" / "replay" / "cfo_call_en.wav"


def _sentences(samples: np.ndarray) -> list[np.ndarray]:
    """Cut at pauses of 0.5 s or more (a rough stand-in for the capture window's segmenter)."""
    frame = int(SAMPLE_RATE * 0.03)
    n = samples.size // frame
    loud = [
        float(np.sqrt(np.mean(samples[i * frame : (i + 1) * frame] ** 2))) > 0.01 for i in range(n)
    ]
    pieces: list[np.ndarray] = []
    start: int | None = None
    quiet = 0
    for i, is_loud in enumerate(loud):
        if is_loud:
            start = i if start is None else start
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= 17:
                pieces.append(samples[start * frame : (i - quiet + 4) * frame])
                start, quiet = None, 0
    if start is not None:
        pieces.append(samples[start * frame :])
    return pieces


def main() -> int:
    engine = build_transcriber()
    if isinstance(engine, UnavailableTranscriber):
        print(f"✗ Ears: {engine.reason}")
        return 1
    assert isinstance(engine, LocalTranscriber)
    print(f"• Engine: {engine.engine} · model {engine.model} · language {engine.status.language}")
    print("• Loading and warming up (first run downloads the model once)…")
    try:
        engine.warm_up()
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic script
        print(f"✗ Ears: could not load the model: {type(exc).__name__}: {exc}")
        return 1
    print(f"✓ Ears ready in {engine.status.warmup_ms:.0f} ms")

    if not REPLAY.exists():
        print("• No replay audio yet. Run `make demo-audio` to test on the demo call.")
        return 0

    samples = decode_wav(REPLAY.read_bytes())
    worst = 0.0
    for piece in _sentences(samples):
        seconds = piece.size / SAMPLE_RATE
        t0 = time.perf_counter()
        result = engine.transcribe_samples(piece)
        took = time.perf_counter() - t0
        worst = max(worst, took)
        cleaned = strip_context(result.text).cleaned
        asks = sorted({span.ask_type.value for span in extract_live_asks(cleaned)})
        cues = sorted({cue.code for cue in extract_cues(result.text)})
        print(f"  [{seconds:4.1f}s audio → {took:4.2f}s] {result.text}")
        if asks or cues:
            print(f"      asks {asks or '-'} · cues {cues or '-'}")
    if worst > 2.5:
        print(
            f"! The slowest sentence took {worst:.1f} s. For snappier captions on this laptop, "
            "start the engine with SATYAPAN_ASR_MODEL=base (or tiny.en)."
        )
    else:
        print(f"✓ Fast enough for live captions (slowest sentence {worst:.1f} s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
