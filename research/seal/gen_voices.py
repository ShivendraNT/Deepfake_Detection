"""Generate the synthetic speech corpus for the Voice Seal evaluation (Kokoro-82M TTS).

No real person's voice is used: every file is TTS output from a stock Kokoro voice
(Apache-2.0 model). The audio is written OUTSIDE the repo, to $SATYAPAN_SEAL_DATA/voices
(default ~/.cache/satyapan/seal/voices), and is never committed. `run_codec_eval.py` hashes every
file into the data manifest in results/.

Model files are not in the repo. Download them once from the kokoro-onnx GitHub release
(thewh1teagle/kokoro-onnx, tag model-files-v1.0): `kokoro-v1.0.int8.onnx` and `voices-v1.0.bin`,
and pass their folder with --models (or set SATYAPAN_KOKORO_DIR).

    python research/seal/gen_voices.py --models /path/to/kokoro-models [voice ...]

Pauses between utterances follow a fixed cycle (no random numbers), so a re-run with the same
model files reproduces the same corpus.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

try:
    from research.seal.common import VOICES_DIR
except ImportError:  # run as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.seal.common import VOICES_DIR

OUT = VOICES_DIR
SR = 16_000

# Our own AP-finance sentences (synthetic, written for this probe; no dataset text).
EN = [
    "Priya, this is Rajesh. I need you to process an urgent payment before four today.",
    "The acquisition team has a new escrow account, I will share the details on chat.",
    "Please keep this confidential for now, the board has not announced it yet.",
    "Can you confirm the invoice number and the amount of two lakh eighty four thousand rupees?",
    "Our vendor in Pune has changed their bank, the new IFSC is in the email.",
    "Let us close the quarter cleanly, so release the pending logistics payments.",
    "I am about to board a flight, so just go ahead and I will approve it later.",
    "Arjun is on leave today, so you can skip his approval this one time.",
    "Send the payroll file to the auditor by evening, they need it for the review.",
    "The amount is forty eight lakh fifty thousand, and the beneficiary is a new account.",
    "Thank you, I will call you back after the meeting to check the status.",
    "We also need the GST invoice copies for the last three months, please.",
]
HI = [
    "प्रिया, मैं राजेश बोल रहा हूँ, आज चार बजे से पहले एक जरूरी पेमेंट करना है।",
    "नया खाता नंबर मैं ईमेल पर भेज रहा हूँ, कृपया उसी में ट्रांसफर करें।",
    "यह बात अभी किसी को मत बताना, बोर्ड ने अभी घोषणा नहीं की है।",
    "वेंडर ने अपना बैंक बदल लिया है, नया आईएफएससी कोड चालान में है।",
    "अर्जुन आज छुट्टी पर है, इसलिए उनकी मंजूरी की जरूरत नहीं है।",
    "राशि अड़तालीस लाख पचास हजार रुपये है, कृपया आज ही भेज दीजिए।",
    "मीटिंग के बाद मैं आपको वापस फोन करके स्टेटस पूछूँगा।",
    "पिछले तीन महीने के जीएसटी चालान भी चाहिए, धन्यवाद।",
]

# (voice, espeak language, sentences): 6 English and 4 Hindi stock voices.
VOICES: list[tuple[str, str, list[str]]] = [
    ("af_heart", "en-us", EN),
    ("am_michael", "en-us", EN),
    ("bf_emma", "en-gb", EN),
    ("bm_george", "en-gb", EN),
    ("am_adam", "en-us", EN),
    ("af_bella", "en-us", EN),
    ("hf_alpha", "hi", HI),
    ("hm_omega", "hi", HI),
    ("hf_beta", "hi", HI),
    ("hm_psi", "hi", HI),
]
PAUSES_S = (0.35, 0.6, 0.45, 0.8, 0.3, 0.7, 0.5)  # fixed cycle between utterances


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", default=os.environ.get("SATYAPAN_KOKORO_DIR", ""))
    ap.add_argument("voices", nargs="*", help="subset of voices (default: all 10)")
    a = ap.parse_args()
    if not a.models:
        raise SystemExit("pass --models <folder with kokoro-v1.0.int8.onnx + voices-v1.0.bin>")
    from kokoro_onnx import Kokoro  # research-only dependency

    models = Path(a.models)
    kokoro = Kokoro(str(models / "kokoro-v1.0.int8.onnx"), str(models / "voices-v1.0.bin"))
    OUT.mkdir(parents=True, exist_ok=True)
    for voice, lang, sentences in VOICES:
        if a.voices and voice not in a.voices:
            continue
        dst = OUT / f"{voice}.wav"
        if dst.exists():
            print(f"skip {dst.name} (exists)")
            continue
        t0 = time.time()
        parts: list[np.ndarray] = []
        for i, s in enumerate(sentences):
            samples, sr = kokoro.create(s, voice=voice, speed=1.0, lang=lang)
            assert sr == 24_000, sr
            parts.append(resample_poly(samples.astype(np.float64), 2, 3))  # 24 kHz -> 16 kHz
            parts.append(np.zeros(int(SR * PAUSES_S[i % len(PAUSES_S)])))
        y = np.concatenate(parts)
        y = 0.5 * y / (np.max(np.abs(y)) + 1e-9)
        wavfile.write(dst, SR, np.round(y * 32767).astype(np.int16))
        print(f"{voice}: {len(y) / SR:.1f} s audio in {time.time() - t0:.1f} s", flush=True)


if __name__ == "__main__":
    main()
