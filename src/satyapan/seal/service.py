"""The Seal services the API holds in AppState (one passkey store shared by both seals)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from satyapan.contracts.common import utcnow
from satyapan.seal.intent import IntentService
from satyapan.seal.passkey import PasskeyStore, RelyingParty
from satyapan.seal.registry import SealRegistry

MAX_SESSIONS_TO_TRY = 20  # an upload is checked against at most this many recent sessions


@dataclass
class SealServices:
    passkeys: PasskeyStore
    registry: SealRegistry
    intents: IntentService
    clock: Callable[[], datetime] = field(default=utcnow)

    @classmethod
    def build(cls, rp: RelyingParty | None = None) -> SealServices:
        passkeys = PasskeyStore(rp=rp or RelyingParty.from_env())
        return cls(
            passkeys=passkeys,
            registry=SealRegistry(passkeys=passkeys),
            intents=IntentService(passkeys=passkeys),
        )
