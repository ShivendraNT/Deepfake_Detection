"""Evidence, signals and the detector output contract. CONTRACT FILE.

Every detector (email, document, asks, voice) returns a `DetectorOutput`.
Every finding inside it is a `Signal` built with `Signal.make(...)`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from satyapan.contracts.common import EvidenceId, Model, Sha256Hex, utcnow
from satyapan.contracts.enums import (
    AskType,
    Channel,
    GreyReason,
    ReasonCode,
    SignalGroup,
    SignalSource,
    Strength,
    TargetRule,
)
from satyapan.contracts.signal_table import DECISION_ONLY_CODES, SIGNAL_TABLE

EXCERPT_MAX_CHARS = 300

DetailValue = str | int | float | bool | None


class AnalysisRun(Model):
    detector: str
    version: str
    at: datetime = Field(default_factory=utcnow)


class Evidence(Model):
    """One piece of attacker-controllable input, hashed at intake BEFORE any parsing."""

    id: EvidenceId
    case_id: str
    channel: Channel
    filename: str | None = None
    media_type: str = "application/octet-stream"
    sha256: Sha256Hex
    size_bytes: int = Field(ge=0)
    captured_at: datetime
    submitted_by: str
    storage_uri: str  # "file://vault_data/..." or "s3://bucket/key"
    excerpt: str | None = Field(default=None, max_length=EXCERPT_MAX_CHARS)
    analysis_runs: list[AnalysisRun] = Field(default_factory=list)


class AskSpan(Model):
    """One detected 'ask' (A1-A7) in a text. Produced by satyapan.asks.extractor (T05)."""

    ask_type: AskType
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    lexicon_id: str  # which lexicon entry matched, e.g. "A2.en.otp"
    script: str = "latin"  # "latin" or "devanagari"


class Signal(Model):
    """A single finding. group/target/strength MUST match SIGNAL_TABLE (validated).

    Build it with Signal.make(code, source=..., evidence_ids=[...]) so you never type
    group/target/strength by hand.
    """

    id: str = Field(pattern=r"^sig_[A-Za-z0-9_\-]+$")
    code: ReasonCode
    group: SignalGroup
    target: TargetRule
    strength: Strength
    source: SignalSource
    evidence_ids: list[str] = Field(default_factory=list)
    detector: str = "unknown"
    # Raw score: shown ONLY to checker/security roles (oracle-abuse mitigation, §5.10).
    score: float | None = None
    detail: dict[str, DetailValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _matches_table(self) -> Signal:
        if self.code in DECISION_ONLY_CODES:
            raise ValueError(f"{self.code} is decision-only; detectors may not emit it")
        spec = SIGNAL_TABLE.get(self.code)
        if spec is None:
            raise ValueError(f"{self.code} has no entry in SIGNAL_TABLE")
        if (self.group, self.target, self.strength) != (spec.group, spec.target, spec.strength):
            raise ValueError(
                f"{self.code}: group/target/strength must be "
                f"{spec.group}/{spec.target}/{spec.strength} (use Signal.make)"
            )
        if self.source not in spec.allowed_sources:
            raise ValueError(f"{self.code} may not come from source={self.source}")
        return self

    @classmethod
    def make(
        cls,
        code: ReasonCode,
        *,
        source: SignalSource,
        evidence_ids: list[str] | None = None,
        detector: str = "unknown",
        score: float | None = None,
        detail: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> Signal:
        spec = SIGNAL_TABLE[code]
        return cls(
            id=id or f"sig_{uuid.uuid4().hex[:12]}",
            code=code,
            group=spec.group,
            target=spec.target,
            strength=spec.strength,
            source=source,
            evidence_ids=list(evidence_ids or []),
            detector=detector,
            score=score,
            detail=dict(detail or {}),
        )


class DetectorOutput(Model):
    """What every detector returns. `artifacts` holds parsed fields for the UI/report."""

    detector: str
    version: str
    evidence_id: EvidenceId | None = None
    signals: list[Signal] = Field(default_factory=list)
    grey_reasons: list[GreyReason] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None
