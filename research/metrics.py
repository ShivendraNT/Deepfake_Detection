"""Research metrics: recall@FPR, bootstrap CIs, paired bootstrap. TASK T19.

See docs/tasks/T19-research-baselines-metrics.md and docs/RESEARCH_PROTOCOL.md §Metrics.
numpy only (no sklearn needed here). All functions are deterministic given `seed`.
Convention: label 1 = fraud (positive), 0 = normal. Higher score = more likely fraud.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CI:
    point: float
    low: float
    high: float
    n_boot: int


def threshold_at_fpr(neg_scores: Sequence[float], fpr: float) -> float:
    """Smallest threshold t such that the fraction of negatives with score >= t is <= fpr.
    Candidates are the distinct negative scores plus +inf (so fpr=0 -> +inf, recall 0).
    Ties: scores EQUAL to t count as alerts. Fit this on VALIDATION negatives only.
    Example: neg = [0.1, 0.2, ..., 1.0] (10 values), fpr=0.1 -> 1.0."""
    neg = [float(s) for s in neg_scores]
    if not neg or fpr <= 0.0:
        return float("inf")
    n = len(neg)
    candidates = sorted(set(neg))
    for t in candidates:
        count = sum(1 for s in neg if s >= t)
        if count / n <= fpr + 1e-12:
            return float(t)
    return float("inf")


def recall_at_threshold(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> float:
    """Fraction of positives (y=1) with score >= threshold. Raise ValueError if no positives."""
    if len(y_true) != len(scores):
        raise ValueError(f"Length mismatch: {len(y_true)} vs {len(scores)}")
    pos = [s for y, s in zip(y_true, scores, strict=True) if y == 1]
    if not pos:
        raise ValueError("No positive samples in y_true")
    count = sum(1 for s in pos if s >= threshold)
    return float(count / len(pos))


def fpr_at_threshold(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> float:
    """Fraction of negatives (y=0) with score >= threshold. Raise ValueError if no negatives."""
    if len(y_true) != len(scores):
        raise ValueError(f"Length mismatch: {len(y_true)} vs {len(scores)}")
    neg = [s for y, s in zip(y_true, scores, strict=True) if y == 0]
    if not neg:
        raise ValueError("No negative samples in y_true")
    count = sum(1 for s in neg if s >= threshold)
    return float(count / len(neg))


def auroc(y_true: Sequence[int], scores: Sequence[float]) -> float:
    """Mann-Whitney U formulation, ties count 0.5."""
    if len(y_true) != len(scores):
        raise ValueError(f"Length mismatch: {len(y_true)} vs {len(scores)}")
    y_arr = np.asarray(y_true)
    s_arr = np.asarray(scores, dtype=float)
    pos_mask = y_arr == 1
    neg_mask = y_arr == 0
    n_pos = int(np.sum(pos_mask))
    n_neg = int(np.sum(neg_mask))
    if n_pos == 0:
        raise ValueError("No positive samples in y_true")
    if n_neg == 0:
        raise ValueError("No negative samples in y_true")

    _, inv, counts = np.unique(s_arr, return_inverse=True, return_counts=True)
    cum = np.cumsum(counts)
    avg_ranks = cum - (counts - 1) / 2.0
    ranks = avg_ranks[inv]
    u = np.sum(ranks[pos_mask]) - (n_pos * (n_pos + 1)) / 2.0
    return float(u / (n_pos * n_neg))


def bootstrap_ci(
    metric: Callable[[Sequence[int], Sequence[float]], float],
    y_true: Sequence[int],
    scores: Sequence[float],
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
) -> CI:
    """Conversation-level bootstrap: resample indices WITH replacement (numpy default_rng(seed)),
    recompute metric, percentile CI [alpha/2, 1-alpha/2]. Skip resamples with no positives."""
    point = float(metric(y_true, scores))
    y_arr = np.asarray(y_true)
    s_arr = np.asarray(scores, dtype=float)
    n = len(y_arr)
    rng = np.random.default_rng(seed)

    boot_values: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        y_b = y_arr[idx]
        if np.sum(y_b == 1) == 0:
            continue
        try:
            val = float(metric(y_b.tolist(), s_arr[idx].tolist()))
            boot_values.append(val)
        except ValueError:
            continue

    if not boot_values:
        return CI(point=point, low=point, high=point, n_boot=0)

    low = float(np.percentile(boot_values, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(boot_values, 100.0 * (1.0 - alpha / 2.0)))
    return CI(point=point, low=low, high=high, n_boot=len(boot_values))


def paired_bootstrap_diff(
    metric: Callable[[Sequence[int], Sequence[float]], float],
    y_true: Sequence[int],
    scores_a: Sequence[float],
    scores_b: Sequence[float],
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
) -> CI:
    """CI of metric(a) - metric(b) using the SAME resampled indices for a and b."""
    point = float(metric(y_true, scores_a) - metric(y_true, scores_b))
    y_arr = np.asarray(y_true)
    sa_arr = np.asarray(scores_a, dtype=float)
    sb_arr = np.asarray(scores_b, dtype=float)
    n = len(y_arr)
    rng = np.random.default_rng(seed)

    boot_values: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        y_b = y_arr[idx]
        if np.sum(y_b == 1) == 0:
            continue
        try:
            val_a = float(metric(y_b.tolist(), sa_arr[idx].tolist()))
            val_b = float(metric(y_b.tolist(), sb_arr[idx].tolist()))
            boot_values.append(val_a - val_b)
        except ValueError:
            continue

    if not boot_values:
        return CI(point=point, low=point, high=point, n_boot=0)

    low = float(np.percentile(boot_values, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(boot_values, 100.0 * (1.0 - alpha / 2.0)))
    return CI(point=point, low=low, high=high, n_boot=len(boot_values))


def paired_drop_diff(
    metric: Callable[[Sequence[int], Sequence[float]], float],
    y_clean: Sequence[int],
    clean_a: Sequence[float],
    attacked_a: Sequence[float],
    clean_b: Sequence[float],
    attacked_b: Sequence[float],
    n_boot: int = 10_000,
    seed: int = 0,
) -> CI:
    """H2 test: CI of (drop_a - drop_b) where drop = metric(clean) - metric(attacked); the
    attacked set is aligned 1:1 with the clean set (same conversations, same order)."""
    drop_a = float(metric(y_clean, clean_a) - metric(y_clean, attacked_a))
    drop_b = float(metric(y_clean, clean_b) - metric(y_clean, attacked_b))
    point = drop_a - drop_b

    y_arr = np.asarray(y_clean)
    ca_arr = np.asarray(clean_a, dtype=float)
    aa_arr = np.asarray(attacked_a, dtype=float)
    cb_arr = np.asarray(clean_b, dtype=float)
    ab_arr = np.asarray(attacked_b, dtype=float)
    n = len(y_arr)
    rng = np.random.default_rng(seed)

    boot_values: list[float] = []
    alpha = 0.05
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        y_b = y_arr[idx]
        if np.sum(y_b == 1) == 0:
            continue
        try:
            d_a = float(
                metric(y_b.tolist(), ca_arr[idx].tolist())
                - metric(y_b.tolist(), aa_arr[idx].tolist())
            )
            d_b = float(
                metric(y_b.tolist(), cb_arr[idx].tolist())
                - metric(y_b.tolist(), ab_arr[idx].tolist())
            )
            boot_values.append(d_a - d_b)
        except ValueError:
            continue

    if not boot_values:
        return CI(point=point, low=point, high=point, n_boot=0)

    low = float(np.percentile(boot_values, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(boot_values, 100.0 * (1.0 - alpha / 2.0)))
    return CI(point=point, low=low, high=high, n_boot=len(boot_values))
