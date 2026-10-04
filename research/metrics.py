"""Research metrics: recall@FPR, bootstrap CIs, paired bootstrap. TASK T19.

See docs/tasks/T19-research-baselines-metrics.md and docs/RESEARCH_PROTOCOL.md §Metrics.
numpy only (no sklearn needed here). All functions are deterministic given `seed`.
Convention: label 1 = fraud (positive), 0 = normal. Higher score = more likely fraud.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


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
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


def recall_at_threshold(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> float:
    """Fraction of positives (y=1) with score >= threshold. Raise ValueError if no positives."""
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


def fpr_at_threshold(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> float:
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


def auroc(y_true: Sequence[int], scores: Sequence[float]) -> float:
    """Mann-Whitney U formulation, ties count 0.5."""
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


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
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


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
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


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
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")
