"""Evaluate D2/D3/D4/D6 on clean / P0 / P1-A / P1-B / P2 and write results/research_main.csv.
TASK T21. Input: score CSVs (conv_id, score) — never raw text. Thresholds come ONLY from
validation (results/thresholds.json written by T19)."""

from __future__ import annotations

from pathlib import Path


def run(scores_dir: Path, thresholds_path: Path, out_csv: Path, n_boot: int = 10_000) -> None:
    """For each (detector, condition): recall@1%FPR and @5%FPR with bootstrap CI, AUROC,
    n_pos, n_neg. Plus paired drop-difference CIs D3 vs D4 and D3 vs D6 (H2).
    Columns: detector,condition,metric,point,low,high,n_pos,n_neg."""
    raise NotImplementedError("T21: see docs/tasks/T21-research-eval-money-figure.md")
