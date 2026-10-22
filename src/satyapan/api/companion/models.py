"""Versioned companion contracts shared by the Electron app and the local FastAPI engine (T25).

These models are deliberately narrow. The HTTP layer cannot carry a policy band, a raw score,
a confidence or a probability: unknown fields are rejected and payload keys are screened. The
`band` field on an event payload is a relay of a `satyapan.policy` Decision, never a UI input.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from satyapan.contracts.common import Model, utcnow
from satyapan.contracts.enums import ActionType, Band, CaseStatus, Channel, Queue, ReasonCode

CONTRACT_VERSION = "1"
POLICY_AUTHORITY = "satyapan.policy"
MANUAL_ONLY = "MANUAL_ONLY"

# Keys a companion client may never send or receive: oracle-abuse and band-authority guards.
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "band",
        "floor_band",
        "score",
        "scores",
        "confidence",
        "probability",
        "risk_score",
        "risk_band",
        "z_score",
    }
)


def assert_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    """Raise ValueError if a nested mapping contains a score/band-control key."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().lower() in FORBIDDEN_KEYS:
                raise ValueError(f"{path}.{key} is not accepted by the companion API")
            assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_forbidden_keys(child, path=f"{path}[{index}]")


class CompanionMode(StrEnum):
    """Six states from docs/GRAND_FINALS_ARCHITECTURE.md §3. Default is SLEEP (DND)."""

    SLEEP = "SLEEP"
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    ALERT = "ALERT"
    SCRIBE = "SCRIBE"
    DISABLED = "DISABLED"


class MascotMood(StrEnum):
    """Only expressions the renderer knows. Mood never encodes a hidden risk score."""

    SLEEPY = "sleepy"
    ATTENTIVE = "attentive"
    FOCUSED = "focused"
    CALM_ALERT = "calm_alert"
    WRITING = "writing"
    OFF = "off"


class CompanionSource(StrEnum):
    """Explicitly consented sources. No implicit/system-wide capture."""

    DEMO_REPLAY = "demo_replay"
    USER_SELECTED_EMAIL = "user_selected_email"
    USER_SELECTED_LOOPBACK = "user_selected_loopback"
    USER_SELECTED_MICROPHONE = "user_selected_microphone"


class CompanionEventType(StrEnum):
    STATE_CHANGED = "state.changed"
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    EVIDENCE_RECEIVED = "evidence.received"
    ALERT_RAISED = "alert.raised"
    DRAFT_READY = "draft.ready"
    SESSION_STARTED = "session.started"
    SESSION_STOPPED = "session.stopped"
    ERROR = "error"


class DraftKind(StrEnum):
    SECTION_63 = "section63"
    HELPLINE_1930 = "helpline_1930"


class NextAction(Model):
    """A safe next step. `oob_verify` only uses a directory/master contact (never message data)."""

    id: str = Field(pattern=r"^[a-z0-9_\-]+$")
    label: str = Field(min_length=1, max_length=80)
    variant: Literal["primary", "outline", "ghost"] = "outline"


class CompanionPayload(Model):
    """Event payload. Contains explanations and references, never detector scores."""

    state: CompanionMode
    mascot_mood: MascotMood
    headline: str = Field(min_length=1, max_length=140)
    explanation: str = Field(default="", max_length=2000)
    band: Band | None = None  # relay of a policy Decision only
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    info_codes: list[ReasonCode] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    monitoring: bool = False
    source: CompanionSource | None = None
    mode_label: str | None = Field(default=None, max_length=80)
    demo: bool = False

    @model_validator(mode="after")
    def _no_score_fields(self) -> CompanionPayload:
        for item in self.reason_codes + self.info_codes:
            if item.value.lower().endswith(("_SCORE", "_PROBABILITY")):
                raise ValueError("score-like reason codes are not exposed to the companion")
        return self


class CompanionEvent(Model):
    """Versioned SSE envelope. `event_id` is assigned by the bounded bus (monotonic)."""

    version: Literal["1"] = CONTRACT_VERSION
    event_id: str = Field(default="evt_00000000", pattern=r"^evt_[0-9]{8}$")
    type: CompanionEventType
    session_id: str | None = Field(default=None, pattern=r"^session_[A-Za-z0-9_\-]+$")
    occurred_at: datetime = Field(default_factory=utcnow)
    payload: CompanionPayload


class CompanionStateSnapshot(Model):
    """What the UI may show about consent and capture. Safe to log."""

    version: Literal["1"] = CONTRACT_VERSION
    mode: CompanionMode = CompanionMode.SLEEP
    hidden: bool = False
    monitoring: bool = False
    session_id: str | None = None
    consent_id: str | None = None
    source: CompanionSource | None = None
    source_label: str | None = Field(default=None, max_length=80)
    started_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    demo: bool = False
    mode_label: str | None = None
    last_event_id: str | None = None
    policy_authority: Literal["satyapan.policy"] = POLICY_AUTHORITY
    raw_scores_visible: Literal[False] = False
    manual_only: Literal[True] = True


class SessionStartRequest(Model):
    version: Literal["1"] = CONTRACT_VERSION
    consent: bool
    source: CompanionSource
    label: str | None = Field(default=None, max_length=80)


class SessionStartResponse(Model):
    version: Literal["1"] = CONTRACT_VERSION
    state: CompanionStateSnapshot
    events: list[CompanionEvent] = Field(default_factory=list)


class CommandType(StrEnum):
    DEMO_REPLAY = "demo.replay"
    SESSION_SLEEP = "session.sleep"
    SESSION_STOP = "session.stop"
    UI_HIDE = "ui.hide"
    UI_SHOW = "ui.show"
    UI_DISABLE = "ui.disable"


class CommandRequest(Model):
    version: Literal["1"] = CONTRACT_VERSION
    request_id: str = Field(pattern=r"^req_[A-Za-z0-9_\-]+$")
    type: CommandType
    session_id: str | None = Field(default=None, pattern=r"^session_[A-Za-z0-9_\-]+$")
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _commands_cannot_control_the_band(self) -> CommandRequest:
        assert_no_forbidden_keys(self.payload)
        if self.type == CommandType.DEMO_REPLAY:
            scenario = self.payload.get("scenario", "beneficiary_change")
            if not isinstance(scenario, str):
                raise ValueError("scenario must be a string")
            self.payload["scenario"] = scenario
        return self


class CommandResponse(Model):
    version: Literal["1"] = CONTRACT_VERSION
    request_id: str
    accepted: bool
    state: CompanionStateSnapshot
    events: list[CompanionEvent] = Field(default_factory=list)


class EvidenceSubmitRequest(Model):
    version: Literal["1"] = CONTRACT_VERSION
    request_id: str = Field(pattern=r"^req_[A-Za-z0-9_\-]+$")
    session_id: str | None = Field(default=None, pattern=r"^session_[A-Za-z0-9_\-]+$")
    source: CompanionSource
    consent: bool
    evidence_id: str = Field(pattern=r"^ev_[A-Za-z0-9_\-]+$")
    text: str = Field(min_length=1, max_length=20_000)
    case_id: str | None = None


class EvidenceSubmitResponse(Model):
    version: Literal["1"] = CONTRACT_VERSION
    request_id: str
    accepted: bool
    evidence_id: str
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    info_codes: list[ReasonCode] = Field(default_factory=list)
    ask_count: int = 0
    band_set_by_companion: Literal[False] = False
    events: list[CompanionEvent] = Field(default_factory=list)


class DraftRequest(Model):
    version: Literal["1"] = CONTRACT_VERSION
    kind: DraftKind
    case_id: str = Field(pattern=r"^case_[A-Za-z0-9_\-]+$")


class DraftArtifact(Model):
    """An editable draft. It is never submitted by any code path."""

    version: Literal["1"] = CONTRACT_VERSION
    draft_id: str = Field(pattern=r"^draft_[A-Za-z0-9_\-]+$")
    kind: DraftKind
    case_id: str
    status: Literal["DRAFT_REQUIRES_HUMAN_REVIEW"] = "DRAFT_REQUIRES_HUMAN_REVIEW"
    submission: Literal["MANUAL_ONLY"] = MANUAL_ONLY
    auto_submit: Literal[False] = False
    generated_at: datetime = Field(default_factory=utcnow)
    fields: dict[str, str | int | bool | None] = Field(default_factory=dict)
    disclaimers: list[str] = Field(default_factory=list)


class EvidenceRef(Model):
    evidence_id: str
    channel: Channel
    filename: str | None = None
    size_bytes: int = Field(ge=0)
    sha256_short: str = Field(pattern=r"^[0-9a-f]{12}$")
    excerpt: str | None = Field(default=None, max_length=300)


class AuditRow(Model):
    at: datetime = Field(default_factory=utcnow)
    actor: str
    action: str
    detail: str = ""


class WorkspaceSnapshot(Model):
    """Safe case view for the details window: no detector scores, masked payee details."""

    version: Literal["1"] = CONTRACT_VERSION
    case_id: str
    title: str
    kind: str
    status: CaseStatus
    band: Band
    floor_band: Band
    action_type: ActionType
    queue: Queue
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    info_codes: list[ReasonCode] = Field(default_factory=list)
    explanation: str = ""
    payee_masked: str | None = None
    amount_inr: int | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    drafts: list[DraftArtifact] = Field(default_factory=list)
    audit: list[AuditRow] = Field(default_factory=list)
    policy_authority: Literal["satyapan.policy"] = POLICY_AUTHORITY
    raw_scores_visible: Literal[False] = False
    manual_only: Literal[True] = True


class CaseSummary(Model):
    case_id: str
    title: str
    status: CaseStatus
    band: Band
    queue: Queue
    updated_at: datetime = Field(default_factory=utcnow)


class CompanionAuditFeed(Model):
    version: Literal["1"] = CONTRACT_VERSION
    rows: list[AuditRow] = Field(default_factory=list)
    policy_authority: Literal["satyapan.policy"] = POLICY_AUTHORITY
    raw_scores_visible: Literal[False] = False
