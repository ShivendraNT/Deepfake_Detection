"""OOB-Confirm: ask the claimed requester "Did you ask for this payment?". TASK T12.

See docs/tasks/T12-oob-confirm.md. The remote caller cannot refuse or intercept this, because
it goes to the requester's DIRECTORY identity (email + console login), not through the call.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from satyapan.adapters.base import Mailer
from satyapan.contracts.case import Case, OOBChannel, OOBRequest
from satyapan.contracts.enums import CaseKind, OOBResult
from satyapan.contracts.master import Employee
from satyapan.contracts.transaction import PaymentAction


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
    return hashlib.sha256(
        f"{account_number or ''}|{ifsc or ''}|{upi_id or ''}".encode()
    ).hexdigest()


def binding_hash(case_id: str, amount_inr: int, beneficiary_hash_hex: str, nonce: str) -> str:
    """SHA-256 hex of f"{case_id}|{amount_inr}|{beneficiary_hash_hex}|{nonce}"."""
    return hashlib.sha256(
        f"{case_id}|{amount_inr}|{beneficiary_hash_hex}|{nonce}".encode()
    ).hexdigest()


def _inr(amount: int) -> str:
    """Indian digit grouping: 4850000 -> '₹48,50,000'."""
    digits = str(abs(amount))
    if len(digits) > 3:
        last3, rest = digits[-3:], digits[:-3]
        head: list[str] = []
        while len(rest) > 2:
            head.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            head.insert(0, rest)
        digits = ",".join([*head, last3])
    return f"₹{digits}"


def _payee(txn: PaymentAction) -> str:
    """Masked beneficiary: never a full account number in a message or log."""
    if txn.account_number:
        return f"A/c ••••{txn.account_number[-4:]}"
    if txn.upi_id:
        return f"UPI {txn.upi_id}"
    return txn.beneficiary_name


def oob_message(case: Case, requester: Employee, maker_name: str) -> str:
    """'Did you just ask Priya to pay ₹48,50,000 to A/c ••••4821 (FAKB0000482)?'
    Indian digit grouping for the amount. Masked account. For a LIVE_CALL case with no txn:
    'Are you on a call with Priya right now asking for a payment?'"""
    if case.txn is None:
        if case.kind == CaseKind.LIVE_CALL:
            return f"Are you on a call with {maker_name} right now asking for a payment?"
        return f"Did you just ask {maker_name} to make a payment for case {case.id}?"
    txn = case.txn
    where = _payee(txn)
    ifsc = f" ({txn.ifsc})" if txn.ifsc else ""
    return f"Did you just ask {maker_name} to pay {_inr(txn.amount_inr)} to {where}{ifsc}?"


@dataclass
class OOBService:
    """In-memory OOB store. Raw tokens are returned once and never stored (only SHA-256)."""

    mailer: Mailer
    ttl_minutes: int = 10
    _store: dict[str, OOBRequest] = field(default_factory=dict)

    def create(
        self, case: Case, requester: Employee, maker_name: str, now: datetime
    ) -> tuple[OOBRequest, str]:
        """Make nonce + token with secrets.token_urlsafe(32); build OOBRequest (id "oob_<hex>",
        binding_hash, token_sha256, expires_at = now + ttl). Send the email with the console
        link f"/oob/{token}" via self.mailer (if it raises, record channels=["in_app"] only).
        Return (request, raw_token)."""
        nonce = secrets.token_urlsafe(32)
        token = secrets.token_urlsafe(32)
        txn = case.txn
        bh = beneficiary_hash(
            txn.account_number if txn else None,
            txn.ifsc if txn else None,
            txn.upi_id if txn else None,
        )
        req = OOBRequest(
            id=f"oob_{secrets.token_hex(8)}",
            case_id=case.id,
            requester_employee_id=requester.employee_id,
            sent_to_email=requester.email,
            message_text=oob_message(case, requester, maker_name),
            binding_hash=binding_hash(case.id, txn.amount_inr if txn else 0, bh, nonce),
            nonce=nonce,
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now,
            expires_at=now + timedelta(minutes=self.ttl_minutes),
            channels=self._send(requester.email, case.id, token),
        )
        self._store[req.token_sha256] = req
        return req, token

    def _send(self, to: str, case_id: str, token: str) -> list[OOBChannel]:
        """Deliver the message. Any mailer failure must NOT lose the request: stay in-app."""
        subject = f"Confirm this payment request — {case_id}"
        body = (
            "You have a new verification request.\n\n"
            "Open the console to answer (expires in 10 minutes):\n"
            f"/oob/{token}\n\n"
            "Only answer if you really asked for this payment."
        )
        try:
            self.mailer.send(to, subject, body)
        except Exception:  # noqa: BLE001 — SES down / not verified: in-app fallback
            return ["in_app"]
        from satyapan.adapters.ses_mailer import SesMailer  # lazy: boto3 is optional

        return ["in_app", "ses"] if isinstance(self.mailer, SesMailer) else ["in_app"]

    def respond(
        self, token: str, approve: bool, session_employee_id: str, now: datetime
    ) -> OOBRequest:
        """Look up by SHA-256(token). Errors: unknown -> UnknownTokenError; spent ->
        TokenReplayError; now > expires_at -> TokenExpiredError (and result EXPIRED);
        session_employee_id != requester_employee_id -> WrongResponderError (an email link
        alone is not enough: the responder must be logged in as the requester).
        Success: result APPROVED/DENIED, responded_at, responded_by, spent=True."""
        key = hashlib.sha256(token.encode()).hexdigest()
        req = self._store.get(key)
        if req is None:
            raise UnknownTokenError("no OOB request for this token")
        if req.spent:
            raise TokenReplayError("this confirmation link was already used")
        if now > req.expires_at:
            req.result = OOBResult.EXPIRED
            raise TokenExpiredError("this confirmation link has expired")
        if session_employee_id != req.requester_employee_id:
            raise WrongResponderError("only the requested person may answer")
        req.result = OOBResult.APPROVED if approve else OOBResult.DENIED
        req.responded_at = now
        req.responded_by = session_employee_id
        req.spent = True
        return req
