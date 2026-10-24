"""The video benchmark: frozen models + frozen thresholds on held-out test sets, once.

    python -m research.video.run_benchmark

Reads config/video_fusion.json + config/video_thresholds.json (fitted by fit_fusion.py on
train/val only) and the window tables. Writes results/video_benchmark.json and
results/video_benchmark.md. Every number is video-level with a 95% identity-cluster bootstrap
interval (AUC, EER) or a Wilson interval (alert rates). Nothing here is fitted.

Sets: FF++ c23 test (official split; DF/F2F/FS/NT seen by the fusion head, FaceShifter never
seen by anything), DFDC parts 0-2 (cross-dataset, never seen), each under the call-channel
conditions that were extracted (orig, call720, call360).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.metrics import auroc
from research.video.data import DATA, ROOT
from research.video.fit_fusion import MAX_T_START, MODELS, SETS
from research.video.stats import cluster_paired_diff, summarize, wilson
from research.video.tables import BLEND, table_path
from satyapan.video.fusion import FusionModel
from satyapan.video.rules import classify_windows, load_thresholds

RESULTS = ROOT / "results"
SHIPPED_MODEL = "fusion:shipped"
CONDITIONS = ("orig", "call720", "call360")
SEEN = ("Deepfakes", "Face2Face", "FaceSwap", "NeuralTextures")


def score_windows(df: pd.DataFrame, cnn: str = BLEND) -> dict[str, np.ndarray]:
    """Window scores for every model; NaN where the window abstained (no usable face)."""
    out: dict[str, np.ndarray] = {}
    usable = df["usable"].to_numpy() == 1
    for name in SETS if cnn == BLEND else ():  # the cue-set fusions were fitted on SBI logits
        m = FusionModel.load(MODELS / f"fusion_{name}.json")
        s = m.score(df[list(m.features)].to_numpy(float))
        out[f"fusion:{name}"] = np.where(usable, s, np.nan)
    shipped = FusionModel.load(ROOT / "config" / "video_fusion.json")
    s = shipped.score(df[list(shipped.features)].to_numpy(float))
    out[SHIPPED_MODEL] = np.where(usable, s, np.nan)
    out["cnn_raw"] = np.where(usable, df["blend"].to_numpy(float), np.nan)  # zero-fit baseline
    out["lipsync_raw"] = np.where(usable, -df["av_corr"].to_numpy(float), np.nan)
    # Shortcut checks: capture properties, not the face. A high AUC here would mean the
    # dataset leaks a confound (it should sit near 0.5 on FF++, where fakes reuse the frames).
    out["shortcut:face_px"] = np.where(usable, df["face_px"].to_numpy(float), np.nan)
    out["shortcut:luma"] = np.where(usable, df["luma"].to_numpy(float), np.nan)
    return out


def per_video(df: pd.DataFrame, s: np.ndarray) -> pd.DataFrame:
    d = df[["key", "label", "identity", "method", "w_index"]].copy()
    d["s"] = s
    d = d.sort_values(["key", "w_index"])
    agg = d.groupby("key").agg(
        label=("label", "first"),
        identity=("identity", "first"),
        method=("method", "first"),
        s=("s", lambda v: float(np.nanmean(v)) if np.isfinite(v).any() else np.nan),
        windows=("s", lambda v: [None if not np.isfinite(x) else float(x) for x in v]),
    )
    return agg.reset_index()


def rule_rates(v: pd.DataFrame, thr) -> dict[str, object]:
    labels = [classify_windows(w, thr).label.value for w in v["windows"]]
    v = v.assign(rule=labels)
    out: dict[str, object] = {}
    for lab, name in ((1, "fake"), (0, "real")):
        sub = v[v.label == lab]
        n = len(sub)
        out[name] = {
            r: wilson(int((sub.rule == r).sum()), n)
            for r in ("likely_synthetic", "inconclusive", "no_signs")
        }
    return out


def evaluate(
    df: pd.DataFrame, scores: dict[str, np.ndarray], thr, fakes: tuple[str, ...] | None
) -> dict[str, object]:
    sel = (df.label == 0) | (df.method.isin(fakes) if fakes else (df.label == 1))
    sub = df[sel]
    res: dict[str, object] = {}
    for model, s in scores.items():
        v = per_video(sub, s[sel.to_numpy()])
        judged = v[np.isfinite(v.s)]
        if judged.label.nunique() < 2:
            continue
        entry = summarize(judged.label.tolist(), judged.s.tolist(), judged.identity.tolist())
        entry["abstained_videos"] = int(len(v) - len(judged))
        if model == SHIPPED_MODEL:
            entry["rule"] = rule_rates(v, thr)
        res[model] = entry
    # Does the shipped fusion beat the zero-fit CNN score on the same videos?
    a = per_video(sub, scores[SHIPPED_MODEL][sel.to_numpy()])
    b = per_video(sub, scores["cnn_raw"][sel.to_numpy()])
    both = a.merge(b[["key", "s"]], on="key", suffixes=("_a", "_b"))
    both = both[np.isfinite(both.s_a) & np.isfinite(both.s_b)]
    if both.label.nunique() == 2:
        res["delta_auc_shipped_minus_cnn_raw"] = cluster_paired_diff(
            lambda yy, ss: auroc(yy.tolist(), ss.tolist()),
            both.label.tolist(),
            both.s_a.tolist(),
            both.s_b.tolist(),
            both.identity.tolist(),
        )
    return res


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--cnn", default=BLEND, help="must be the CNN the shipped config uses")
    ap.add_argument("--tag", help="write results/video_benchmark__<tag>.* (a non-shipped run)")
    a = ap.parse_args()
    shipped_cnn = (FusionModel.load(ROOT / "config" / "video_fusion.json").cnn or {}).get(
        "file", "blend_b0.onnx"
    )
    if (a.cnn == BLEND) != (shipped_cnn == "blend_b0.onnx"):
        raise SystemExit(f"config/video_fusion.json is fitted for {shipped_cnn}, not {a.cnn}")
    thr = load_thresholds()
    fit_log = DATA / "logs" / ("fit_fusion.json" if a.cnn == BLEND else f"fit_fusion__{a.cnn}.json")
    report: dict[str, object] = {
        "cnn": a.cnn,
        "thresholds": json.loads((ROOT / "config" / "video_thresholds.json").read_text()),
        "fit": json.loads(fit_log.read_text()) if fit_log.exists() else None,
        "conditions": {},
    }
    for cond in CONDITIONS:
        path = table_path(cond, a.cnn)
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df = df[df.t_start <= MAX_T_START + 1e-6].reset_index(drop=True)
        scores = score_windows(df, a.cnn)
        blocks: dict[str, object] = {}
        test = df.split == "test"
        if test.any():
            t = df[test].reset_index(drop=True)
            ts = {k: v[test.to_numpy()] for k, v in scores.items()}
            blocks["ffpp_test_all"] = evaluate(t, ts, thr, None)
            blocks["ffpp_test_seen4"] = evaluate(t, ts, thr, SEEN)
            for m in (*SEEN, "FaceShifter"):
                blocks[f"ffpp_test_{m}"] = evaluate(t, ts, thr, (m,))
        x = df.split == "xtest"
        if x.any():
            d = df[x].reset_index(drop=True)
            blocks["dfdc"] = evaluate(d, {k: v[x.to_numpy()] for k, v in scores.items()}, thr, None)
        val = df.split == "val"
        if val.any() and cond == "orig":
            d = df[val].reset_index(drop=True)
            blocks["ffpp_val"] = evaluate(
                d, {k: v[val.to_numpy()] for k, v in scores.items()}, thr, None
            )
        cov = df.groupby("split").usable.mean().round(4).to_dict()
        report["conditions"][cond] = {"sets": blocks, "usable_window_fraction": cov}  # type: ignore[index]
    RESULTS.mkdir(exist_ok=True)
    stem = "video_benchmark" + (f"__{a.tag}" if a.tag else "")
    (RESULTS / f"{stem}.json").write_text(json.dumps(report, indent=1) + "\n")
    (RESULTS / f"{stem}.md").write_text(render(report))
    print((RESULTS / f"{stem}.md").read_text())


def _ci(x: dict[str, float]) -> str:
    return f"{x['value']:.3f} [{x['low']:.3f}, {x['high']:.3f}]"


def _rate(w: dict[str, object]) -> str:
    if w.get("value") is None:
        return "n/a"
    lo, hi = w["ci95"]  # type: ignore[misc]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}] ({w['k']}/{w['n']})"  # type: ignore[operator]


def render(report: dict[str, object]) -> str:
    lines = [
        "# Video deepfake benchmark (generated by research/video/run_benchmark.py)",
        "",
        "Video-level. AUC/EER: 95% identity-cluster bootstrap (2000 resamples). Rates: Wilson "
        "95%. Thresholds frozen on FF++ val reals before this run; see "
        "docs/VIDEO_DEEPFAKE.md for the protocol.",
        "",
    ]
    thr = report["thresholds"]
    lines += [
        f"tau_hi = {thr['tau_hi']} (1% window FPR on val reals), tau_lo = {thr['tau_lo']} "  # type: ignore[index]
        f"(5%), model `{thr['model_version']}`, calibrated={thr['calibrated']}.",
        "",
    ]  # type: ignore[index]
    for cond, block in report["conditions"].items():  # type: ignore[union-attr]
        lines += [
            f"## Condition: {cond}",
            "",
            "| Set | Model | n real / fake | AUC | EER | abstained |",
            "|---|---|---|---|---|---|",
        ]
        for set_name, models in block["sets"].items():
            for model, e in models.items():
                if model.startswith("delta_"):
                    lines.append(f"| {set_name} | Δ AUC shipped − cnn_raw | | {_ci(e)} | | |")
                    continue
                lines.append(
                    f"| {set_name} | {model} | {e['n_real']} / {e['n_fake']} | "
                    f"{_ci(e['auc'])} | {_ci(e['eer'])} | {e['abstained_videos']} |"
                )
        lines += [
            "",
            "Product rule (fusion:shipped, >= 2 windows in a row >= tau_hi -> LIKELY_SYNTHETIC):",
            "",
            "| Set | fakes flagged (TPR) | reals flagged (FPR) | reals inconclusive |",
            "|---|---|---|---|",
        ]
        for set_name, models in block["sets"].items():
            e = models.get(SHIPPED_MODEL, {})
            r = e.get("rule") if isinstance(e, dict) else None
            if r:
                lines.append(
                    f"| {set_name} | {_rate(r['fake']['likely_synthetic'])} | "
                    f"{_rate(r['real']['likely_synthetic'])} | "
                    f"{_rate(r['real']['inconclusive'])} |"
                )
        lines += ["", f"Usable-window fraction by split: {block['usable_window_fraction']}", ""]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
