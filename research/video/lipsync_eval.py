"""Lip-sync cue on a controlled audio-visual mismatch test (DFDC real videos, consenting actors).

    python -m research.video.lipsync_eval

FaceForensics++ has no audio and DFDC fakes keep the original voice, so neither tests the
"real footage + someone else's / a cloned voice" scam directly. Here every DFDC REAL video in
the test pool (with speech) is scored four ways, re-using the mouth track already extracted
(the video is identical; only the audio changes):

  matched   its own audio                                      (negative class)
  swapped   another real video's audio (seeded derangement)    (dubbed / wrong speaker)
  tts       a synthetic Piper TTS voice saying other words     (cloned-voice-over-real-video)
  desync    its own audio delayed by 1.0 s                     (gross A/V offset)

Score = -av_corr (zero parameters; nothing is fitted). Writes results/video_lipsync.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave

import numpy as np  # provenance: seeded-resampling-ok

from research.video.data import ROOT, SEED, dfdc_items
from research.video.extract import out_paths
from research.video.fit_fusion import MAX_T_START
from research.video.records import load_records
from research.video.stats import summarize
from satyapan.video.features import window_features, windows

SR = 16000
TTS_DIR = ROOT / ".cache" / "lipsync_tts"
VOICE = ROOT / ".cache" / "piper" / "en_US-ryan-medium.onnx"
# Neutral filler sentences (fictional, no real names): the content does not matter, only that
# the words are not the ones the face is saying.
SENTENCES = [
    "Thanks for joining, I just wanted to go over the quarterly numbers with you.",
    "The shipment is delayed by two days because of the weather at the port.",
    "Can you send me the updated spreadsheet before the end of the day?",
    "We should schedule a follow up meeting with the vendor next week.",
    "I think the new design looks much better than the previous version.",
    "Please make sure the team has access to the shared folder.",
    "The client asked for a revised quote with the extra items included.",
    "Let us keep the agenda short today, we have three things to cover.",
    "I will check with accounts and get back to you this afternoon.",
    "The training session has moved to the second floor conference room.",
    "Remember to submit your travel claims before Friday.",
    "Our internet connection was unstable this morning, sorry about that.",
]


def tts_clips() -> list[np.ndarray]:
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    clips = []
    for i in range(len(SENTENCES)):
        a, b = SENTENCES[i], SENTENCES[(i + 5) % len(SENTENCES)]
        path = TTS_DIR / f"clip_{i:02d}.wav"
        if not path.exists():
            subprocess.run(
                [sys.executable, "-m", "piper", "-m", str(VOICE), "-f", str(path)],
                input=f"{a} {b}".encode(),
                check=True,
                capture_output=True,
            )
        with wave.open(str(path), "rb") as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
            rate = w.getframerate()
        n = int(len(pcm) * SR / rate)
        clips.append(
            np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
        )
    return clips


def video_score(recs, audio: np.ndarray | None) -> tuple[float, float]:
    """(mean -av_corr over windows with speech, fraction of windows that abstained)."""
    vals, total = [], 0
    for s, e in windows(recs[0].t, recs[-1].t + 1e-6):
        if s > MAX_T_START + 1e-6:
            continue
        total += 1
        f = window_features([r for r in recs if s <= r.t < e], audio, SR, 0.0, [])
        if np.isfinite(f["av_corr"]):
            vals.append(-f["av_corr"])
    return (float(np.mean(vals)) if vals else float("nan"), 1 - len(vals) / max(total, 1))


def main() -> None:
    items = [i for i in dfdc_items() if i.label == 0]
    loaded = []
    for it in items:
        npz, _ = out_paths(it, "orig")
        if not npz.exists():
            continue
        recs, _, audio = load_records(npz)
        if audio is not None and len(audio) >= 6 * SR:
            loaded.append((it, recs, audio))
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(loaded))
    while np.any(perm == np.arange(len(loaded))):  # derangement: never your own audio
        perm = rng.permutation(len(loaded))
    clips = tts_clips()
    delay = np.zeros(SR, np.float32)
    rows: dict[str, list[tuple[float, str]]] = {
        k: [] for k in ("matched", "swapped", "tts", "desync")
    }
    abstain: dict[str, list[float]] = {k: [] for k in rows}
    for i, (it, recs, audio) in enumerate(loaded):
        variants = {
            "matched": audio,
            "swapped": loaded[perm[i]][2],
            "tts": clips[i % len(clips)],
            "desync": np.concatenate([delay, audio]),
        }
        for name, a in variants.items():
            s, ab = video_score(recs, a)
            rows[name].append((s, it.identity))
            abstain[name].append(ab)
    report: dict[str, object] = {
        "videos": len(loaded),
        "score": "-av_corr (no fitting)",
        "comparisons": {},
    }
    for name in ("swapped", "tts", "desync"):
        y, s, g = [], [], []
        for lab, src in ((0, rows["matched"]), (1, rows[name])):
            for score, ident in src:
                if np.isfinite(score):
                    y.append(lab)
                    s.append(score)
                    g.append(ident)
        report["comparisons"][f"matched_vs_{name}"] = summarize(y, s, g)  # type: ignore[index]
    report["abstained_window_fraction"] = {
        k: round(float(np.mean(v)), 4) for k, v in abstain.items()
    }
    out = ROOT / "results" / "video_lipsync.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
