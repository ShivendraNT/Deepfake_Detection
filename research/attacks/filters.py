"""Meaning-preservation filters + agreement stats. TASK T20."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

LABSE_MIN_COSINE = 0.80


@dataclass(frozen=True)
class FilterDecision:
    keep: bool
    cosine: float
    judge_ok: bool | None
    reason: str


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity; raise ValueError on zero vectors or length mismatch."""
    raise NotImplementedError("T20: see docs/tasks/T20-research-paraphrase-attacks.md")


def filter_pair(
    emb_original: Sequence[float], emb_rewrite: Sequence[float], judge_ok: bool | None
) -> FilterDecision:
    """keep only if cosine >= LABSE_MIN_COSINE AND judge_ok is True.
    reason in {"ok", "low_cosine", "judge_rejected", "judge_missing"}."""
    raise NotImplementedError("T20: see docs/tasks/T20-research-paraphrase-attacks.md")


def cohen_kappa(labels_a: Sequence[int], labels_b: Sequence[int]) -> float:
    """Cohen's kappa for two annotators (binary or multi-class). 1.0 = perfect agreement."""
    raise NotImplementedError("T20: see docs/tasks/T20-research-paraphrase-attacks.md")


def discard_rate(decisions: Sequence[FilterDecision]) -> float:
    raise NotImplementedError("T20: see docs/tasks/T20-research-paraphrase-attacks.md")
