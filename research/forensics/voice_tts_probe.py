"""Probe: do the voice-deepfake candidates catch modern open-source TTS (Piper / VITS)?

    uv run python -m research.forensics.voice_tts_probe

Why: the shipped detector (gustking XLS-R, selected on In-the-Wild) scored a Piper voice
trained on LJSpeech exactly like real LJSpeech speech. This probe measures every candidate of
research/voice/models.py on
  real:  LJSpeech (public domain) and LibriTTS-R dev-clean (CC BY 4.0) utterances,
  fake:  Piper voices (en_US ljspeech/amy/ryan/lessac, en_GB alan, hi_IN rohan/pratham/
         priyamvada) reading LJSpeech / Hindi sentences,
all re-encoded as 16 kHz Opus like a WhatsApp voice note. Rule (fixed before running): a
candidate is added to the lab as a second, independent voice detector only if its AUC on this
probe is >= 0.90 AND at its 1%-FPR threshold on the real clips it flags >= 50% of TTS clips;
the threshold is then fitted on half of the real clips and checked on the other half.
"""

from __future__ import annotations

import io
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from research.forensics.aigen_select import auc

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT.parent / "satyapan-data" / "voiceprobe"
OUT = ROOT / "results" / "voice_tts_probe.json"
EN_TEXT = [
    "Please transfer the amount today, the officer is waiting for your confirmation.",
    "I cannot talk for long, they have taken my phone, please send the money quickly.",
    "Your account will be blocked unless you verify the details within one hour.",
    "This call is being recorded for the investigation, do not disconnect.",
    "We found a parcel in your name with illegal items, you must cooperate now.",
    "Do not tell anyone in your family, it will only make the case worse for you.",
]  # fmt: skip
HI_TEXT = [
    "आपका खाता बंद हो जाएगा, तुरंत ओटीपी बताइए।",
    "पापा मैं मुसीबत में हूँ, जल्दी पैसे भेज दीजिए।",
    "यह कॉल जाँच के लिए रिकॉर्ड हो रही है, फ़ोन मत काटिए।",
    "किसी को मत बताइए, नहीं तो केस और बिगड़ जाएगा।",
]  # fmt: skip
VOICES = {
    "en_US-ljspeech-high": "en/en_US/ljspeech/high/", "en_US-amy-medium": "en/en_US/amy/medium/",
    "en_US-ryan-high": "en/en_US/ryan/high/", "en_US-lessac-high": "en/en_US/lessac/high/",
    "en_GB-alan-medium": "en/en_GB/alan/medium/", "hi_IN-rohan-medium": "hi/hi_IN/rohan/medium/",
    "hi_IN-pratham-medium": "hi/hi_IN/pratham/medium/",
    "hi_IN-priyamvada-medium": "hi/hi_IN/priyamvada/medium/",
}  # fmt: skip


def opus16(x: np.ndarray, sr: int) -> np.ndarray:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    enc = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                          "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "pipe:1"],
                         input=buf.getvalue(), capture_output=True, check=True).stdout  # fmt: skip
    dec = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "pipe:1"], input=enc, capture_output=True, check=True).stdout  # fmt: skip
    return np.frombuffer(dec, np.float32).copy()


def real_clips(n_lj: int = 30, n_libri: int = 30) -> list[np.ndarray]:
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    out = []
    rng = np.random.default_rng(5)
    for i in rng.choice(np.arange(1, 13100), size=n_lj, replace=False):
        chap = 1 + (int(i) - 1) // 300
        try:
            p = hf_hub_download("flexthink/ljspeech", f"wavs/LJ{chap:03d}-{(int(i) % 300) + 1:04d}.wav",
                                repo_type="dataset")  # fmt: skip
        except Exception:  # noqa: BLE001
            continue
        with wave.open(p) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            out.append(opus16(x, w.getframerate()))
    p = hf_hub_download("mythicinfinity/libritts_r", "data/dev.clean/dev.clean-00000-of-00004.parquet",
                        repo_type="dataset")  # fmt: skip
    tab = pq.read_table(p, columns=["audio"])
    col = tab.column("audio")
    for i in rng.choice(len(col), size=min(n_libri, len(col)), replace=False):
        a = col[int(i)].as_py()
        import soundfile as sf

        x, sr = sf.read(io.BytesIO(a["bytes"]), dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        if len(x) > sr * 2:
            out.append(opus16(x, sr))
    return out


def tts_clips() -> list[tuple[str, np.ndarray]]:
    from huggingface_hub import hf_hub_download
    from piper import PiperVoice

    out = []
    for name, sub in VOICES.items():
        try:
            onnx = hf_hub_download("rhasspy/piper-voices", sub + name + ".onnx")
            hf_hub_download("rhasspy/piper-voices", sub + name + ".onnx.json")
        except Exception as exc:  # noqa: BLE001
            print("skip voice", name, exc)
            continue
        v = PiperVoice.load(onnx)
        texts = HI_TEXT if name.startswith("hi") else EN_TEXT
        for t in texts:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                v.synthesize_wav(t, w)
            buf.seek(0)
            with wave.open(buf) as w:
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
                out.append((name, opus16(x, w.getframerate())))
    return out


def main() -> None:
    from research.voice.models import CANDIDATES, hf_classifier

    reals = real_clips()
    fakes = tts_clips()
    print(f"real {len(reals)}, tts {len(fakes)}", flush=True)
    res: dict = {"rule": __doc__.split("Rule (fixed before running):")[1].strip(), "candidates": {},
                 "n_real": len(reals), "n_tts": len(fakes)}  # fmt: skip
    for c in CANDIDATES:
        if c.name == "satya_xlsr_l7":
            continue  # needs the research head files; it lost the original selection anyway
        try:
            clf = hf_classifier(c.name)

            def score(x: np.ndarray, clf=clf) -> float:  # mean over 5 s windows, like the lab
                n = 80000
                ws = [x[i : i + n] for i in range(0, max(1, len(x) - 16000), n)] or [x]
                return float(np.mean([clf(w) for w in ws if len(w) >= 16000] or [clf(x)]))
        except Exception as exc:  # noqa: BLE001
            print(c.name, "FAILED", exc, flush=True)
            continue
        r = np.array([score(x) for x in reals])
        f = np.array([score(x) for _, x in fakes])
        a = auc(f, r)
        thr = float(np.quantile(r, 0.99))
        per = {}
        for (name, _), s in zip(fakes, f, strict=True):
            per.setdefault(name, []).append(float(s >= thr))
        res["candidates"][c.name] = {"auc": a, "thr_1pct": thr, "tpr_at_1pct": float((f >= thr).mean()),
                                     "per_voice_tpr": {k: float(np.mean(v)) for k, v in per.items()},
                                     "real_scores": r.tolist(), "tts_scores": f.tolist()}  # fmt: skip
        print(f"{c.name}: AUC {a:.3f} TPR@1%FPR {(f >= thr).mean():.2f} "
              f"{ {k: round(float(np.mean(v)), 2) for k, v in per.items()} }", flush=True)  # fmt: skip
    OUT.write_text(json.dumps(res, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
