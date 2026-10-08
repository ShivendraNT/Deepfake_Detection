"""Seal results -> policy Signals (deterministic, raise-only; the policy engine sets the band).

Rules (docs/SEAL.md §Policy):
* VOICE_SEALED (info, never raises, never lowers, never clears): the audio carries a valid seal
  from an enrolled executive's device for this session. Detail says WHO sealed it.
* VOICE_UNSEALED_CLAIMED_EXEC (weak, VERIFY): an enrolled executive is CLAIMED (display name,
  WhatsApp contact name, or the maker's own entry) and at least MIN_UNSEALED_SPEECH_S seconds of
  speech carry no seal from that executive. "Not sealed" is never shown as "fake".
* SEAL_PRESENCE_CONFLICT (strong, HOLD with money movement, else VERIFY): the claimed executive's
  passkey-started session is live in ANOTHER meeting right now, and the speech here is not sealed.

Live-call note: in a multi-party meeting the 15 s must be speech attributed to the claimed
participant (active-speaker attribution); that wiring is finale work. For uploads (a voice note
claimed to be from the executive) all speech is attributed to the claimed sender.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from satyapan.contracts.enums import ReasonCode, SealEpochStatus, SealSessionKind, SignalSource
from satyapan.contracts.evidence import Signal
from satyapan.contracts.seal import SealVerification
from satyapan.seal.registry import SealRegistry

DETECTOR = "satyapan_seal"
MIN_UNSEALED_SPEECH_S = 15.0


def unsealed_speech_seconds(v: SealVerification, epoch_s: float) -> float:
    """Speech seconds NOT covered by sealed epochs (whole file if not sealed)."""
    if not v.sealed:
        return v.speech_seconds
    n_unsealed = sum(e.status == SealEpochStatus.UNSEALED for e in v.epochs)
    return min(v.speech_seconds, n_unsealed * epoch_s)


def voice_seal_signals(
    verifications: Sequence[SealVerification],
    *,
    claimed_employee_id: str | None,
    claimed_enrolled: bool,
    speech_seconds: float,
    evidence_ids: Sequence[str] = (),
    epoch_s: float = 5.0,
) -> list[Signal]:
    """Signals for one piece of audio checked against every relevant seal session."""
    out: list[Signal] = []
    sealed_by: set[str] = set()
    for v in verifications:
        if not v.sealed or v.employee_id is None or v.employee_id in sealed_by:
            continue
        sealed_by.add(v.employee_id)
        out.append(
            Signal.make(
                ReasonCode.VOICE_SEALED,
                source=SignalSource.DETERMINISTIC,
                evidence_ids=list(evidence_ids),
                detector=DETECTOR,
                detail={
                    "sealed_by": v.employee_id,
                    "session_id": v.session_id,
                    "epochs_sealed": v.n_epochs_sealed,
                    "epochs_with_speech": v.n_epochs_speech,
                    "gaps": len(v.gaps),
                },
            )
        )
    if not claimed_employee_id or not claimed_enrolled:
        return out
    own = [v for v in verifications if v.sealed and v.employee_id == claimed_employee_id]
    unsealed = (
        min(unsealed_speech_seconds(v, epoch_s) for v in own) if own else float(speech_seconds)
    )
    if unsealed >= MIN_UNSEALED_SPEECH_S:
        out.append(
            Signal.make(
                ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC,
                source=SignalSource.DETERMINISTIC,
                evidence_ids=list(evidence_ids),
                detector=DETECTOR,
                detail={
                    "claimed": claimed_employee_id,
                    "unsealed_speech_s": round(unsealed, 1),
                    "partly_sealed": bool(own),
                },
            )
        )
    return out


def presence_conflict_signal(
    registry: SealRegistry,
    *,
    claimed_employee_id: str,
    meeting_binding: str,
    sealed_here: bool,
    now: datetime,
    evidence_ids: Sequence[str] = (),
) -> Signal | None:
    """SEAL_PRESENCE_CONFLICT when the claimed exec is live-sealing a different meeting."""
    if sealed_here:
        return None
    elsewhere = [
        s
        for s in registry.live_elsewhere(claimed_employee_id, meeting_binding, now)
        if s.kind == SealSessionKind.MEETING
    ]
    if not elsewhere:
        return None
    return Signal.make(
        ReasonCode.SEAL_PRESENCE_CONFLICT,
        source=SignalSource.DETERMINISTIC,
        evidence_ids=list(evidence_ids),
        detector=DETECTOR,
        detail={"claimed": claimed_employee_id, "live_sessions_elsewhere": len(elsewhere)},
    )
