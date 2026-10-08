"""Intent Seal: the requester's passkey signs the exact payment ("what you approve is what gets
paid").

The canonical intent (case id, requester, action, amount in whole rupees, SHA-256 of the full
beneficiary account, masked account, IFSC, a single-use nonce, expiry) is serialised as sorted,
compact JSON; its SHA-256 is the WebAuthn challenge. Any change after approval (amount,
beneficiary, case, requester) changes the challenge, so the signature no longer verifies.
The nonce is spent on first success (replay), and the origin and RP id are checked by
py_webauthn (phishing page). This upgrades OOB-Confirm from "a click" to a signature over the
payment; it does NOT replace the HOLD clearance rules (policy unchanged: OOB alone cannot clear a
HOLD).

Known limit (docs/SEAL.md): a WebAuthn prompt does not display transaction text. Malware in the
approver's browser could show Rs 48,500 while asking the passkey to sign Rs 48,50,000. The fix
in production is Secure Payment Confirmation style browser UI or a second device.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from satyapan.contracts.common import mask_account
from satyapan.contracts.seal import IntentBeneficiary, PaymentIntent
from satyapan.seal.passkey import PasskeyError, PasskeyStore
from satyapan.seal.registry import canonical_json

INTENT_TTL = timedelta(minutes=10)


class IntentError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def account_sha256(account_number: str) -> str:
    return hashlib.sha256(account_number.strip().encode()).hexdigest()


def make_intent(
    *,
    case_id: str,
    requester: str,
    amount_inr: int,
    account_number: str,
    ifsc: str | None,
    now: datetime,
    action: str = "PAY_NEW_BENEFICIARY",
    ttl: timedelta = INTENT_TTL,
    nonce: str | None = None,
) -> PaymentIntent:
    return PaymentIntent(
        case_id=case_id,
        requester=requester,
        action=action,
        amount_inr=amount_inr,
        beneficiary=IntentBeneficiary(
            account_sha256=account_sha256(account_number),
            account_masked=mask_account(account_number),
            ifsc=ifsc,
        ),
        nonce=nonce or secrets.token_urlsafe(18),
        expires_at=int((now + ttl).timestamp()),
    )


def canonical_intent(intent: PaymentIntent) -> bytes:
    return canonical_json(intent.model_dump(mode="json"))


def intent_challenge(intent: PaymentIntent) -> bytes:
    """The WebAuthn challenge: SHA-256 of the canonical intent JSON."""
    return hashlib.sha256(canonical_intent(intent)).digest()


def format_inr(amount: int) -> str:
    """Indian digit grouping: 4850000 -> '₹48,50,000'."""
    s = str(abs(amount))
    head, tail = s[:-3], s[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join([*groups, tail]) if groups else "₹" + tail


def display_text(intent: PaymentIntent) -> str:
    b = intent.beneficiary
    ifsc = f" ({b.ifsc})" if b.ifsc else ""
    return (
        f"Approve {format_inr(intent.amount_inr)} to A/c {b.account_masked}{ifsc} "
        f"for {intent.case_id}?"
    )


def matches_payment(intent: PaymentIntent, amount_inr: int, account_number: str) -> bool:
    """Execution-time check: is the payment about to be sent the one that was signed?"""
    return intent.amount_inr == amount_inr and intent.beneficiary.account_sha256 == (
        account_sha256(account_number)
    )


@dataclass(frozen=True)
class VerifiedIntent:
    intent: PaymentIntent
    sign_count: int
    verified_at: datetime


@dataclass
class IntentService:
    passkeys: PasskeyStore
    _issued: dict[str, PaymentIntent] = field(default_factory=dict)
    _spent: set[str] = field(default_factory=set)

    def issue(self, intent: PaymentIntent) -> dict[str, Any]:
        """Remember the intent and return what the approval page needs."""
        if intent.nonce in self._issued or intent.nonce in self._spent:
            raise IntentError("nonce_reused")
        challenge = intent_challenge(intent)
        options = self.passkeys.request_options(intent.requester, challenge)
        self._issued[intent.nonce] = intent
        return {
            "intent": intent.model_dump(mode="json"),
            "display_text": display_text(intent),
            "challenge_sha256_hex": challenge.hex(),
            "request_options": options,
        }

    def verify(
        self, presented: PaymentIntent, assertion: str | dict[str, Any], now: datetime
    ) -> VerifiedIntent:
        """Verify an approval of `presented` (the payment as it will be executed).

        Order of checks: nonce spent (replay) -> nonce known -> expiry -> requester -> passkey
        signature over SHA-256(presented) -> presented equals the issued intent.
        """
        if presented.nonce in self._spent:
            raise IntentError("replay", "nonce already spent")
        issued = self._issued.get(presented.nonce)
        if issued is None:
            raise IntentError("unknown_nonce")
        if now.timestamp() > issued.expires_at:
            raise IntentError("expired")
        if presented.requester != issued.requester:
            raise IntentError("wrong_requester")
        try:
            count = self.passkeys.verify_assertion(
                presented.requester, assertion, intent_challenge(presented)
            )
        except PasskeyError as e:
            raise IntentError("signature_rejected", e.detail or e.reason) from e
        if canonical_intent(presented) != canonical_intent(issued):
            raise IntentError("intent_mismatch", "signed intent differs from the issued one")
        self._spent.add(presented.nonce)
        del self._issued[presented.nonce]
        return VerifiedIntent(intent=presented, sign_count=count, verified_at=now)
