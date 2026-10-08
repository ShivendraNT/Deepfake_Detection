"""Passkey (WebAuthn) enrolment and assertion checks for the Satyapan Seal, via py_webauthn.

One passkey per executive serves both seals:
* Voice Seal session start: the passkey signs SHA-256(canonical SEAL-START statement), which
  binds the meeting, the TESLA commitment, t0 and the seal parameters (registry.py).
* Intent Seal: the passkey signs SHA-256(canonical payment intent) (intent.py).

In both cases the WebAuthn "challenge" is not a random server nonce but the hash of the exact
statement being approved ("transaction binding"); replay is stopped by single-use nonces (intent)
or a fresh commitment plus a time window (session start). `require_user_verification=True`:
the authenticator must have checked the user (Touch ID / PIN), not just presence.

No network here: py_webauthn only parses and checks signatures locally. The credential store
is in memory (demo); production keeps it in the case database with the employee directory.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

REGISTRATION_TTL = timedelta(minutes=5)


class PasskeyError(ValueError):
    """A passkey operation was refused. `reason` is a short machine-readable string."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class RelyingParty:
    """Who the passkeys belong to. The browser enforces rp_id; we check the page origin."""

    rp_id: str = "localhost"
    rp_name: str = "Satyapan"
    origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:8000")

    @classmethod
    def from_env(cls) -> RelyingParty:
        origins = os.environ.get("SATYAPAN_WEBAUTHN_ORIGINS", "")
        return cls(
            rp_id=os.environ.get("SATYAPAN_WEBAUTHN_RP_ID", cls.rp_id),
            origins=tuple(o.strip() for o in origins.split(",") if o.strip()) or cls.origins,
        )


@dataclass
class PasskeyCredential:
    employee_id: str
    credential_id: bytes
    public_key: bytes  # COSE-encoded public key (no secret material is ever stored)
    sign_count: int
    registered_at: datetime


def _as_dict(credential: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(credential, str):
        parsed = json.loads(credential)
        if not isinstance(parsed, dict):
            raise PasskeyError("bad_credential", "credential JSON must be an object")
        return parsed
    return credential


@dataclass
class PasskeyStore:
    rp: RelyingParty = field(default_factory=RelyingParty.from_env)
    _creds: dict[str, PasskeyCredential] = field(default_factory=dict)
    _pending: dict[str, tuple[bytes, datetime]] = field(default_factory=dict)

    # ---------------------------------------------------------------- enrolment

    def registration_options(
        self, employee_id: str, display_name: str, now: datetime
    ) -> dict[str, Any]:
        """Options for navigator.credentials.create(). The challenge is random and single-use."""
        challenge = secrets.token_bytes(32)
        self._pending[employee_id] = (challenge, now + REGISTRATION_TTL)
        opts = generate_registration_options(
            rp_id=self.rp.rp_id,
            rp_name=self.rp.rp_name,
            user_name=employee_id,
            user_id=employee_id.encode(),
            user_display_name=display_name,
            challenge=challenge,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        out: dict[str, Any] = json.loads(options_to_json(opts))
        return out

    def register(
        self, employee_id: str, credential: str | dict[str, Any], now: datetime
    ) -> PasskeyCredential:
        pending = self._pending.pop(employee_id, None)
        if pending is None or now > pending[1]:
            raise PasskeyError("no_pending_registration")
        try:
            v = verify_registration_response(
                credential=_as_dict(credential),
                expected_challenge=pending[0],
                expected_rp_id=self.rp.rp_id,
                expected_origin=list(self.rp.origins),
                require_user_verification=True,
            )
        except Exception as exc:  # py_webauthn raises several exception types
            raise PasskeyError("registration_rejected", str(exc)[:160]) from exc
        cred = PasskeyCredential(
            employee_id=employee_id,
            credential_id=v.credential_id,
            public_key=v.credential_public_key,
            sign_count=v.sign_count,
            registered_at=now,
        )
        self._creds[employee_id] = cred
        return cred

    def enrolled(self, employee_id: str) -> bool:
        return employee_id in self._creds

    def credential(self, employee_id: str) -> PasskeyCredential | None:
        return self._creds.get(employee_id)

    # ---------------------------------------------------------------- assertions

    def request_options(self, employee_id: str, challenge: bytes) -> dict[str, Any]:
        """Options for navigator.credentials.get() over a statement-derived challenge."""
        cred = self._creds.get(employee_id)
        if cred is None:
            raise PasskeyError("not_enrolled", employee_id)
        opts = generate_authentication_options(
            rp_id=self.rp.rp_id,
            challenge=challenge,
            allow_credentials=[PublicKeyCredentialDescriptor(id=cred.credential_id)],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        out: dict[str, Any] = json.loads(options_to_json(opts))
        return out

    def verify_assertion(
        self, employee_id: str, assertion: str | dict[str, Any], expected_challenge: bytes
    ) -> int:
        """Check that `employee_id`'s enrolled passkey signed `expected_challenge` on our origin
        with user verification. Returns the new signature counter. Raises PasskeyError."""
        cred = self._creds.get(employee_id)
        if cred is None:
            raise PasskeyError("not_enrolled", employee_id)
        a = _as_dict(assertion)
        try:
            raw_id = base64url_to_bytes(str(a.get("rawId") or a.get("id") or ""))
        except Exception as exc:
            raise PasskeyError("bad_credential", "unreadable credential id") from exc
        if raw_id != cred.credential_id:
            raise PasskeyError("wrong_credential", "assertion is not from the enrolled passkey")
        try:
            v = verify_authentication_response(
                credential=a,
                expected_challenge=expected_challenge,
                expected_rp_id=self.rp.rp_id,
                expected_origin=list(self.rp.origins),
                credential_public_key=cred.public_key,
                credential_current_sign_count=cred.sign_count,
                require_user_verification=True,
            )
        except Exception as exc:
            raise PasskeyError("assertion_rejected", str(exc)[:160]) from exc
        cred.sign_count = v.new_sign_count
        return v.new_sign_count
