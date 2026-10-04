"""Custody log rows and anchors (vault, C1). CONTRACT FILE."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from satyapan.contracts.common import Model, Sha256Hex
from satyapan.contracts.enums import CustodyEvent

GENESIS_HASH = "0" * 64


class CustodyRow(Model):
    """row_hash = SHA-256(prev_hash ‖ canonical_json(row without row_hash))."""

    seq: int = Field(ge=1)
    case_id: str
    evidence_id: str | None = None
    event: CustodyEvent
    actor: str
    at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: Sha256Hex
    row_hash: Sha256Hex


class ChainVerification(Model):
    ok: bool
    rows_checked: int
    broken_at_seq: int | None = None
    reason: str | None = None


class AnchorRecord(Model):
    """Chain head written to S3 Object Lock (or the local fallback folder)."""

    head_hash: Sha256Hex
    seq: int
    at: datetime
    uri: str  # s3://bucket/anchors/... or file://...
    object_lock_mode: str | None = None  # "GOVERNANCE" in the hackathon, "COMPLIANCE" in prod
