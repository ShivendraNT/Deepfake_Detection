"""Parsed-artifact models shared between detectors (email T03/T04, document T08). CONTRACT FILE."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from satyapan.contracts.common import Model, Sha256Hex

AuthVerdict = Literal[
    "pass", "fail", "none", "softfail", "neutral", "temperror", "permerror", "policy", "unknown"
]


class AuthResults(Model):
    """Values from the TRUSTED Authentication-Results header only (added by our own MTA)."""

    authserv_id: str | None = None
    spf: AuthVerdict = "unknown"
    dkim: AuthVerdict = "unknown"
    dmarc: AuthVerdict = "unknown"
    trusted: bool = False  # False if no header from our own authserv-id was found
    untrusted_headers_seen: int = 0  # Authentication-Results added by others (ignored)


class AttachmentMeta(Model):
    filename: str | None
    media_type: str
    size_bytes: int
    sha256: Sha256Hex


class ParsedEmail(Model):
    message_id: str | None = None
    subject: str = ""
    from_addr: str
    from_display_name: str = ""
    from_domain: str
    reply_to_domain: str | None = None
    return_path_domain: str | None = None
    to: list[str] = Field(default_factory=list)
    date: datetime | None = None
    auth: AuthResults
    body_text: str = ""  # plain text; HTML converted to text, comments/hidden text removed
    attachments: list[AttachmentMeta] = Field(default_factory=list)


class InvoiceFields(Model):
    """Fields extracted by regex from invoice text (T08). Lists because invoices can repeat."""

    ifsc_codes: list[str] = Field(default_factory=list)
    account_numbers: list[str] = Field(default_factory=list)
    upi_ids: list[str] = Field(default_factory=list)
    gstins: list[str] = Field(default_factory=list)
    amounts_inr: list[int] = Field(default_factory=list)
    invoice_number: str | None = None


class PdfMeta(Model):
    eof_count: int = Field(ge=0)
    incremental_updates: int = Field(ge=0)  # eof_count - 1, never negative
    producer: str | None = None
    creator: str | None = None
    creation_date: datetime | None = None
    mod_date: datetime | None = None
