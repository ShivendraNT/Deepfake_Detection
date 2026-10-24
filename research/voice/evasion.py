"""Cheap ways an attacker could try to slip a cloned voice past Satya: a paired test.

    python -m research.voice.evasion     # -> results/voice_evasion.{json,md}

The In-the-Wild test clips that the product would judge (seeded test subset of bench.py,
>= 3 s of speech) go through the product's own scorer (the installed ONNX files, frozen
thresholds in config/voice_thresholds.json) as they are and after each edit:

* noise:  white noise at 10 dB SNR (a noisy street; seeded);
* speed:  10 % faster, pitch kept (ffmpeg atempo 1.1);
* pitch:  two semitones up, duration kept (asetrate + atempo).

Nothing is fitted. AUC uses a bootstrap over speakers; the change is paired per clip.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np  # provenance: seeded-resampling-ok

from research.metrics import auroc
from research.video.stats import cluster_ci, cluster_paired_diff, wilson
from research.voice.bench import subset, test_subset
from research.voice.data import ROOT, SEED, load

EDITS = ("clean", "noise", "speed", "pitch")


def _ffmpeg(x: np.ndarray, filt: str) -> np.ndarray:
    import soundfile as sf

    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.wav", Path(d) / "out.wav"
        sf.write(src, x, 16000, subtype="PCM_16")
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
                        "-filter:a", filt, "-ar", "16000", "-ac", "1", str(dst)],
                       check=True)  # fmt: skip
        y, _ = sf.read(dst, dtype="float32")
    return y


def edit(x: np.ndarray, how: str, rng: np.random.Generator) -> np.ndarray:
    if how == "clean":
        return x
    if how == "noise":
        p = float(np.mean(x**2)) or 1e-8
        n = rng.standard_normal(len(x)).astype(np.float32) * np.sqrt(p / 10.0)  # 10 dB SNR
        return np.clip(x + n, -1, 1).astype(np.float32)
    if how == "speed":
        return _ffmpeg(x, "atempo=1.1")
    if how == "pitch":
        r = 2 ** (2 / 12)
        return _ffmpeg(x, f"asetrate={16000 * r:.0f},aresample=16000,atempo={1 / r:.6f}")
    raise ValueError(how)


def main() -> None:
    from satyapan.voice.audio_io import estimate_speech_seconds
    from satyapan.voice.detector import load_default_detector
    from satyapan.voice.rules import MIN_SPEECH_SECONDS, load_thresholds

    thr = load_thresholds(ROOT / "config" / "voice_thresholds.json")
    scorer = load_default_detector(thr.model_version)
    sp = load("test_itw")
    sp = subset(sp, test_subset("test_itw", sp))
    keep = np.flatnonzero([estimate_speech_seconds(a) >= MIN_SPEECH_SECONDS for a in sp.audio])
    sp = subset(sp, keep)
    rng = np.random.default_rng(SEED)
    scores = {h: np.array([scorer.score_windows([edit(x, h, rng)])[0] for x in sp.audio])
              for h in EDITS}  # fmt: skip
    y, g = sp.labels, sp.speakers

    def auc(yy, ss):
        return auroc(yy.tolist(), ss.tolist())

    out: dict = {"n_bonafide": int((y == 0).sum()), "n_spoof": int(y.sum()),
                 "model": thr.model_version, "tau_hi": thr.tau_hi, "tau_lo": thr.tau_lo}  # fmt: skip
    for h in EDITS:
        s = scores[h]
        out[h] = {
            "auc": cluster_ci(auc, y, s, g),
            "spoof_flagged": wilson(int((s[y == 1] >= thr.tau_lo).sum()), int(y.sum())),
            "bonafide_flagged": wilson(int((s[y == 0] >= thr.tau_lo).sum()), int((y == 0).sum())),
        }
        if h != "clean":
            out[h]["delta_auc"] = cluster_paired_diff(auc, y, s, scores["clean"], g)
    res = ROOT / "results"
    (res / "voice_evasion.json").write_text(json.dumps(out, indent=1) + "\n")
    (res / "voice_evasion.md").write_text(render(out))
    print(render(out))


def _r(w: dict) -> str:
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def render(o: dict) -> str:
    names = {"clean": "as recorded", "noise": "+ white noise, 10 dB SNR",
             "speed": "10 % faster (pitch kept)", "pitch": "2 semitones up (duration kept)"}  # fmt: skip
    lines = [
        "# Voice evasion attempts (research/voice/evasion.py)",
        "",
        f"In-the-Wild test clips with >= 3 s of speech ({o['n_bonafide']} bonafide, "
        f"{o['n_spoof']} spoof), the product's scorer `{o['model']}`, frozen tau_lo "
        f"{o['tau_lo']:.3f}. Flagged = VERIFY or above for a one-window voice note.",
        "",
        "| Edit | AUC [95% CI] | change vs as recorded (paired) | fakes flagged | genuine flagged |",
        "|---|---|---|---|---|",
    ]
    for h in EDITS:
        e, a = o[h], o[h]["auc"]
        d = e.get("delta_auc")
        dd = "–" if d is None else f"{d['value']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}]"
        lines.append(f"| {names[h]} | {a['value']:.3f} [{a['low']:.3f}, {a['high']:.3f}] | {dd} "
                     f"| {_r(e['spoof_flagged'])} | {_r(e['bonafide_flagged'])} |")  # fmt: skip
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
