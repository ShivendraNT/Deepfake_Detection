"""Technique registry: every forensic method is a `Technique` with a run(ctx) function.

A technique never raises to the engine: a parse failure returns Status.ERROR, a missing model
Status.UNAVAILABLE, a file it does not apply to Status.SKIPPED. Only Status.OK results count
towards "nothing found"; the verdict lists everything else as not checked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from satyapan.forensics.context import AnalysisContext
from satyapan.forensics.models import (
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Region,
    Status,
    Strength,
    TechniqueResult,
    TimeSpan,
)


class Unavailable(Exception):
    """A model or optional dependency is not installed on this workstation."""


class NotApplicable(Exception):
    """The technique does not apply to this file (reason in the message)."""


@dataclass(frozen=True)
class Technique:
    id: str
    name: str
    category: Category
    kinds: tuple[MediaKind, ...]
    run: Callable[[AnalysisContext], TechniqueResult]
    method: str
    reference: str | None = None
    limitations: str | None = None
    weight_note: str = ""
    order: int = 50
    roles: tuple[str, ...] = field(default=("questioned", "reference"))


def make_result(
    t: Technique,
    *,
    summary: str,
    findings: list[Finding] | None = None,
    data: dict[str, object] | None = None,
    artifacts: list[object] | None = None,
    status: Status = Status.OK,
) -> TechniqueResult:
    return TechniqueResult(
        id=t.id,
        name=t.name,
        category=t.category,
        status=status,
        summary=summary,
        method=t.method,
        reference=t.reference,
        limitations=t.limitations,
        findings=findings or [],
        data=data or {},
        artifacts=list(artifacts or []),  # type: ignore[arg-type]
    )


def finding(
    code: str,
    title: str,
    detail: str,
    hypothesis: Hypothesis,
    strength: Strength,
    category: Category,
    *,
    score: float | None = None,
    regions: list[Region] | None = None,
    spans: list[TimeSpan] | None = None,
    artifacts: list[str] | None = None,
    **observations: object,
) -> Finding:
    return Finding(
        code=code,
        title=title,
        detail=detail,
        hypothesis=hypothesis,
        strength=strength,
        category=category,
        score=score,
        regions=regions or [],
        spans=spans or [],
        artifacts=artifacts or [],
        observations=dict(observations),
    )


def info(code: str, title: str, detail: str, category: Category, **obs: object) -> Finding:
    return finding(code, title, detail, Hypothesis.NEUTRAL, Strength.NONE, category, **obs)
