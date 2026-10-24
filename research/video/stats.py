"""Metrics with identity-cluster bootstrap CIs (videos of the same person / source pair are
resampled together, so near-duplicate clips cannot shrink the interval)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np  # provenance: seeded-resampling-ok

from research.heldout.stats import wilson
from research.metrics import auroc, threshold_at_fpr

N_BOOT = 2000


def eer(y: Sequence[int], s: Sequence[float]) -> float:
    y_arr, s_arr = np.asarray(y), np.asarray(s, float)
    best = 1.0
    for t in np.unique(s_arr):
        fpr = float(np.mean(s_arr[y_arr == 0] >= t))
        fnr = float(np.mean(s_arr[y_arr == 1] < t))
        best = min(best, max(fpr, fnr))
    return best


def tpr_at(y: Sequence[int], s: Sequence[float], t: float) -> float:
    y_arr, s_arr = np.asarray(y), np.asarray(s, float)
    return float(np.mean(s_arr[y_arr == 1] >= t))


def fpr_at(y: Sequence[int], s: Sequence[float], t: float) -> float:
    y_arr, s_arr = np.asarray(y), np.asarray(s, float)
    return float(np.mean(s_arr[y_arr == 0] >= t))


def cluster_ci(
    metric: Callable[[np.ndarray, np.ndarray], float],
    y: Sequence[int],
    s: Sequence[float],
    groups: Sequence[str],
    seed: int = 0,
    n_boot: int = N_BOOT,
) -> dict[str, float]:
    y_arr, s_arr, g_arr = np.asarray(y), np.asarray(s, float), np.asarray(groups)
    point = float(metric(y_arr, s_arr))
    uniq = np.unique(g_arr)
    members = {g: np.flatnonzero(g_arr == g) for g in uniq}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([members[g] for g in pick])
        yb = y_arr[idx]
        if yb.min() == yb.max():
            continue
        vals.append(float(metric(yb, s_arr[idx])))
    lo, hi = np.percentile(vals, [2.5, 97.5]) if vals else (point, point)
    return {
        "value": round(point, 4),
        "low": round(float(lo), 4),
        "high": round(float(hi), 4),
        "n_boot": len(vals),
    }


def cluster_paired_diff(
    metric: Callable[[np.ndarray, np.ndarray], float],
    y: Sequence[int],
    s_a: Sequence[float],
    s_b: Sequence[float],
    groups: Sequence[str],
    seed: int = 0,
    n_boot: int = N_BOOT,
) -> dict[str, float]:
    """metric(a) - metric(b) on the same videos, identity clusters resampled together."""
    y_arr = np.asarray(y)
    a_arr, b_arr, g_arr = np.asarray(s_a, float), np.asarray(s_b, float), np.asarray(groups)
    point = float(metric(y_arr, a_arr) - metric(y_arr, b_arr))
    uniq = np.unique(g_arr)
    members = {g: np.flatnonzero(g_arr == g) for g in uniq}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = np.concatenate([members[g] for g in rng.choice(uniq, size=len(uniq))])
        yb = y_arr[idx]
        if yb.min() == yb.max():
            continue
        vals.append(float(metric(yb, a_arr[idx]) - metric(yb, b_arr[idx])))
    lo, hi = np.percentile(vals, [2.5, 97.5]) if vals else (point, point)
    return {
        "value": round(point, 4),
        "low": round(float(lo), 4),
        "high": round(float(hi), 4),
        "se": round(float(np.std(vals, ddof=1)), 4) if len(vals) > 1 else 0.0,
        "n_boot": len(vals),
    }


def summarize(
    y: Sequence[int],
    s: Sequence[float],
    groups: Sequence[str],
    tau_hi: float | None = None,
    tau_lo: float | None = None,
) -> dict[str, object]:
    y_arr, s_arr = np.asarray(y), np.asarray(s, float)
    out: dict[str, object] = {
        "n_real": int((y_arr == 0).sum()),
        "n_fake": int((y_arr == 1).sum()),
        "auc": cluster_ci(lambda a, b: auroc(a.tolist(), b.tolist()), y, s, groups),
        "eer": cluster_ci(eer, y, s, groups),
    }
    for name, t in (("hi", tau_hi), ("lo", tau_lo)):
        if t is None:
            continue
        k_tp = int((s_arr[y_arr == 1] >= t).sum())
        k_fp = int((s_arr[y_arr == 0] >= t).sum())
        out[f"tpr_at_tau_{name}"] = wilson(k_tp, int((y_arr == 1).sum()))
        out[f"fpr_at_tau_{name}"] = wilson(k_fp, int((y_arr == 0).sum()))
    return out


__all__ = [
    "auroc",
    "cluster_ci",
    "eer",
    "fpr_at",
    "summarize",
    "threshold_at_fpr",
    "tpr_at",
    "wilson",
]
