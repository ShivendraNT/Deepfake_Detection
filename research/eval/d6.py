"""D6 = monotone OR of D4 (ask count) and D3 (classifier score). TASK T21.

Mirrors the product policy: an invariant ask OR a strong classifier score raises an alert.
"""

from __future__ import annotations

from collections.abc import Sequence


def d6_alert(d4_counts: Sequence[int], d3_scores: Sequence[float], k: int, t: float) -> list[bool]:
    """alert_i = d4_counts[i] >= k OR d3_scores[i] >= t."""
    raise NotImplementedError("T21: see docs/tasks/T21-research-eval-money-figure.md")


def d6_score(d4_counts: Sequence[int], d3_scores: Sequence[float], k: int, t: float) -> list[float]:
    """A single score so recall@FPR code can be reused: 1.0 + d3 if d4 >= k else d3 scaled so
    that d3 >= t maps above every non-alert. Document the mapping; it must be monotone in both."""
    raise NotImplementedError("T21: see docs/tasks/T21-research-eval-money-figure.md")


def fit_d6(
    val_labels: Sequence[int],
    val_d4: Sequence[int],
    val_d3: Sequence[float],
    target_fpr: float = 0.01,
) -> tuple[int, float]:
    """Grid over k in {1, 2, 3} and t = thresholds from val negatives; pick the (k, t) with the
    highest validation recall whose combined validation FPR <= target_fpr. VALIDATION ONLY."""
    raise NotImplementedError("T21: see docs/tasks/T21-research-eval-money-figure.md")


def residual_exposure(recall: float) -> float:
    """Fraction of attacked frauds that would still reach PASS in the product = 1 - recall."""
    raise NotImplementedError("T21: see docs/tasks/T21-research-eval-money-figure.md")
