"""Imperceptibility PROXIES for the Voice Seal: PESQ-WB and STOI against the clean original,
with plain codecs (no seal) as anchors. Synthetic voices only; first 30 s of each voice.

PESQ (ITU-T P.862.2 wideband, `pesq` package) and STOI (`pystoi`) are objective proxies. PESQ is
known to be lenient on slow level changes, so these numbers do NOT replace a listening test
(procedure in research/seal/README.md).

Run: python research/seal/quality.py     Output: results/seal_quality.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

try:
    from research.seal import channels as ch
    from research.seal.common import RESULTS, VOICES_DIR, git_commit, sha256_file, tool_versions
except ImportError:  # run as a plain script
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.seal import channels as ch
    from research.seal.common import RESULTS, VOICES_DIR, git_commit, sha256_file, tool_versions

from satyapan.seal import tesla  # noqa: E402
from satyapan.seal import voiceseal as vs  # noqa: E402

AMPS = (1.0, 1.5, 2.0, 2.5)


def main() -> None:
    try:
        from pesq import pesq
        from pystoi import stoi
    except ImportError as e:  # report honestly instead of inventing numbers
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "seal_quality.json").write_text(
            json.dumps({"status": "not run", "reason": f"missing package: {e.name}"}, indent=1)
        )
        raise SystemExit(f"pesq/pystoi not installed ({e.name}); wrote a 'not run' note") from e
    from scipy.io import wavfile

    voices = sorted(p.stem for p in VOICES_DIR.glob("*.wav"))
    _, keys = tesla.make_chain(b"quality-seed", 50)
    scores: dict[str, dict[str, list[float]]] = {}

    def add(name: str, ref: np.ndarray, deg: np.ndarray) -> None:
        deg = deg[: len(ref)]
        if len(deg) < len(ref):
            deg = np.pad(deg, (0, len(ref) - len(deg)))
        d = scores.setdefault(name, {"pesq_wb": [], "stoi": []})
        d["pesq_wb"].append(float(pesq(vs.SR, ref, deg, "wb")))
        d["stoi"].append(float(stoi(ref, deg, vs.SR, extended=False)))

    for v in voices:
        sr, raw = wavfile.read(VOICES_DIR / f"{v}.wav")
        x = (raw.astype(np.float64) / 32768.0)[: 30 * vs.SR]
        for amp in AMPS:
            add(
                f"seal_{amp}dB",
                x,
                vs.embed(x, keys, "meet:abc-defg-hij", vs.SealParams(amp_db=amp)),
            )
        sealed = vs.embed(x, keys, "meet:abc-defg-hij")
        add("seal_2.0dB_then_opus16", x, ch.opus(sealed, 16, 16000))
        add("anchor_opus16_no_seal", x, ch.opus(x, 16, 16000))
        add("anchor_opus32_no_seal", x, ch.opus(x, 32))
        add("anchor_mp3_32_no_seal", x, ch.mp3(x, 32))
        print(v, {k: round(d["pesq_wb"][-1], 3) for k, d in scores.items()}, flush=True)
    out: dict[str, Any] = {
        "what": "PESQ-WB and STOI vs the clean original (proxies, not a listening test)",
        "format": "per condition: mean, min, n over voices (first 30 s of each)",
        "script": "research/seal/quality.py",
        "voices": voices,
        "audio_sha256": {f"{v}.wav": sha256_file(VOICES_DIR / f"{v}.wav") for v in voices},
        "git_commit": git_commit(),
        "tools": tool_versions(),
        "conditions": {
            k: {
                m: {
                    "mean": round(float(np.mean(s)), 3),
                    "min": round(float(np.min(s)), 3),
                    "n": len(s),
                }
                for m, s in d.items()
            }
            for k, d in scores.items()
        },
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "seal_quality.json").write_text(json.dumps(out, indent=1))
    for k, d in out["conditions"].items():
        print(
            f"{k:26s} PESQ-WB {d['pesq_wb']['mean']:.2f} (min {d['pesq_wb']['min']:.2f})  "
            f"STOI {d['stoi']['mean']:.3f}"
        )


if __name__ == "__main__":
    main()
