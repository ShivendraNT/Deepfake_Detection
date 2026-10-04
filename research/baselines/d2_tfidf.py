"""D2 baseline: TF-IDF char 2-5-grams + logistic regression. TASK T19 (CPU, minutes).
Needs: `uv sync --extra research`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def train_d2(texts: Sequence[str], labels: Sequence[int], seed: int = 0) -> Any:
    """sklearn Pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=4.0, random_state=seed),
    ). Fit and return."""
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


def score_d2(model: Any, texts: Sequence[str]) -> list[float]:
    """predict_proba[:, 1] as a list of floats."""
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")
