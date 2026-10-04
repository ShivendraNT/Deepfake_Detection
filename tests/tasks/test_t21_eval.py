"""T21 acceptance: D6 monotone OR, residual exposure, money figure."""

from __future__ import annotations

import pytest

from research.eval.d6 import d6_alert, d6_score, fit_d6, residual_exposure
from tests.helpers import require_artifact

pytestmark = pytest.mark.task("T21")


def test_d6_alert() -> None:
    assert d6_alert([0, 1, 2], [0.1, 0.9, 0.1], k=2, t=0.8) == [False, True, True]


def test_d6_score_is_monotone_or() -> None:
    d4, d3 = [0, 2, 0, 1], [0.95, 0.1, 0.2, 0.5]
    s = d6_score(d4, d3, k=2, t=0.9)
    alerts = d6_alert(d4, d3, k=2, t=0.9)
    lowest_alert = min(x for x, a in zip(s, alerts, strict=True) if a)
    assert all(x < lowest_alert for x, a in zip(s, alerts, strict=True) if not a)


def test_fit_d6_respects_fpr() -> None:
    labels = [0] * 100 + [1] * 20
    d4 = [0] * 99 + [1] + [1] * 15 + [0] * 5
    d3 = [i / 100 for i in range(100)] + [0.99] * 20
    k, t = fit_d6(labels, d4, d3, target_fpr=0.02)
    alerts = d6_alert(d4, d3, k, t)
    fp = sum(a for a, y in zip(alerts, labels, strict=True) if y == 0)
    assert fp / 100 <= 0.02


def test_residual_exposure() -> None:
    assert residual_exposure(0.8) == pytest.approx(0.2)


def test_money_figure_committed() -> None:
    require_artifact("figures/money.png", "T21")
    text = require_artifact("results/research_main.csv", "T21").read_text(encoding="utf-8")
    assert "P1" in text and "D6" in text and "low" in text
