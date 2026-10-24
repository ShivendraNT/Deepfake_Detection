"""Explanation + LLM I/O contracts (T14, T15). CONTRACT FILE.

The LLM only ever sees `EvidenceItemForLLM` objects (structured, excerpts <= 300 chars).
It never sees raw HTML, hidden PDF layers, tools, or case state it could write to.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from satyapan.contracts.common import Model
from satyapan.contracts.enums import Band, Lang, ReasonCode
from satyapan.contracts.evidence import EXCERPT_MAX_CHARS


class EvidenceItemForLLM(Model):
    id: str = Field(pattern=r"^ev_[A-Za-z0-9_\-]+$")  # cited as [ev_...]
    type: str  # e.g. "reason_code", "transaction_field", "email_excerpt"
    value: str = Field(max_length=EXCERPT_MAX_CHARS)
    source: Literal["trusted", "untrusted"]


class LLMRequest(Model):
    system: str  # constant text; NEVER contains untrusted content
    user_json: str  # JSON of {"lang":..., "band":..., "evidence":[EvidenceItemForLLM,...]}
    max_tokens: int = 400


class FaithfulnessResult(Model):
    ok: bool
    failures: list[str] = Field(default_factory=list)


class Explanation(Model):
    lang: Lang
    band: Band
    text: str
    source: Literal["template", "llm"]
    reason_codes: list[ReasonCode]
    faithfulness: FaithfulnessResult | None = None


class CitizenResult(Model):
    """Coarse output for the citizen page (T24): band + action only, never scores."""

    band: Band
    action_text: str
    rule_hits: list[str] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)  # {"call_1930": "tel:1930", ...}


class CitizenFileResult(CitizenResult):
    """Citizen check of any message or file (finale): band + action + plain reasons; never
    scores. `checked` / `not_checked` say what this device could and could not look at."""

    why: list[str] = Field(default_factory=list)
    checked: list[str] = Field(default_factory=list)
    not_checked: list[str] = Field(default_factory=list)
    heard_or_read: str | None = None  # what the voice note said / the screenshot read
    seconds: float = 0.0
