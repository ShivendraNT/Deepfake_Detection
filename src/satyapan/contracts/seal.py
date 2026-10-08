"""Satyapan Seal contracts: Voice Seal sessions/verifications and Intent Seal. CONTRACT FILE.

Design and threat model: docs/SEAL.md. Code: src/satyapan/seal/.

Nothing here is biometric. A seal session holds only public values: a hash-chain commitment,
timing parameters and (after each epoch has ended) the disclosed epoch keys. Audio never
reaches the registry.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from satyapan.contracts.common import Model, Sha256Hex
from satyapan.contracts.enums import SealEpochStatus, SealSessionKind


class SealSession(Model):
    """One passkey-started seal session (one meeting, or one voice note)."""

    id: str = Field(pattern=r"^seal_[A-Za-z0-9_\-]+$")
    employee_id: str
    kind: SealSessionKind
    binding: str  # canonical "meet:<code>" / "url:<host/path>" / "note:<id>"
    commitment: Sha256Hex  # hex of H(K_0); K_e = H(K_{e+1}) (TESLA chain)
    t0: datetime  # wall-clock start of epoch 0
    epoch_s: float = Field(gt=0)
    n_epochs: int = Field(gt=0)  # chain length: the session cannot run longer
    params_id: str  # seal parameter set, e.g. "vs1-12b-300-3400-6f-104c-625f-2.0dB"
    started_at: datetime
    last_disclosed_epoch: int | None = None
    last_disclosed_at: datetime | None = None


class SealKey(Model):
    """A disclosed epoch key (hex). Public once its epoch has ended."""

    epoch: int = Field(ge=0)
    key: Sha256Hex


class SealMeetingView(Model):
    """GET /seal/meetings/{meeting}: a session plus the keys a live receiver may use."""

    session: SealSession
    keys: list[SealKey] = Field(default_factory=list)


class SealEpoch(Model):
    """Per-epoch verification result. `z` is a raw score: stripped for the maker role."""

    epoch: int = Field(ge=0)
    start_s: float  # where this epoch starts in the analysed audio
    cells: int = Field(ge=0)  # band x chip cells with speech (0 = silence)
    status: SealEpochStatus
    z: float | None = None


class SealGap(Model):
    """A run of epochs that contain speech but no seal, inside a sealed recording."""

    first_epoch: int
    last_epoch: int
    start_s: float
    end_s: float


class SealVerification(Model):
    """Result of verifying a recording / voice note against one seal session."""

    session_id: str | None = None
    employee_id: str | None = None
    binding: str | None = None
    sealed: bool
    decided_by: str  # acquisition_1 | acquisition_2 | stouffer | not_sealed | no_keys
    decided_at_epoch: int | None = None
    offset_s: float | None = None  # where epoch `first_epoch` starts in the file
    first_epoch: int = 0
    acquisition_threshold: float
    acquisition_statistic: float | None = None  # raw score: stripped for makers
    stouffer_z: float | None = None  # raw score: stripped for makers
    epochs: list[SealEpoch] = Field(default_factory=list)
    n_epochs_speech: int = 0
    n_epochs_sealed: int = 0
    gaps: list[SealGap] = Field(default_factory=list)
    speech_seconds: float = 0.0
    audio_seconds: float = 0.0
    params_id: str
    verifier_version: str
    # Uploaded files cannot prove WHEN the audio was made (TESLA timing is a live-call property).
    timing_provable: bool = False
    notes: list[str] = Field(default_factory=list)


class IntentBeneficiary(Model):
    """Beneficiary as signed: a hash of the full account plus what the approver is shown."""

    account_sha256: Sha256Hex
    account_masked: str
    ifsc: str | None = None


class PaymentIntent(Model):
    """Intent Seal: the exact payment a passkey approves. Challenge = SHA-256(canonical JSON)."""

    v: int = 1
    case_id: str
    requester: str  # employee id of the person whose passkey must sign
    action: str  # e.g. "PAY_NEW_BENEFICIARY"
    amount_inr: int = Field(gt=0)  # whole rupees
    beneficiary: IntentBeneficiary
    nonce: str = Field(min_length=16)
    expires_at: int  # unix seconds
