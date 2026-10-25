"""Would a denoiser in front of the voice check undo the noise evasion? A VALIDATION-only probe.

    python -m research.voice.denoise_probe    # -> results/voice_denoise_probe.{json,md}

results/voice_evasion.md shows that 10 dB of white noise hides cloned voices from the product's
scorer. Before any product change, this probe asks the question on In-the-Wild VAL clips only
(>= 3 s of speech; the test set is not touched): AUC of the product's scorer on

    clean · clean + denoiser · noisy · noisy + denoiser    (denoiser: ffmpeg afftdn)

Nothing ships from here. Adopting a front end would mean re-fitting the thresholds on denoised
val and one new frozen test run (docs/VOICE_DEEPFAKE.md, rule 4).
"""

from __future__ import annotations

import json

import numpy as np  # provenance: seeded-resampling-ok

from research.metrics import auroc
from research.video.stats import cluster_ci, cluster_paired_diff
from research.voice.bench import subset
from research.voice.data import ROOT, SEED, load
from research.voice.evasion import _ffmpeg, edit

DENOISE = "afftdn=nf=-25"
VERSIONS = ("clean", "clean+dn", "noisy", "noisy+dn")


def main() -> None:
    from satyapan.voice.audio_io import estimate_speech_seconds
    from satyapan.voice.detector import load_default_detector
    from satyapan.voice.rules import MIN_SPEECH_SECONDS, load_thresholds

    thr = load_thresholds(ROOT / "config" / "voice_thresholds.json")
    scorer = load_default_detector(thr.model_version)
    sp = load("val")
    keep = np.flatnonzero([estimate_speech_seconds(a) >= MIN_SPEECH_SECONDS for a in sp.audio])
    sp = subset(sp, keep)
    rng = np.random.default_rng(SEED + 7)
    scores: dict[str, list[float]] = {v: [] for v in VERSIONS}
    for x in sp.audio:
        noisy = edit(x, "noise", rng)
        for v, a in (("clean", x), ("clean+dn", _ffmpeg(x, DENOISE)), ("noisy", noisy),
                     ("noisy+dn", _ffmpeg(noisy, DENOISE))):  # fmt: skip
            scores[v].append(scorer.score_windows([a])[0])
    y, g = sp.labels, sp.speakers
    s = {v: np.array(scores[v]) for v in VERSIONS}

    def auc(yy, ss):
        return auroc(yy.tolist(), ss.tolist())

    out: dict = {"split": "val", "n_bonafide": int((y == 0).sum()), "n_spoof": int(y.sum()),
                 "denoiser": DENOISE, "model": thr.model_version}  # fmt: skip
    for v in VERSIONS:
        out[v] = {"auc": cluster_ci(auc, y, s[v], g),
                  "spoof_over_tau_lo": float((s[v][y == 1] >= thr.tau_lo).mean())}  # fmt: skip
    out["denoiser_gain_on_noisy"] = cluster_paired_diff(auc, y, s["noisy+dn"], s["noisy"], g)
    out["denoiser_cost_on_clean"] = cluster_paired_diff(auc, y, s["clean+dn"], s["clean"], g)
    res = ROOT / "results"
    (res / "voice_denoise_probe.json").write_text(json.dumps(out, indent=1) + "\n")
    (res / "voice_denoise_probe.md").write_text(render(out))
    print(render(out))


def render(o: dict) -> str:
    lines = [
        "# Denoiser probe on VALIDATION clips (research/voice/denoise_probe.py)",
        "",
        f"In-the-Wild val, >= 3 s speech ({o['n_bonafide']} bonafide, {o['n_spoof']} spoof); "
        f"scorer `{o['model']}`; denoiser `{o['denoiser']}`; noise = white, 10 dB SNR. The test "
        "set is not used. Fakes over tau_lo use the current thresholds, which were fitted "
        "without a denoiser.",
        "",
        "| Version | AUC [95% CI] | fakes over current tau_lo |",
        "|---|---|---|",
    ]
    for v in VERSIONS:
        a = o[v]["auc"]
        lines.append(f"| {v} | {a['value']:.3f} [{a['low']:.3f}, {a['high']:.3f}] | "
                     f"{100 * o[v]['spoof_over_tau_lo']:.1f}% |")  # fmt: skip
    gn, cc = o["denoiser_gain_on_noisy"], o["denoiser_cost_on_clean"]
    lines += [
        "",
        f"Denoiser on noisy clips: AUC {gn['value']:+.3f} [{gn['low']:+.3f}, {gn['high']:+.3f}]; "
        f"on clean clips: {cc['value']:+.3f} [{cc['low']:+.3f}, {cc['high']:+.3f}].",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
