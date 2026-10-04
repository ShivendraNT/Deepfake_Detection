"""The money figure: grouped bars, x = {clean, P1-A, P1-B, P2}, bars = D2, D3, D3+aug, D4, D6,
y = recall@1%FPR with 95% CI whiskers; n printed in the caption. TASK T21.
Writes figures/money.png and figures/money.pdf. Matplotlib only, colour-blind-safe palette."""

from __future__ import annotations

from pathlib import Path


def plot(results_csv: Path, out_png: Path) -> None:
    raise NotImplementedError("T21: see docs/tasks/T21-research-eval-money-figure.md")
