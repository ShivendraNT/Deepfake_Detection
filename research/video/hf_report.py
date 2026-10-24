"""Matched-protocol report for the off-the-shelf detectors (hf_baselines.py).

Reads the cached per-crop logits, builds one score per video (mean fake-logit over the same
K crops for every model), applies the pre-registered rule of docs/VIDEO_DEEPFAKE.md 5b on the
FF++ val split, and writes results/video_external.{json,md}. Test sets select nothing.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.metrics import auroc, threshold_at_fpr
from research.video.data import FFPP_UNSEEN
from research.video.hf_baselines import (
    EXTERNAL,
    HF_LOGITS,
    K_CROPS,
    OURS_LOGITS,
    RESULTS,
    cache_path,
    items,
    pick,
)
from research.video.stats import cluster_ci, cluster_paired_diff, wilson

OURS = "satya_sbi"
SELECT_CONDITION = "call360"
CALL_GATE_AUC = 0.70  # models below this on orig val are not run on the call conditions


def _auc(y: np.ndarray, s: np.ndarray) -> float:
    return auroc(y.tolist(), s.tolist())


def video_scores(model: str, condition: str) -> pd.DataFrame:
    rows = []
    for it in items():
        if model == OURS:
            f = OURS_LOGITS / condition / (it.key.replace("/", "__") + ".npy")
            lg = np.load(f) if f.exists() else None
            lg = None if lg is None else lg[pick(len(lg))]
        else:
            f = cache_path(model, condition, it)
            lg = np.load(f) if f.exists() else None
        if lg is None:
            continue
        rows.append(
            {
                "key": it.key, "split": it.split, "method": it.method, "label": it.label,
                "identity": it.identity, "n_crops": len(lg),
                "s": float(np.mean(lg)) if len(lg) else float("nan"),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def _block(v: pd.DataFrame, tau: float | None) -> dict[str, object]:
    out: dict[str, object] = {"n_real": int((v.label == 0).sum()), "n_fake": int(v.label.sum())}
    if v.label.nunique() == 2:
        out["auc"] = cluster_ci(_auc, v.label.to_numpy(), v.s.to_numpy(), v.identity.to_numpy())
    if tau is not None:
        fake, real = v[v.label == 1], v[v.label == 0]
        out["tpr@tau"] = wilson(int((fake.s >= tau).sum()), len(fake))
        out["fpr@tau"] = wilson(int((real.s >= tau).sum()), len(real))
    return out


def evaluate(model: str, condition: str) -> dict[str, object] | None:
    v = video_scores(model, condition)
    if v.empty:
        return None
    judged = v[np.isfinite(v.s)]
    val = judged[judged.split == "val"]
    tau = (
        float(threshold_at_fpr(val[val.label == 0].s.tolist(), 0.01))
        if (val.label == 0).any()
        else None
    )
    test = judged[judged.split == "test"]
    seen = test[(test.label == 0) | ~test.method.isin(FFPP_UNSEEN)]
    res: dict[str, object] = {
        "videos_scored": int(len(v)),
        "videos_without_face": int(len(v) - len(judged)),
        "tau_1pct_val": tau,
        "val": _block(val, None),
        "ffpp_test_seen": _block(seen, tau),
        "ffpp_test_all": _block(test, tau),
        "dfdc": _block(judged[judged.split == "xtest"], tau),
        "per_method": {},
    }
    for m in sorted(set(test.method) - {"real"}):
        sub = test[(test.label == 0) | (test.method == m)]
        res["per_method"][m] = _block(sub, None)  # type: ignore[index]
    return res


def paired(model: str, condition: str, split: str) -> dict[str, float] | None:
    """AUC(model) - AUC(our SBI CNN) on the same videos, identity clusters resampled."""
    a, b = video_scores(model, condition), video_scores(OURS, condition)
    both = a.merge(b[["key", "s"]], on="key", suffixes=("_a", "_b"))
    both = both[(both.split == split) & np.isfinite(both.s_a) & np.isfinite(both.s_b)]
    if both.label.nunique() < 2:
        return None
    return cluster_paired_diff(
        _auc, both.label.to_numpy(), both.s_a.to_numpy(), both.s_b.to_numpy(),
        both.identity.to_numpy(),
    )  # fmt: skip


def call_gate() -> list[str]:
    """External models whose orig val AUC >= CALL_GATE_AUC (scored on the call conditions)."""
    keep = []
    for e in EXTERNAL:
        r = evaluate(e.name, "orig")
        auc = r and r["val"].get("auc")  # type: ignore[union-attr]
        if isinstance(auc, dict) and auc["value"] >= CALL_GATE_AUC:
            keep.append(e.name)
    return keep


def select(report: dict[str, dict[str, object]]) -> dict[str, object]:
    """docs/VIDEO_DEEPFAKE.md 5b: GenD replaces the SBI CNN only if its call360 val AUC beats
    the SBI CNN's by more than one bootstrap SE of the paired difference."""
    d = paired("gend_clip_l14", SELECT_CONDITION, "val")
    if d is None:
        return {"decision": "pending", "reason": f"GenD not scored on {SELECT_CONDITION} val"}
    win = d["value"] > d["se"]
    return {
        "rule": "delta val AUC (GenD - SBI CNN), call360, must exceed 1 bootstrap SE",
        "delta": d,
        "decision": "gend_clip_l14" if win else OURS,
    }


def main(conditions: list[str] | tuple[str, ...] = ("orig", "call720", "call360")) -> None:
    models = [OURS, *[e.name for e in EXTERNAL]]
    report: dict[str, object] = {"k_crops": K_CROPS, "models": {}, "conditions": {}}
    for e in EXTERNAL:
        report["models"][e.name] = {  # type: ignore[index]
            "repo": e.repo, "revision": e.revision, "licence": e.licence,
            "params_m": e.params_m, "trained_on": e.trained_on,
            "ffpp_val_test_unseen": e.ffpp_clean, "note": e.note,
        }  # fmt: skip
    lat = HF_LOGITS / "latency.json"
    report["latency_ms_per_crop"] = json.loads(lat.read_text()) if lat.exists() else None
    for cond in conditions:
        block: dict[str, object] = {}
        for m in models:
            r = evaluate(m, cond)
            if r is None:
                continue
            if m != OURS:
                r["delta_auc_vs_satya_sbi"] = {
                    s: paired(m, cond, s) for s in ("val", "test", "xtest")
                }
            block[m] = r
        report["conditions"][cond] = block  # type: ignore[index]
    report["selection"] = select(report)  # type: ignore[arg-type]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "video_external.json").write_text(json.dumps(report, indent=2) + "\n")
    (RESULTS / "video_external.md").write_text(render(report))
    print(render(report))


def _ci(x: object) -> str:
    if not isinstance(x, dict) or "value" not in x:
        return "–"
    return f"{x['value']:.3f} [{x['low']:.3f}, {x['high']:.3f}]"


def _rate(w: object) -> str:
    if not isinstance(w, dict) or w.get("value") is None:
        return "–"
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.0f}, {100 * hi:.0f}]"


def render(r: dict) -> str:
    out = [
        "# Off-the-shelf detectors vs ours, matched protocol (research/video/hf_baselines.py)",
        "",
        f"Same stored face crops (K = {r['k_crops']} per 9.2 s clip), same videos, identity-"
        "cluster bootstrap 95% CIs, tau = 1% FPR on val reals of the same condition. Rule and "
        "candidates fixed before scoring: docs/VIDEO_DEEPFAKE.md 5b. FF++ rows of models "
        "marked * may include videos they were trained on (training lists unpublished).",
        "",
        "| Model | Hub id @ revision | Licence | Params (M) | Trained on |",
        "|---|---|---|---|---|",
        "| satya_sbi | ours (`research/video/train_sbi.py`) | FF++ terms | 4.0 "
        "| FF++ train **reals** + self-blended pseudo-fakes |",
    ]
    for name, m in r["models"].items():
        out.append(
            f"| {name} | `{m['repo']}` @ {m['revision'][:7]} | {m['licence']} | "
            f"{m['params_m']:g} | {m['trained_on']} |"
        )
    out.append("")
    for cond, block in r["conditions"].items():
        out += [
            f"## Condition `{cond}`",
            "",
            "| Model | val AUC | FF++ test AUC (4 seen) | FaceShifter AUC (unseen) "
            "| DFDC AUC (unseen) | DFDC TPR @ tau | DFDC FPR @ tau |",
            "|---|---|---|---|---|---|---|",
        ]
        for m, e in block.items():
            star = "" if m == OURS or r["models"][m]["ffpp_val_test_unseen"] else " *"
            fsh = e["per_method"].get("FaceShifter", {}).get("auc")
            out.append(
                f"| {m}{star} | {_ci(e['val'].get('auc'))} | "
                f"{_ci(e['ffpp_test_seen'].get('auc'))} | {_ci(fsh)} | "
                f"{_ci(e['dfdc'].get('auc'))} | {_rate(e['dfdc'].get('tpr@tau'))} | "
                f"{_rate(e['dfdc'].get('fpr@tau'))} |"
            )
        deltas = [(m, e["delta_auc_vs_satya_sbi"]) for m, e in block.items() if m != OURS]
        if deltas:
            out += [
                "",
                "Paired delta AUC vs our SBI CNN (same videos):",
                "",
                "| Model | val | FF++ test | DFDC |",
                "|---|---|---|---|",
            ]
            for m, d in deltas:
                out.append(
                    f"| {m} | {_ci(d.get('val'))} | {_ci(d.get('test'))} | {_ci(d.get('xtest'))} |"
                )
        out.append("")
    sel = r["selection"]
    out += ["## Pre-registered selection (val only)", "", f"Decision: **{sel['decision']}**."]
    if "delta" in sel:
        d = sel["delta"]
        out.append(
            f"GenD - SBI val AUC under call360: {d['value']:+.3f} (bootstrap SE {d['se']:.3f}, "
            f"95% CI [{d['low']:.3f}, {d['high']:.3f}])."
        )
    if r.get("latency_ms_per_crop"):
        out += ["", "CPU latency, ms per crop (batch 1): " + ", ".join(
            f"{k} {v:.0f}" for k, v in r["latency_ms_per_crop"].items()
        )]  # fmt: skip
    return "\n".join(out) + "\n"
