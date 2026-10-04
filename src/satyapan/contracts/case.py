"""Case, decision, clearance and verification records. CONTRACT FILE."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from satyapan.contracts.common import Model, Sha256Hex
from satyapan.contracts.enums import (
    ActionType,
    Band,
    CallbackOutcome,
    CaseKind,
    CaseStatus,
    ClearanceMethod,
    GreyReason,
    OOBResult,
    Queue,
    ReasonCode,
    Role,
)
from satyapan.contracts.evidence import Evidence, Signal
from satyapan.contracts.master import MasterChange
from satyapan.contracts.transaction import PaymentAction

OOBChannel = Literal["ses", "in_app"]


def _default_channels() -> list[OOBChannel]:
    return ["in_app"]


class OOBRequest(Model):
    """OOB-Confirm: 'Did you ask for this payment?' sent to the claimed requester (T12).

    The raw token is NEVER stored; only its SHA-256 (`token_sha256`).
    binding_hash = SHA-256(case_id ‖ amount ‖ beneficiary_hash ‖ nonce).
    """

    id: str = Field(pattern=r"^oob_[A-Za-z0-9_\-]+$")
    case_id: str
    requester_employee_id: str
    sent_to_email: str
    message_text: str
    binding_hash: Sha256Hex
    nonce: str  # not secret; stored so the binding can be re-verified
    token_sha256: Sha256Hex
    created_at: datetime
    expires_at: datetime
    result: OOBResult = OOBResult.PENDING
    responded_at: datetime | None = None
    responded_by: str | None = None
    channels: list[OOBChannel] = Field(default_factory=_default_channels)
    spent: bool = False


class CallbackRecord(Model):
    """A logged callback. The number MUST come from the master/directory, never a message."""

    id: str = Field(pattern=r"^cb_[A-Za-z0-9_\-]+$")
    case_id: str
    performed_by: str  # employee_id
    performed_as: Role
    number_dialed: str
    number_source: Literal["vendor_master", "vendor_master_old", "directory"]
    outcome: CallbackOutcome
    confirmed_by_name: str | None = None
    bank_shown_payee_name: str | None = None
    at: datetime
    notes: str = ""


class OverrideRecord(Model):
    """Urgent legitimate payment override: two distinct senior approvers, reason, 48 h review."""

    approver_ids: list[str] = Field(min_length=2)
    reason: str = Field(min_length=10)
    at: datetime
    review_due_at: datetime

    @model_validator(mode="after")
    def _distinct(self) -> OverrideRecord:
        if len(set(self.approver_ids)) < 2:
            raise ValueError("override needs two DISTINCT approvers")
        return self


class ClearanceRequirement(Model):
    """What must happen before the payment may proceed. Clearing never lowers the band."""

    band: Band
    who: list[Role] = Field(default_factory=list)
    methods: list[ClearanceMethod] = Field(default_factory=list)
    mode: Literal["any", "all", "none"] = "none"
    callback_number: str | None = None
    callback_number_source: (
        Literal["vendor_master", "vendor_master_old", "directory", "independent_source"] | None
    ) = None
    notes: list[str] = Field(default_factory=list)


class Decision(Model):
    """Output of satyapan.policy.engine.decide(). Only the policy engine creates these."""

    band: Band
    floor_band: Band
    action_type: ActionType
    reason_codes: list[ReasonCode]  # codes that set or raised the band; floor code first
    info_codes: list[ReasonCode] = Field(default_factory=list)  # informational, no band effect
    clearance: ClearanceRequirement
    queue: Queue = Queue.MAKER
    suggested_status: CaseStatus | None = None
    grey: bool = False
    policy_version: str
    decided_at: datetime


class Case(Model):
    id: str = Field(pattern=r"^case_[A-Za-z0-9_\-]+$")
    title: str
    kind: CaseKind
    created_at: datetime
    created_by: str
    txn: PaymentAction | None = None
    master_change: MasterChange | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    grey_reasons: list[GreyReason] = Field(default_factory=list)
    oob: OOBRequest | None = None
    callbacks: list[CallbackRecord] = Field(default_factory=list)
    linked_call_ids: list[str] = Field(default_factory=list)
    status: CaseStatus = CaseStatus.OPEN
    queue: Queue = Queue.MAKER
    decision: Decision | None = None
    override: OverrideRecord | None = None
    security_acknowledged_by: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _kind_fields(self) -> Case:
        if self.kind == "PAYMENT" and self.txn is None:
            raise ValueError("PAYMENT case needs txn")
        if self.kind == "MASTER_CHANGE" and self.master_change is None:
            raise ValueError("MASTER_CHANGE case needs master_change")
        return self
