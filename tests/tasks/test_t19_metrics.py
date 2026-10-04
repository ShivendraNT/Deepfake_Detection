"""T19 acceptance: metrics module (recall@FPR, bootstrap), loader, D2 baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.data.icfd import load_jsonl_conversations
from research.metrics import (
    auroc,
    bootstrap_ci,
    fpr_at_threshold,
    paired_bootstrap_diff,
    recall_at_threshold,
    threshold_at_fpr,
)
from tests.helpers import require_artifact

pytestmark = pytest.mark.task("T19")

NEG = [i / 10 for i in range(1, 11)]


def test_threshold_at_fpr() -> None:
    assert threshold_at_fpr(NEG, 0.1) == pytest.approx(1.0)
    assert threshold_at_fpr(NEG, 0.2) == pytest.approx(0.9)
    assert threshold_at_fpr(NEG, 0.0) == float("inf")


def test_recall_and_fpr() -> None:
    y, s = [1, 1, 0, 0], [0.9, 0.4, 0.5, 0.1]
    assert recall_at_threshold(y, s, 0.5) == 0.5
    assert fpr_at_threshold(y, s, 0.5) == 0.5
    with pytest.raises(ValueError):
        recall_at_threshold([0, 0], [0.1, 0.2], 0.5)


def test_auroc() -> None:
    assert auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auroc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert auroc([0, 1], [0.5, 0.5]) == 0.5


def _metric(y, s):  # type: ignore[no-untyped-def]
    return recall_at_threshold(y, s, 0.5)


def test_bootstrap_deterministic_and_brackets_point() -> None:
    y = [1, 0] * 50
    s = [0.6, 0.4, 0.3, 0.2] * 25
    a = bootstrap_ci(_metric, y, s, n_boot=500, seed=3)
    b = bootstrap_ci(_metric, y, s, n_boot=500, seed=3)
    assert a == b and a.low <= a.point <= a.high and a.point == pytest.approx(0.5)


def test_paired_identical_is_zero() -> None:
    y = [1, 0] * 30
    s = [0.7, 0.2] * 30
    ci = paired_bootstrap_diff(_metric, y, s, s, n_boot=300, seed=0)
    assert ci.point == 0 and ci.low == 0 and ci.high == 0


def test_jsonl_loader(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text(
        json.dumps(
            {
                "conv_id": "c1",
                "label": 1,
                "category": "kyc",
                "turns": [{"speaker": "caller", "text": "hello"}],
            }
        )
        + "\n"
    )
    convs = load_jsonl_conversations(p, "test")
    assert convs[0].label == 1 and convs[0].text == "caller: hello"


def test_d2_trains_on_toy_data() -> None:
    pytest.importorskip("sklearn")
    from research.baselines.d2_tfidf import score_d2, train_d2

    texts = ["share otp now", "otp batao", "invoice attached", "meeting at 11"] * 5
    labels = [1, 1, 0, 0] * 5
    m = train_d2(texts, labels)
    s = score_d2(m, ["otp please", "see invoice"])
    assert len(s) == 2 and s[0] > s[1]


def test_clean_results_table_committed() -> None:
    p = require_artifact("results/research_clean.csv", "T19")
    text = p.read_text(encoding="utf-8")
    assert "recall@1%FPR" in text and "D2" in text and "D3" in text and "D4" in text
    assert require_artifact("results/thresholds.json", "T19").exists()
