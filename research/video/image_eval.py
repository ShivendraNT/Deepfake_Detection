"""Still images: GenD on ONE face crop (the photo / screenshot path of Satya).

    python -m research.video.image_eval    # -> config/image_face_thresholds.json + results/

A dropped photo has one face, not a 6 s window, so it needs its own operating point. Every
number comes from crops GenD already scored for the video benchmark (hf_baselines.py), so the
crop, model and data are the same:

* thresholds: 1% / 5% FPR over single crops of the FF++ val REAL videos, per channel
  condition, the highest kept (fitted before any test crop is read);
* test: every scored crop of FF++ test (DF/F2F/FS/NT + FaceShifter) and DFDC, one crop = one
  "photo"; AUC with a bootstrap over identity clusters, rates with Wilson intervals.
"""

from __future__ import annotations

import json

import numpy as np

from research.metrics import auroc, threshold_at_fpr
from research.video.data import ROOT
from research.video.hf_baselines import cache_path, items
from research.video.stats import cluster_ci, wilson

MODEL = "gend_clip_l14"
CONDITIONS = ("orig", "call720", "call360")


def crops(split: str, cond: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(logits, labels, identity, method) over every scored crop of a split."""
    s, y, g, m = [], [], [], []
    for it in items():
        f = cache_path(MODEL, cond, it)
        if it.split != split or not f.exists():
            continue
        lg = np.load(f)
        s += lg.tolist()
        y += [it.label] * len(lg)
        g += [it.identity] * len(lg)
        m += [it.method] * len(lg)
    return np.array(s), np.array(y), np.array(g), np.array(m)


def main() -> None:
    per = {}
    for cond in CONDITIONS:
        s, y, _, _ = crops("val", cond)
        neg = s[y == 0].tolist()
        if len(neg) < 100:
            continue
        per[cond] = {
            "tau_hi": float(threshold_at_fpr(neg, 0.01)),
            "tau_lo": float(threshold_at_fpr(neg, 0.05)),
            "n_real_crops": len(neg),
        }
    tau_hi = max(v["tau_hi"] for v in per.values())
    tau_lo = min(max(v["tau_lo"] for v in per.values()), tau_hi)
    cfg = {
        "model": f"{MODEL}.onnx",
        "tau_hi_logit": round(tau_hi, 4),
        "tau_lo_logit": round(tau_lo, 4),
        "calibration_set": "single GenD crops of FF++ c23 val REAL videos, 1% / 5% FPR per "
        f"channel condition {sorted(per)}, max kept; NOT phone photos",
        "calibrated": False,
        "per_condition": per,
    }
    (ROOT / "config" / "image_face_thresholds.json").write_text(json.dumps(cfg, indent=1) + "\n")
    report: dict = {"thresholds": cfg, "test": {}}
    for cond in CONDITIONS:
        for split, name in (("test", "ffpp_test"), ("xtest", "dfdc")):
            s, y, g, m = crops(split, cond)
            if len(s) == 0 or len(set(y.tolist())) < 2:
                continue
            row = {
                "n_real_crops": int((y == 0).sum()),
                "n_fake_crops": int((y == 1).sum()),
                "auc": cluster_ci(lambda a, b: auroc(a.tolist(), b.tolist()), y, s, g),
                "tpr@tau_hi": wilson(int((s[y == 1] >= tau_hi).sum()), int((y == 1).sum())),
                "fpr@tau_hi": wilson(int((s[y == 0] >= tau_hi).sum()), int((y == 0).sum())),
                "tpr@tau_lo": wilson(int((s[y == 1] >= tau_lo).sum()), int((y == 1).sum())),
                "fpr@tau_lo": wilson(int((s[y == 0] >= tau_lo).sum()), int((y == 0).sum())),
            }
            if split == "test":
                row["auc_per_method"] = {
                    meth: round(auroc(y[(m == meth) | (y == 0)].tolist(),
                                      s[(m == meth) | (y == 0)].tolist()), 4)
                    for meth in sorted(set(m.tolist()) - {"real"})
                }  # fmt: skip
            report["test"][f"{name}/{cond}"] = row
            print(name, cond, row["auc"], row["tpr@tau_hi"]["value"], row["fpr@tau_hi"]["value"])
    (ROOT / "results" / "image_face_benchmark.json").write_text(json.dumps(report, indent=1) + "\n")
    (ROOT / "results" / "image_face_benchmark.md").write_text(render(report))


def _ci(x: dict) -> str:
    return f"{x['value']:.3f} [{x['low']:.3f}, {x['high']:.3f}]"


def _rate(w: dict) -> str:
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def render(r: dict) -> str:
    t = r["thresholds"]
    out = [
        "# Still-image face check: GenD on one face crop (research/video/image_eval.py)",
        "",
        f"Thresholds (logit) frozen on val real crops: tau_hi {t['tau_hi_logit']} (1% FPR), "
        f"tau_lo {t['tau_lo_logit']} (5%). One crop = one photo. AUC: identity-cluster "
        "bootstrap 95% CI; rates: Wilson 95%.",
        "",
        "| Set / channel | real / fake crops | AUC | fakes flagged @ tau_hi "
        "| reals flagged @ tau_hi | fakes @ tau_lo | reals @ tau_lo |",
        "|---|---|---|---|---|---|---|",
    ]
    for k, v in r["test"].items():
        out.append(
            f"| {k} | {v['n_real_crops']} / {v['n_fake_crops']} | {_ci(v['auc'])} | "
            f"{_rate(v['tpr@tau_hi'])} | {_rate(v['fpr@tau_hi'])} | {_rate(v['tpr@tau_lo'])} | "
            f"{_rate(v['fpr@tau_lo'])} |"
        )
    for k, v in r["test"].items():
        if "auc_per_method" in v:
            out.append("")
            out.append(f"{k} AUC per method: " + ", ".join(
                f"{a} {b:.3f}" for a, b in v["auc_per_method"].items()))  # fmt: skip
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
