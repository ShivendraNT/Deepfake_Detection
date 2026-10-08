"""D2 baseline: TF-IDF char 2-5-grams + logistic regression. TASK T19 (CPU, minutes).
Needs: `uv sync --extra research`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]


def train_d2(texts: Sequence[str], labels: Sequence[int], seed: int = 0) -> Any:
    """sklearn Pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=4.0, random_state=seed),
    ). Fit and return."""
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    C=4.0,
                    random_state=seed,
                ),
            ),
        ]
    )
    pipeline.fit(list(texts), list(labels))
    return pipeline


def score_d2(model: Any, texts: Sequence[str]) -> list[float]:
    """predict_proba[:, 1] as a list of floats."""
    probs = model.predict_proba(list(texts))
    if hasattr(model, "classes_"):
        classes = list(model.classes_)
    elif hasattr(model, "named_steps") and "clf" in model.named_steps:
        classes = list(model.named_steps["clf"].classes_)
    else:
        classes = [0, 1]
    pos_idx = classes.index(1) if 1 in classes else 1
    return [float(p[pos_idx]) for p in probs]
