"""Fit the fusion model (CV-selected) and freeze the thresholds. Never reads a test set.

    python -m research.video.fit_fusion

Protocol (docs/VIDEO_DEEPFAKE.md §5):
1. FF++ `fusion_train` windows with a usable face (60 identity pairs, never seen by the CNN).
   For each cue set, 5-fold StratifiedGroupKFold (groups = FF++ source/target pair, so a face
   never sits on both sides of a fold) over C in a small grid; score = mean of the video's
   window probabilities; report CV video-AUC mean +- sd. Pick C by mean CV AUC.
2. Refit each cue set on all of fusion_train with its C. The set that ships
   (config/video_fusion.json) is chosen by the one-standard-error rule (Breiman et al.): the
   simplest set (fewest features) whose mean CV AUC is within one standard error of the best
   set's. This rule was fixed before any CNN or test number existed.
3. Thresholds from FF++ `val` REAL windows only: tau_hi = 1% window FPR, tau_lo = 5%, fitted
   per channel condition (orig, call720, call360) and the highest kept, so the false-alarm
   target holds on call-quality video too. Written to config/video_thresholds.json with
   calibrated=false (no webcam calibration yet).

    python -m research.video.fit_fusion --cnn gend_clip_l14

The same, with an off-the-shelf detector (hf_baselines.py) in the CNN slot, used only if it
wins the pre-registered rule of docs/VIDEO_DEEPFAKE.md 5b. It was trained on the FF++ train
split, so fusion_train cannot fit anything for it: the fusion is the identity on its mean
crop logit (a 1-D logistic fit would be monotone and give the same alerts at thresholds set on
val reals). Steps 1-2 are skipped, step 3 is the same.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np  # provenance: seeded-resampling-ok
import pandas as pd

from research.metrics import auroc, threshold_at_fpr
from research.video.data import DATA, ROOT, SEED
from research.video.tables import BLEND, table_path
from satyapan.video.features import CUES

MODELS = DATA / "models"
C_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0)
MAX_T_START = 3.0  # two windows per video (0-6 s, 3-9 s), the same for every set
SETS: dict[str, tuple[str, ...]] = {
    "blend": CUES["blend"],
    "pulse": CUES["pulse"],
    "light": CUES["light"],
    "pulse+light": CUES["pulse"] + CUES["light"],
    "visual": CUES["blend"] + CUES["pulse"] + CUES["light"],
}


def one_se_choice(cv: dict[str, dict[str, object]]) -> str:
    """Simplest cue set within one standard error (sd / sqrt(folds)) of the best mean."""
    best = max(cv, key=lambda k: float(cv[k]["cv_auc_mean"]))  # type: ignore[arg-type]
    se = float(cv[best]["cv_auc_sd"]) / np.sqrt(len(cv[best]["folds"]))  # type: ignore[arg-type]
    floor = float(cv[best]["cv_auc_mean"]) - se  # type: ignore[arg-type]
    ok = [k for k in cv if float(cv[k]["cv_auc_mean"]) >= floor]  # type: ignore[arg-type]
    return min(ok, key=lambda k: (len(SETS[k]), -float(cv[k]["cv_auc_mean"])))  # type: ignore[arg-type]


# Off-the-shelf CNNs that may take the slot: ONNX file (models/video/) and crop interval.
EXTERNAL_CNN = {"gend_clip_l14": {"file": "gend_clip_l14.onnx", "crop_every_s": 2.25}}


def load_table(condition: str = "orig", cnn: str = BLEND) -> pd.DataFrame:
    df = pd.read_csv(table_path(condition, cnn))
    return df[(df["t_start"] <= MAX_T_START + 1e-6)].copy()


def design_params(x: np.ndarray) -> dict[str, np.ndarray]:
    miss = ~np.isfinite(x)
    median = np.array([np.nanmedian(c) if np.isfinite(c).any() else 0.0 for c in x.T])
    filled = np.where(miss, median, x)
    mean, scale = filled.mean(axis=0), filled.std(axis=0)
    scale = np.where(scale > 1e-9, scale, 1.0)
    return {"median": median, "mean": mean, "scale": scale}


def design(x: np.ndarray, p: dict[str, np.ndarray]) -> np.ndarray:
    miss = ~np.isfinite(x)
    z = (np.where(miss, p["median"], x) - p["mean"]) / p["scale"]
    return np.hstack([z, miss.astype(float)])


def fit_lr(x: np.ndarray, y: np.ndarray, c: float) -> tuple[dict[str, np.ndarray], object]:
    from sklearn.linear_model import LogisticRegression

    p = design_params(x)
    lr = LogisticRegression(C=c, class_weight="balanced", max_iter=5000)
    lr.fit(design(x, p), y)
    return p, lr


def video_scores(df: pd.DataFrame, window_scores: np.ndarray) -> pd.DataFrame:
    d = df[["key", "label", "identity"]].copy()
    d["s"] = window_scores
    return (
        d.groupby("key")
        .agg(label=("label", "first"), identity=("identity", "first"), s=("s", "mean"))
        .reset_index()
    )


def cv_auc(df: pd.DataFrame, feats: tuple[str, ...], c: float) -> list[float]:
    from sklearn.model_selection import StratifiedGroupKFold

    vids = df.groupby("key").agg(label=("label", "first"), identity=("identity", "first"))
    folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    out = []
    for tr, va in folds.split(vids.index, vids["label"], vids["identity"]):
        tr_keys, va_keys = set(vids.index[tr]), set(vids.index[va])
        a, b = df[df.key.isin(tr_keys)], df[df.key.isin(va_keys)]
        p, lr = fit_lr(a[list(feats)].to_numpy(float), a["label"].to_numpy(), c)
        prob = lr.predict_proba(design(b[list(feats)].to_numpy(float), p))[:, 1]
        v = video_scores(b, prob)
        out.append(auroc(v["label"].tolist(), v["s"].tolist()))
    return out


def to_json(feats: tuple[str, ...], p: dict[str, np.ndarray], lr: object, version: str) -> dict:
    coef = np.asarray(lr.coef_).ravel()  # type: ignore[attr-defined]
    k = len(feats)
    return {
        "features": list(feats),
        "median": p["median"].tolist(),
        "mean": p["mean"].tolist(),
        "scale": p["scale"].tolist(),
        "coef": coef[:k].tolist(),
        "missing_coef": coef[k:].tolist(),
        "intercept": float(np.asarray(lr.intercept_).ravel()[0]),  # type: ignore[attr-defined]
        "version": version,
    }


def identity_fusion(cnn: str, onnx_sha: str, median: float) -> dict:
    return {
        "features": ["blend"], "median": [median], "mean": [0.0], "scale": [1.0],
        "coef": [1.0], "missing_coef": [0.0], "intercept": 0.0,
        "version": f"fusion-identity@{cnn}:{onnx_sha[:8]}", "cnn": EXTERNAL_CNN[cnn],
    }  # fmt: skip


def freeze_thresholds(model, cnn: str, version: str, n_val_videos: int) -> dict:
    """Step 3: 1% / 5% window FPR on val reals per condition; the highest is kept."""
    per_condition: dict[str, dict[str, float]] = {}
    n_windows: dict[str, int] = {}
    for cond in ("orig", "call720", "call360"):
        if not table_path(cond, cnn).exists():
            continue
        t = load_table(cond, cnn)
        vr = t[(t.split == "val") & (t.label == 0) & (t.usable == 1)]
        if vr.empty:
            continue
        sv = model.score(vr[list(model.features)].to_numpy(float)).tolist()
        per_condition[cond] = {
            "tau_hi": round(float(threshold_at_fpr(sv, 0.01)), 6),
            "tau_lo": round(float(threshold_at_fpr(sv, 0.05)), 6),
        }
        n_windows[cond] = int(len(vr))
    tau_hi = max(v["tau_hi"] for v in per_condition.values())
    tau_lo = min(max(v["tau_lo"] for v in per_condition.values()), tau_hi)
    return {
        "tau_hi": round(float(tau_hi), 6),
        "tau_lo": round(float(tau_lo), 6),
        "model_version": version,
        "calibrated": False,
        "calibration_set": f"FF++ c23 val reals ({n_val_videos} videos), usable 6 s "
        f"windows per channel condition {n_windows}; max over conditions; NOT webcam calls",
        "cue_flag_logit": 0.75,
        "fpr_targets": {"tau_hi": 0.01, "tau_lo": 0.05},
        "per_condition": per_condition,
    }


def main_external(cnn: str) -> None:
    from research.video.export_gend import FP32
    from satyapan.video.fusion import FusionModel

    onnx_sha = hashlib.sha256(FP32.read_bytes()).hexdigest()
    df = load_table("orig", cnn)
    val_real = df[(df.split == "val") & (df.label == 0) & (df.usable == 1)]
    median = float(np.nanmedian(val_real["blend"].to_numpy(float)))
    fusion_path = ROOT / "config" / "video_fusion.json"
    fusion_path.write_text(json.dumps(identity_fusion(cnn, onnx_sha, median), indent=1))
    model = FusionModel.load(fusion_path)
    fusion_sha = hashlib.sha256(fusion_path.read_bytes()).hexdigest()
    version = f"{cnn}:{onnx_sha[:12]}+fusion:{fusion_sha[:12]}"
    thresholds = freeze_thresholds(model, cnn, version, int(val_real.key.nunique()))
    (ROOT / "config" / "video_thresholds.json").write_text(json.dumps(thresholds, indent=1) + "\n")
    report = {"cnn": cnn, "onnx_sha256": onnx_sha, "fusion_sha256": fusion_sha,
              "thresholds": thresholds}  # fmt: skip
    (DATA / "logs" / f"fit_fusion__{cnn}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(thresholds, indent=1))


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--cnn", default=BLEND)
    a = ap.parse_args()
    if a.cnn != BLEND:
        main_external(a.cnn)
        return
    from satyapan.video.fusion import FusionModel

    df = load_table("orig")
    train = df[(df.split == "fusion_train") & (df.usable == 1)]
    val_real = df[(df.split == "val") & (df.label == 0) & (df.usable == 1)]
    cnn_meta = json.loads((ROOT / "models" / "video" / "blend_b0.json").read_text())
    report: dict[str, object] = {
        "train_windows": int(len(train)), "train_videos": int(train.key.nunique()),
        "train_real_videos": int(train[train.label == 0].key.nunique()),
        "val_real_windows": int(len(val_real)),
        "cnn_onnx_sha256": cnn_meta["onnx_sha256"], "cv": {},
    }  # fmt: skip
    MODELS.mkdir(parents=True, exist_ok=True)
    for name, feats in SETS.items():
        grid = {c: cv_auc(train, feats, c) for c in C_GRID}
        best = max(grid, key=lambda c: float(np.mean(grid[c])))
        report["cv"][name] = {  # type: ignore[index]
            "best_C": best,
            "cv_auc_mean": round(float(np.mean(grid[best])), 4),
            "cv_auc_sd": round(float(np.std(grid[best], ddof=1)), 4),
            "folds": [round(v, 4) for v in grid[best]],
            "grid": {str(c): round(float(np.mean(v)), 4) for c, v in grid.items()},
        }
        p, lr = fit_lr(train[list(feats)].to_numpy(float), train["label"].to_numpy(), best)
        version = f"fusion-{name}@{cnn_meta['onnx_sha256'][:8]}"
        raw = to_json(feats, p, lr, version)
        (MODELS / f"fusion_{name}.json").write_text(json.dumps(raw, indent=1))
        print(name, report["cv"][name], flush=True)  # type: ignore[index]

    chosen = one_se_choice(report["cv"])  # type: ignore[arg-type]
    report["shipped_set"] = chosen
    print("shipped cue set (1-SE rule):", chosen, flush=True)
    shipped = MODELS / f"fusion_{chosen}.json"
    fusion_path = ROOT / "config" / "video_fusion.json"
    fusion_path.write_text(shipped.read_text())
    model = FusionModel.load(fusion_path)
    # Satya sees call-quality video, so the operating point must hold in every channel
    # condition: fit the 1% / 5% window-FPR thresholds on val reals per condition (orig and
    # the VP8 call simulations, when extracted) and keep the most conservative (highest).
    fusion_sha = hashlib.sha256(fusion_path.read_bytes()).hexdigest()
    version = f"blend_b0:{cnn_meta['onnx_sha256'][:12]}+fusion:{fusion_sha[:12]}"
    thresholds = freeze_thresholds(model, BLEND, version, int(val_real.key.nunique()))
    (ROOT / "config" / "video_thresholds.json").write_text(json.dumps(thresholds, indent=1) + "\n")
    report["thresholds"] = thresholds
    report["fusion_sha256"] = fusion_sha
    out = DATA / "logs" / "fit_fusion.json"
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps(thresholds, indent=1))


if __name__ == "__main__":
    main()
