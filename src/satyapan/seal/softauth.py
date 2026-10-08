"""DEMO / TEST ONLY: a software P-256 passkey that speaks the exact WebAuthn wire format.

It stands in for Touch ID in unit tests, the CLI (`scripts/seal_cli.py`) and offline demos.
The SERVER never uses it: the registry and the Intent Seal verify whatever the browser sends with
py_webauthn (passkey.py), exactly as they would verify a real platform authenticator. A software
key has no user-verification hardware behind it, so it must never be enrolled in production.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _client_data(kind: str, challenge: bytes, origin: str) -> bytes:
    return json.dumps(
        {"type": kind, "challenge": b64u(challenge), "origin": origin, "crossOrigin": False},
        separators=(",", ":"),
    ).encode()


class SoftAuthenticator:
    """Minimal platform authenticator: ES256, attestation 'none', UP+UV flags set."""

    def __init__(self, rp_id: str = "localhost", origin: str = "http://localhost:5173") -> None:
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = os.urandom(16)
        self.count = 0
        self.user_handle = b""

    def _cose_public_key(self) -> bytes:
        n = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")}
        )

    def create(self, options: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        """navigator.credentials.create() given the JSON options from the server."""
        challenge = b64u_decode(options["challenge"])
        self.user_handle = b64u_decode(options["user"]["id"])
        cdj = _client_data("webauthn.create", challenge, origin or self.origin)
        attested = (
            bytes(16) + len(self.cred_id).to_bytes(2, "big") + self.cred_id
        ) + self._cose_public_key()
        auth_data = (
            hashlib.sha256(self.rp_id.encode()).digest()
            + bytes([0x45])  # UP | UV | AT
            + self.count.to_bytes(4, "big")
            + attested
        )
        att = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64u(self.cred_id),
            "rawId": b64u(self.cred_id),
            "type": "public-key",
            "response": {"clientDataJSON": b64u(cdj), "attestationObject": b64u(att)},
        }

    def get(self, challenge: bytes, origin: str | None = None) -> dict[str, Any]:
        """navigator.credentials.get() over a raw challenge (bytes)."""
        self.count += 1
        cdj = _client_data("webauthn.get", challenge, origin or self.origin)
        auth_data = (
            hashlib.sha256(self.rp_id.encode()).digest()
            + bytes([0x05])  # UP | UV
            + self.count.to_bytes(4, "big")
        )
        sig = self.key.sign(auth_data + hashlib.sha256(cdj).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64u(self.cred_id),
            "rawId": b64u(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(cdj),
                "authenticatorData": b64u(auth_data),
                "signature": b64u(sig),
                "userHandle": b64u(self.user_handle),
            },
        }
