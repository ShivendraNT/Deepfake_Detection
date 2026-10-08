"""Seal Registry (component C14): passkey-started seal sessions and TESLA key disclosure.

In-memory (demo). It stores only public values: who started a session, for which meeting/note,
the hash-chain commitment, timing, and keys whose epoch has already ended. It never sees audio.

Session start (one Touch ID per meeting or voice note)
    The executive's client builds the canonical SEAL-START statement (employee, meeting, TESLA
    commitment, t0, epoch length, chain length, seal parameters) and signs SHA-256(statement)
    with the passkey. The registry rebuilds the same statement from the request fields and
    verifies the assertion (passkey.py). A commitment can start only one session, and t0 must
    be close to the server clock, so an old assertion cannot be replayed.

Key disclosure (every 5 s)
    After epoch e has ended (server clock) the client posts K_e. The registry checks
    H(K_e) = K_{e-1} (or hashes up to the commitment) and then knows K_0..K_e.

Who may read keys
    Meeting sessions: any receiver of that meeting may fetch disclosed keys (live verification
    happens on the receiver's laptop). Voice-note sessions: keys stay on the server and are only
    used by POST /seal/verify-upload, so a leaked key cannot be used to seal a fake note.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from satyapan.contracts.enums import SealSessionKind
from satyapan.contracts.seal import SealKey, SealMeetingView, SealSession
from satyapan.seal import tesla
from satyapan.seal.passkey import PasskeyError, PasskeyStore
from satyapan.seal.voiceseal import SealParams

MAX_START_SKEW = timedelta(seconds=120)  # |t0 - server clock| at session start
MAX_EPOCHS = 4 * 720  # 4 hours of 5 s epochs per session


class RegistryError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no spaces, UTF-8. Only ints and strings inside (no float formatting traps
    between Python and JavaScript)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def seal_start_statement(
    *,
    employee_id: str,
    kind: SealSessionKind,
    binding: str,
    commitment_hex: str,
    t0_ms: int,
    epoch_ms: int,
    n_epochs: int,
    params_id: str,
) -> dict[str, Any]:
    return {
        "v": 1,
        "kind": "SEAL-START",
        "employee_id": employee_id,
        "session_kind": kind.value,
        "binding": binding,
        "commitment": commitment_hex,
        "t0_ms": t0_ms,
        "epoch_ms": epoch_ms,
        "n_epochs": n_epochs,
        "params": params_id,
    }


def seal_start_challenge(statement: dict[str, Any]) -> bytes:
    return hashlib.sha256(canonical_json(statement)).digest()


def binding_for(kind: SealSessionKind, meeting_or_note: str) -> str:
    if kind == SealSessionKind.VOICE_NOTE:
        raw = meeting_or_note.strip()
        return tesla.canonical_binding(raw if raw.startswith("note:") else f"note:{raw}")
    b = tesla.canonical_binding(meeting_or_note)
    if b.startswith("note:"):
        raise RegistryError("bad_binding", "a meeting session cannot use a note: id")
    return b


@dataclass
class _Session:
    view: SealSession
    commitment: bytes
    keys: dict[int, bytes] = field(default_factory=dict)


@dataclass
class SealRegistry:
    passkeys: PasskeyStore
    _sessions: dict[str, _Session] = field(default_factory=dict)
    _commitments: set[bytes] = field(default_factory=set)

    def start_session(
        self,
        *,
        employee_id: str,
        kind: SealSessionKind,
        meeting: str,
        commitment_hex: str,
        t0_ms: int,
        epoch_ms: int,
        n_epochs: int,
        params_id: str,
        assertion: str | dict[str, Any],
        now: datetime,
    ) -> SealSession:
        binding = binding_for(kind, meeting)
        try:
            params = SealParams.from_id(params_id)
        except ValueError as e:
            raise RegistryError("bad_params", str(e)) from e
        if round(params.epoch_s * 1000) != epoch_ms:
            raise RegistryError("bad_params", "epoch_ms does not match the seal parameters")
        if not 0 < n_epochs <= MAX_EPOCHS:
            raise RegistryError("bad_params", f"n_epochs must be 1..{MAX_EPOCHS}")
        try:
            commitment = bytes.fromhex(commitment_hex)
        except ValueError as e:
            raise RegistryError("bad_commitment", "not hex") from e
        if len(commitment) != 32:
            raise RegistryError("bad_commitment", "must be 32 bytes")
        if commitment in self._commitments:
            raise RegistryError("replayed_commitment", "this commitment already started a session")
        t0 = datetime.fromtimestamp(t0_ms / 1000, tz=UTC)
        if abs(t0 - now) > MAX_START_SKEW:
            raise RegistryError("stale_start", "t0 is too far from the server clock")
        statement = seal_start_statement(
            employee_id=employee_id,
            kind=kind,
            binding=binding,
            commitment_hex=commitment_hex.lower(),
            t0_ms=t0_ms,
            epoch_ms=epoch_ms,
            n_epochs=n_epochs,
            params_id=params_id,
        )
        try:
            self.passkeys.verify_assertion(employee_id, assertion, seal_start_challenge(statement))
        except PasskeyError as e:
            raise RegistryError("passkey_rejected", str(e)) from e
        sid = f"seal_{secrets.token_hex(6)}"
        view = SealSession(
            id=sid,
            employee_id=employee_id,
            kind=kind,
            binding=binding,
            commitment=commitment_hex.lower(),
            t0=t0,
            epoch_s=epoch_ms / 1000,
            n_epochs=n_epochs,
            params_id=params_id,
            started_at=now,
        )
        self._sessions[sid] = _Session(view=view, commitment=commitment)
        self._commitments.add(commitment)
        return view

    def _get(self, session_id: str) -> _Session:
        s = self._sessions.get(session_id)
        if s is None:
            raise RegistryError("unknown_session", session_id)
        return s

    def get(self, session_id: str) -> SealSession:
        return self._get(session_id).view

    def disclose(self, session_id: str, epoch: int, key_hex: str, now: datetime) -> SealSession:
        s = self._get(session_id)
        v = s.view
        if not 0 <= epoch < v.n_epochs:
            raise RegistryError("bad_epoch", f"epoch must be 0..{v.n_epochs - 1}")
        if not tesla.epoch_has_ended(v.t0, v.epoch_s, epoch, now):
            raise RegistryError("epoch_not_ended", "a key may be disclosed only after its epoch")
        try:
            key = bytes.fromhex(key_hex)
        except ValueError as e:
            raise RegistryError("bad_key", "not hex") from e
        if len(key) != 32:
            raise RegistryError("bad_key", "must be 32 bytes")
        if epoch in s.keys:
            if s.keys[epoch] != key:
                raise RegistryError("key_mismatch", "does not match the hash chain")
            return v  # idempotent re-post
        last = v.last_disclosed_epoch
        ok = (
            tesla.key_matches_commitment(s.commitment, key, epoch)
            if last is None
            else tesla.key_follows(s.keys[last], last, key, epoch)
        )
        if not ok:
            raise RegistryError("key_mismatch", "does not match the hash chain")
        s.keys.update(tesla.earlier_keys(key, epoch))
        s.view = v.model_copy(update={"last_disclosed_epoch": epoch, "last_disclosed_at": now})
        return s.view

    def keys(self, session_id: str) -> dict[int, bytes]:
        return dict(self._get(session_id).keys)

    def meeting(self, meeting: str) -> list[SealMeetingView]:
        """Meeting sessions bound to this meeting, with their disclosed keys (for receivers)."""
        binding = tesla.canonical_binding(meeting)
        out = []
        for s in self._sessions.values():
            if s.view.kind == SealSessionKind.MEETING and s.view.binding == binding:
                keys = [SealKey(epoch=e, key=k.hex()) for e, k in sorted(s.keys.items())]
                out.append(SealMeetingView(session=s.view, keys=keys))
        return out

    def sessions_for(self, employee_id: str) -> list[SealSession]:
        return [s.view for s in self._sessions.values() if s.view.employee_id == employee_id]

    def live_elsewhere(self, employee_id: str, binding: str, now: datetime) -> list[SealSession]:
        """Meeting sessions of this employee that are live right now in ANOTHER meeting.

        Live = a key was disclosed within one epoch plus LIVE_GRACE_S. Used for
        SEAL_PRESENCE_CONFLICT; passkey-started sessions are trusted data.
        """
        out = []
        for v in self.sessions_for(employee_id):
            if v.kind != SealSessionKind.MEETING or v.binding == binding:
                continue
            if v.last_disclosed_at is None:
                continue
            if now - v.last_disclosed_at <= timedelta(seconds=v.epoch_s + tesla.LIVE_GRACE_S):
                out.append(v)
        return out
