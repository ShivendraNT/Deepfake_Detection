"""Report pack contract (T16). CONTRACT FILE.

Reports are DRAFTS. `submission` is always "MANUAL_ONLY": nothing is ever auto-filed to
1930, NCRP or a bank. There is no public API for 1930/NCRP; we never pretend there is.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from satyapan.contracts.common import Model, Sha256Hex
from satyapan.contracts.enums import Channel


class TransactionFacts(Model):
    """UTR-first facts. These are what freeze money in the golden hour — not media hashes."""

    utr: str | None
    amount_inr: int
    sent_at: datetime | None
    rail: str
    debit_account_masked: str
    beneficiary_name: str
    beneficiary_account: str | None
    beneficiary_ifsc: str | None
    beneficiary_upi: str | None
    beneficiary_bank: str | None


class EmailDraft(Model):
    to_hint: str  # e.g. "your bank relationship manager / fraud desk"
    subject: str
    body: str


class NcrpField(Model):
    label: str
    value: str


class EvidenceIndexItem(Model):
    evidence_id: str
    filename: str | None
    sha256: Sha256Hex
    captured_at: datetime
    channel: Channel
    submitted_by: str
    analysis_runs: list[str] = Field(default_factory=list)  # "detector@version"


class ReportPack(Model):
    case_id: str
    variant: Literal["ATTEMPTED", "MONEY_SENT"]
    generated_at: datetime
    generated_by: str
    facts: TransactionFacts
    call_script_1930: str | None  # MONEY_SENT only; first line contains the UTR
    bank_email: EmailDraft
    ncrp_draft: list[NcrpField]
    chakshu_note: str | None = None
    evidence_index: list[EvidenceIndexItem]
    custody_head: str | None = None
    sec63_helper: str
    submission: Literal["MANUAL_ONLY"] = "MANUAL_ONLY"
    disclaimer: str = (
        "Draft only. Nothing has been submitted. A human must review and submit "
        "via 1930 / cybercrime.gov.in / your bank."
    )
