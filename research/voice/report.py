"""Render results/voice_benchmark.json as Markdown."""

from __future__ import annotations

from typing import Any

from research.voice.models import BY_NAME


def _ci(x: Any) -> str:
    if not isinstance(x, dict) or "value" not in x:
        return "–"
    return f"{x['value']:.3f} [{x['low']:.3f}, {x['high']:.3f}]"


def _rate(w: Any) -> str:
    if not isinstance(w, dict) or w.get("value") is None:
        return "–"
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def render(r: dict[str, Any]) -> str:
    sel = r["selection"]
    out = [
        "# Voice-clone benchmark (research/voice/bench.py)",
        "",
        "Protocol fixed before scoring: docs/VOICE_DEEPFAKE.md. Clips = first 5 s, 16 kHz. "
        "AUC/EER: 95% bootstrap over speakers; rates: Wilson 95%. In-the-Wild val and test "
        "speakers are disjoint; ASVspoof eval attacks A07-A19 (A16 = A04 and A19 = A06 were seen "
        "in training).",
        "",
        f"Our model (XLS-R layer 7 + LR on ASVspoof 2019 LA train): C = {r['ours_fit']['C']}, "
        f"speaker-grouped CV AUC {r['ours_fit']['cv_auc_mean']} ± {r['ours_fit']['cv_auc_sd']}.",
        "",
        "## Gate (val, clean; >= 0.70 to be tested)",
        "",
        "| Model | Licence | Trained on | val AUC |",
        "|---|---|---|---|",
    ]
    for name, auc in r["gate"].items():
        c = BY_NAME[name]
        out.append(f"| {name} | {c.licence} | {c.trained_on} | {_ci(auc)} |")
    out += [
        "",
        f"## Selection (val, {sel['rule']})",
        "",
        f"Decision: **{sel['decision']}**. Thresholds (logit): "
        f"tau_hi {sel['thresholds_logit']['tau_hi']:.3f}, "
        f"tau_lo {sel['thresholds_logit']['tau_lo']:.3f} "
        "(1% / 5% FPR on val bonafide, max over conditions).",
    ]
    for name, d in sel["candidates"].items():
        out.append(f"- {name} − ours: {d['value']:+.3f} (SE {d['se']:.3f})")
    for name, res in r["results"].items():
        out += [
            "",
            f"## {name}" + (" (shipped)" if name == sel["decision"] else ""),
            "",
            "| Set / channel | n bonafide / spoof | AUC | EER | spoof caught @ tau_hi "
            "| bonafide flagged @ tau_hi |",
            "|---|---|---|---|---|---|",
        ]
        for key, b in res.items():
            if key == "per_attack":
                continue
            out.append(
                f"| {key} | {b['n_bonafide']} / {b['n_spoof']} | {_ci(b['auc'])} | "
                f"{_ci(b['eer'])} | "
                f"{_rate(b.get('tpr@tau_hi'))} | {_rate(b.get('fpr@tau_hi'))} |"
            )
        if "per_attack" in res:
            out += ["", "ASVspoof 2019 eval, AUC per attack (vs all bonafide): " + ", ".join(
                f"{a} {v:.3f}" for a, v in res["per_attack"].items())]  # fmt: skip
    return "\n".join(out) + "\n"
