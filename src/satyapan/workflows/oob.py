"""OOB-Confirm: ask the claimed requester "Did you ask for this payment?". TASK T12.

See docs/tasks/T12-oob-confirm.md. The remote caller cannot refuse or intercept this, because
it goes to the requester's DIRECTORY identity (email + console login), not through the call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from satyapan.adapters.base import Mailer
from satyapan.contracts.case import Case, OOBRequest
from satyapan.contracts.master import Employee


class OOBError(Exception):
    """Base class. Subclasses below are what the API maps to HTTP 4xx."""


class TokenReplayError(OOBError):
    pass


class TokenExpiredError(OOBError):
    pass


class WrongResponderError(OOBError):
    pass


class UnknownTokenError(OOBError):
    pass


def beneficiary_hash(account_number: str | None, ifsc: str | None, upi_id: str | None) -> str:
    """SHA-256 hex of f"{account_number or ''}|{ifsc or ''}|{upi_id or ''}"."""
    raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")


def binding_hash(case_id: str, amount_inr: int, beneficiary_hash_hex: str, nonce: str) -> str:
    """SHA-256 hex of f"{case_id}|{amount_inr}|{beneficiary_hash_hex}|{nonce}"."""
    raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")


def oob_message(case: Case, requester: Employee, maker_name: str) -> str:
    """'Did you just ask Priya to pay ₹48,50,000 to A/c ••••4821 (FAKB0000482)?'
    Indian digit grouping for the amount. Masked account. For a LIVE_CALL case with no txn:
    'Are you on a call with Priya right now asking for a payment?'"""
    raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")


@dataclass
class OOBService:
    """In-memory OOB store. Raw tokens are returned once and never stored (only SHA-256)."""

    mailer: Mailer
    ttl_minutes: int = 10

    def create(
        self, case: Case, requester: Employee, maker_name: str, now: datetime
    ) -> tuple[OOBRequest, str]:
        """Make nonce + token with secrets.token_urlsafe(32); build OOBRequest (id "oob_<hex>",
        binding_hash, token_sha256, expires_at = now + ttl). Send the email with the console
        link f"/oob/{token}" via self.mailer (if it raises, record channels=["in_app"] only).
        Return (request, raw_token)."""
        raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")

    def respond(
        self, token: str, approve: bool, session_employee_id: str, now: datetime
    ) -> OOBRequest:
        """Look up by SHA-256(token). Errors: unknown -> UnknownTokenError; spent ->
        TokenReplayError; now > expires_at -> TokenExpiredError (and result EXPIRED);
        session_employee_id != requester_employee_id -> WrongResponderError (an email link
        alone is not enough: the responder must be logged in as the requester).
        Success: result APPROVED/DENIED, responded_at, responded_by, spent=True."""
        raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")
