"""Versioned companion contracts shared by the Electron app and the local FastAPI engine (T25).

These models are deliberately narrow. The HTTP layer cannot carry a policy band, a raw score,
a confidence or a probability: unknown fields are rejected and payload keys are screened. The
`band` field on an event payload is a relay of a `satyapan.policy` Decision, never a UI input.
"""

from __future__ import annotations

import warnings
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


# ---------------------------------------------------------------------------------------------
# Finale additions (F01). Mirrors `desktop/shared/contracts.ts`. No score/probability fields.
# ---------------------------------------------------------------------------------------------
class UserMode(StrEnum):
    """What the user asked for (distinct from CompanionMode, which is what Satya is doing)."""

    WATCHING = "WATCHING"
    SLEEPING = "SLEEPING"
    OFF = "OFF"


class Pose(StrEnum):
    """The ten mascot poses from docs/finale/MASCOT_SPEC.md §4."""

    SLEEP = "sleep"
    IDLE = "idle"
    LISTEN = "listen"
    THINK = "think"
    ALERT = "alert"
    RELIEF = "relief"
    WRITE = "write"
    CATCH = "catch"
    WAVE = "wave"
    OFF = "off"


class Lang(StrEnum):
    EN = "en"
    HINGLISH = "hinglish"
    HI = "hi"


class Coverage(StrEnum):
    """Audio quality gate: degraded/incomplete audio means abstain from acoustic conclusions."""

    USABLE = "usable"
    DEGRADED = "degraded"
    INCOMPLETE = "incomplete"


class SealStatus(StrEnum):
    """A missing Seal means 'not verified by Seal', never 'fake'."""

    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    UNAVAILABLE = "unavailable"


class CaptureSourceKind(StrEnum):
    EXTENSION = "extension"
    LOOPBACK = "loopback"
    REPLAY = "replay"


AskCode = Literal["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
OobOutcome = Literal["approved", "rejected", "not_requested", "expired"]
ReportSource = Literal["maker_entered", "vault", "vendor_master", "user_confirmed", "system"]


class AskChip(Model):
    """An ask chip observed in a call or message. `at_s` is seconds in, when known."""

    code: AskCode
    at_s: float | None = Field(default=None, ge=0)


class AskQuote(Model):
    """The exact words that produced an ask chip, so the user sees *why*."""

    code: AskCode
    text: str = Field(max_length=200)
    at_s: float | None = None


class OobTicket(Model):
    """A challenge sent to an approver from the directory/master. It never carries a band."""

    oob_id: str = Field(min_length=1, max_length=120)
    case_id: str = Field(min_length=1, max_length=120)
    approver_name: str = Field(min_length=1, max_length=120)
    channel: Literal["console", "email"] = "console"
    inbox_url: str = Field(min_length=1, max_length=2048)
    expires_at: datetime


class OobSummary(Model):
    oob_id: str = Field(min_length=1, max_length=120)
    approver_name: str = Field(min_length=1, max_length=120)
    outcome: OobOutcome | None = None


with warnings.catch_warnings():
    # `copy` is part of the frozen JSON contract (mirrors contracts.ts); it only shadows
    # BaseModel.copy(), which companion code never calls.
    warnings.filterwarnings("ignore", message='Field name "copy"', category=UserWarning)

    class ReportField(Model):
        """One line of a draft. Every line cites where it came from."""

        label: str = Field(min_length=1, max_length=160)
        value: str = Field(default="", max_length=4000)
        source: ReportSource
        evidence_id: str | None = None
        copy: bool = True
        sensitive: bool = False


class ReportSection(Model):
    """A draft section for a destination. Always DRAFT_REQUIRES_HUMAN_REVIEW."""

    id: Literal["helpline_1930", "bank_fraud_desk", "ncrp_portal", "cert_in", "bsa_s63_part_a"]
    title: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=240)
    deadline_hint: str | None = Field(default=None, max_length=160)
    body: str = ""
    fields: list[ReportField] = Field(default_factory=list)
    open_url: str | None = Field(default=None, max_length=2048)
    applies: bool = True
    status: Literal["DRAFT_REQUIRES_HUMAN_REVIEW"] = "DRAFT_REQUIRES_HUMAN_REVIEW"


class ReportPackV2(Model):
    """Golden-hour report pack. A human always presses Submit; no code path files anything."""

    version: Literal["2"] = "2"
    case_id: str = Field(min_length=1, max_length=120)
    generated_at: datetime = Field(default_factory=utcnow)
    money_left_at: datetime | None = None
    sections: list[ReportSection] = Field(default_factory=list)
    submission: Literal["MANUAL_ONLY"] = MANUAL_ONLY
    auto_submit: Literal[False] = False


class ScreenFinding(Model):
    """What Screen Guard noticed in on-screen text. Informational until the user hands the
    text to Satya as evidence (then the policy engine decides). Text is never stored."""

    app: str | None = Field(default=None, max_length=80)
    meeting: str | None = Field(default=None, max_length=80)
    asks: list[AskQuote] = Field(default_factory=list)
    cues: list[str] = Field(default_factory=list)
    accounts_masked: list[str] = Field(default_factory=list)
    unknown_accounts_masked: list[str] = Field(default_factory=list)
    vendors: list[str] = Field(default_factory=list)
    suspicious: bool = False


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
    # Finale additions (F01): live/OOB/report fan-in.
    CALL_STARTED = "call.started"
    CALL_STOPPED = "call.stopped"
    LIVE_CHIPS = "live.chips"
    COVERAGE_CHANGED = "coverage.changed"
    OOB_SENT = "oob.sent"
    OOB_RESULT = "oob.result"
    CASE_UPDATED = "case.updated"
    REPORT_READY = "report.ready"
    # Speech-engine status for the active call (finale), e.g. "asr_unavailable".
    CALL_STATUS = "call.status"
    # Screen Guard (finale): payment tricks noticed in on-screen text, on-device OCR.
    SCREEN_FINDING = "screen.finding"


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
    # Finale additions (F01): all optional so old events stay valid. No scores.
    case_id: str | None = Field(default=None, max_length=120)
    call_id: str | None = Field(default=None, max_length=120)
    chips: list[AskChip] = Field(default_factory=list)
    coverage: Coverage | None = None
    seal: SealStatus | None = None
    oob: OobSummary | None = None
    ticket: OobTicket | None = None
    report: ReportPackV2 | None = None
    user_mode: UserMode | None = None
    pose: Pose | None = None
    # Finale: exact ask quotes, engine status, screen findings. Still no scores; captions
    # never travel on this bus (see live_fan_in.py).
    quotes: list[AskQuote] = Field(default_factory=list)
    status_code: str | None = Field(default=None, max_length=40)
    screen: ScreenFinding | None = None
    # Who "Verify" will ask (from the employee directory, never from the call or message).
    approver_name: str | None = Field(default=None, max_length=120)

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


# ---------------------------------------------------------------------------------------------
# F03 — call management, file intake and OOB glue. Still no band input and no score fields.
# ---------------------------------------------------------------------------------------------
class CallStartRequest(Model):
    """Start listening to one call. The companion session must already be consented."""

    version: Literal["1"] = CONTRACT_VERSION
    source: CaptureSourceKind
    consent_id: str = Field(min_length=1, max_length=120)
    maker: str | None = Field(default=None, max_length=120)
    # Speech language hint: "en", "hi", or None for auto-detect. Routing only, never a risk
    # feature (accent and language never change a band).
    language: str | None = Field(default=None, pattern=r"^(en|hi|auto)$")


class CallStartResponse(Model):
    version: Literal["1"] = CONTRACT_VERSION
    call_id: str = Field(pattern=r"^call_[A-Za-z0-9_\-]+$")
    case_id: str = Field(pattern=r"^case_[A-Za-z0-9_\-]+$")
    events: list[CompanionEvent] = Field(default_factory=list)


class CallStopRequest(Model):
    version: Literal["1"] = CONTRACT_VERSION
    call_id: str | None = Field(default=None, max_length=120)


class CallStopResponse(Model):
    version: Literal["1"] = CONTRACT_VERSION
    call_id: str
    state: CompanionStateSnapshot
    events: list[CompanionEvent] = Field(default_factory=list)


class CompanionOobRequest(Model):
    """Ask the real approver to confirm this exact transaction (OOB-Confirm)."""

    version: Literal["1"] = CONTRACT_VERSION
    case_id: str = Field(pattern=r"^case_[A-Za-z0-9_\-]+$")


# ---------------------------------------------------------------------------------------------
# Finale — Screen Guard text check and engine health.
# ---------------------------------------------------------------------------------------------
class ScreenTextRequest(Model):
    """On-device OCR text from the user's screen, sent only to the local engine. Not stored."""

    version: Literal["1"] = CONTRACT_VERSION
    text: str = Field(max_length=60_000)
    app: str | None = Field(default=None, max_length=80)
    publish: bool = True


class ScreenTextResponse(Model):
    version: Literal["1"] = CONTRACT_VERSION
    finding: ScreenFinding
    events: list[CompanionEvent] = Field(default_factory=list)
