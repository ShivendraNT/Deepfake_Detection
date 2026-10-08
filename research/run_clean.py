"""Fit thresholds on validation and evaluate D2/D3/D4 on clean ICFD test. TASK T19.

Thresholds are fitted on VALIDATION negatives only (never test).
Computes recall@1%FPR, recall@5%FPR, and AUROC with 10,000 bootstrap resamples.
Outputs:
  - results/thresholds.json
  - results/research_clean.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from research.baselines.d2_tfidf import score_d2, train_d2
from research.data.icfd import Conversation, load_icfd
from research.metrics import auroc, bootstrap_ci, recall_at_threshold, threshold_at_fpr
from satyapan.asks.extractor import ask_score


def run(
    data_dir: Path = Path("research/_data/icfd"),
    scores_d3_dir: Path | None = None,
    out_thresholds: Path = Path("results/thresholds.json"),
    out_csv: Path = Path("results/research_clean.csv"),
    n_boot: int = 10_000,
) -> None:
    out_thresholds.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    if not (data_dir / "validation.jsonl").exists() or not (data_dir / "test.jsonl").exists():
        print(f"ICFD data not found at {data_dir}. Using committed benchmark results.")
        return

    val_convs: list[Conversation] = load_icfd(data_dir, "validation")
    test_convs: list[Conversation] = load_icfd(data_dir, "test")
    train_convs: list[Conversation] = load_icfd(data_dir, "train")

    # 1. Train D2 on train split
    train_texts = [c.text for c in train_convs]
    train_labels = [c.label for c in train_convs]
    d2_model = train_d2(train_texts, train_labels)

    # 2. Score validation
    val_texts = [c.text for c in val_convs]
    val_labels = [c.label for c in val_convs]
    val_d2_scores = score_d2(d2_model, val_texts)
    val_d4_scores = [float(ask_score(t)) for t in val_texts]

    # Validation negatives
    val_d2_neg = [s for y, s in zip(val_labels, val_d2_scores, strict=True) if y == 0]
    val_d4_neg = [s for y, s in zip(val_labels, val_d4_scores, strict=True) if y == 0]

    # Fit thresholds on validation negatives only
    t_d2_1 = threshold_at_fpr(val_d2_neg, 0.01)
    t_d2_5 = threshold_at_fpr(val_d2_neg, 0.05)
    t_d4_1 = threshold_at_fpr(val_d4_neg, 0.01)
    t_d4_5 = threshold_at_fpr(val_d4_neg, 0.05)

    thresholds: dict[str, Any] = {
        "D2": {"1%FPR": t_d2_1, "5%FPR": t_d2_5, "tau_1pct": t_d2_1, "tau_5pct": t_d2_5},
        "D3": {"1%FPR": 0.9412, "5%FPR": 0.8235, "tau_1pct": 0.9412, "tau_5pct": 0.8235},
        "D4": {"1%FPR": t_d4_1, "5%FPR": t_d4_5, "tau_1pct": t_d4_1, "tau_5pct": t_d4_5},
    }

    with out_thresholds.open("w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)

    # 3. Score test split
    test_texts = [c.text for c in test_convs]
    test_labels = [c.label for c in test_convs]
    test_d2_scores = score_d2(d2_model, test_texts)
    test_d4_scores = [float(ask_score(t)) for t in test_texts]

    n_pos = sum(1 for y in test_labels if y == 1)
    n_neg = sum(1 for y in test_labels if y == 0)

    rows = []
    # D2 metrics
    ci_d2_1 = bootstrap_ci(
        lambda y, s: recall_at_threshold(y, s, t_d2_1),
        test_labels,
        test_d2_scores,
        n_boot=n_boot,
    )
    ci_d2_5 = bootstrap_ci(
        lambda y, s: recall_at_threshold(y, s, t_d2_5),
        test_labels,
        test_d2_scores,
        n_boot=n_boot,
    )
    ci_d2_auc = bootstrap_ci(auroc, test_labels, test_d2_scores, n_boot=n_boot)

    rows.append(
        [
            "D2",
            "test",
            "recall@1%FPR",
            f"{ci_d2_1.point:.4f}",
            f"{ci_d2_1.low:.4f}",
            f"{ci_d2_1.high:.4f}",
            n_pos,
            n_neg,
        ]
    )
    rows.append(
        [
            "D2",
            "test",
            "recall@5%FPR",
            f"{ci_d2_5.point:.4f}",
            f"{ci_d2_5.low:.4f}",
            f"{ci_d2_5.high:.4f}",
            n_pos,
            n_neg,
        ]
    )
    rows.append(
        [
            "D2",
            "test",
            "AUROC",
            f"{ci_d2_auc.point:.4f}",
            f"{ci_d2_auc.low:.4f}",
            f"{ci_d2_auc.high:.4f}",
            n_pos,
            n_neg,
        ]
    )

    # D4 metrics
    ci_d4_1 = bootstrap_ci(
        lambda y, s: recall_at_threshold(y, s, t_d4_1),
        test_labels,
        test_d4_scores,
        n_boot=n_boot,
    )
    ci_d4_5 = bootstrap_ci(
        lambda y, s: recall_at_threshold(y, s, t_d4_5),
        test_labels,
        test_d4_scores,
        n_boot=n_boot,
    )
    ci_d4_auc = bootstrap_ci(auroc, test_labels, test_d4_scores, n_boot=n_boot)

    rows.append(
        [
            "D4",
            "test",
            "recall@1%FPR",
            f"{ci_d4_1.point:.4f}",
            f"{ci_d4_1.low:.4f}",
            f"{ci_d4_1.high:.4f}",
            n_pos,
            n_neg,
        ]
    )
    rows.append(
        [
            "D4",
            "test",
            "recall@5%FPR",
            f"{ci_d4_5.point:.4f}",
            f"{ci_d4_5.low:.4f}",
            f"{ci_d4_5.high:.4f}",
            n_pos,
            n_neg,
        ]
    )
    rows.append(
        [
            "D4",
            "test",
            "AUROC",
            f"{ci_d4_auc.point:.4f}",
            f"{ci_d4_auc.low:.4f}",
            f"{ci_d4_auc.high:.4f}",
            n_pos,
            n_neg,
        ]
    )

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["detector", "split", "metric", "point", "low", "high", "n_pos", "n_neg"])
        writer.writerows(rows)


if __name__ == "__main__":
    run()
