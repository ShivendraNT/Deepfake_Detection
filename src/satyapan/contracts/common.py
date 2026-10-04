"""Shared field types and the base model. CONTRACT FILE."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
UPI_RE = re.compile(r"^[\w.\-]+@[a-z]+$")
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
ACCOUNT_RE = re.compile(r"^\d{9,18}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

Ifsc = Annotated[str, StringConstraints(pattern=IFSC_RE.pattern)]
UpiId = Annotated[str, StringConstraints(pattern=UPI_RE.pattern)]
Gstin = Annotated[str, StringConstraints(pattern=GSTIN_RE.pattern)]
AccountNumber = Annotated[str, StringConstraints(pattern=ACCOUNT_RE.pattern)]
Sha256Hex = Annotated[str, StringConstraints(pattern=SHA256_RE.pattern)]
CaseId = Annotated[str, StringConstraints(pattern=r"^case_[A-Za-z0-9_\-]+$")]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^ev_[A-Za-z0-9_\-]+$")]
SignalId = Annotated[str, StringConstraints(pattern=r"^sig_[A-Za-z0-9_\-]+$")]
# Whole rupees. Paise are ignored for policy purposes (ADR-006).
AmountInr = Annotated[int, "whole rupees, >= 0"]


class Model(BaseModel):
    """Base for every contract model: unknown fields are rejected, so typos fail loudly."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


def utcnow() -> datetime:
    return datetime.now(UTC)


def mask_account(account_number: str | None) -> str:
    """'99990000004821' -> '••••4821'. Never show full account numbers in UI or prompts."""
    if not account_number:
        return ""
    return "••••" + account_number[-4:]
