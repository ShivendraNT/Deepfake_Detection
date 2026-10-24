"""Companion service: consent lifecycle, policy relay, evidence intake and drafts (T25).

Safety design:
* The service never computes a band. Demo scenarios call `satyapan.policy.engine.decide()` and
  relay the resulting `Decision`; the HTTP layer cannot send a band at all.
* Starting any session requires explicit consent. Hide/disable/window-close clear the session
  before anything is published, so monitoring can never continue invisibly.
* Evidence intake runs the deterministic ask extractor only. An ask is not a band.
* Every draft is editable, `MANUAL_ONLY` and has no submission code path.
"""

from __future__ import annotations

import hashlib
import re
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from satyapan.api.companion.bus import CompanionBus
from satyapan.api.companion.live_fan_in import attach_live_bus
from satyapan.api.companion.models import (
    MANUAL_ONLY,
    AskChip,
    AskQuote,
    AuditRow,
    CallStartRequest,
    CaptureSourceKind,
    CaseSummary,
    CommandRequest,
    CommandType,
    CompanionEvent,
    CompanionEventType,
    CompanionMode,
    CompanionPayload,
    CompanionSource,
    CompanionStateSnapshot,
    Coverage,
    DraftArtifact,
    DraftKind,
    EvidenceRef,
    EvidenceSubmitRequest,
    EvidenceSubmitResponse,
    MascotMood,
    NextAction,
    OobSummary,
    OobTicket,
    PolicyTrace,
    ReportField,
    ReportPackV2,
    ReportSection,
    ScreenFinding,
    SealStatus,
    SessionStartRequest,
    TraceSignal,
    WorkspaceSnapshot,
)
from satyapan.asks.extractor import extract_asks
from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import (
    ASK_TO_REASON,
    Band,
    CaseKind,
    Channel,
    CustodyEvent,
    Lang,
    PaymentRail,
    ReasonCode,
    SignalSource,
    VoiceLabel,
)
from satyapan.contracts.evidence import Evidence, Signal
from satyapan.contracts.live import (
    AskEvent,
    BandEvent,
    LiveEvent,
    StatusEvent,
    TranscriptEvent,
    VoiceEvent,
)
from satyapan.contracts.transaction import PaymentAction
from satyapan.explain.templates import explain_template, reason_text
from satyapan.master.store import MasterData
from satyapan.pipeline import PipelineContext, analyze_evidence, merge_output, recompute
from satyapan.policy.bands import rank as band_rank
from satyapan.policy.config import DEFAULT_CONFIG, PolicyConfig
from satyapan.policy.engine import decide
from satyapan.repository import CaseRepository

if TYPE_CHECKING:  # avoids a runtime import cycle (state -> companion -> state)
    from satyapan.api.state import AppState

SESSION_TTL = timedelta(hours=8)
AUDIT_CAPACITY = 200
DEMO_LABEL = "DEMO REPLAY — NOT LIVE CAPTURE"
_DEFAULT_ACTIONS = [
    NextAction(id="oob_verify", label="Verify using a saved contact", variant="primary"),
    NextAction(id="open_scribe", label="Prepare an incident draft", variant="outline"),
    NextAction(id="open_workspace", label="View details", variant="outline"),
]
_ALERT_ACTIONS = [
    NextAction(id="verify", label="Verify with the approver", variant="primary"),
    NextAction(id="copy_reply", label="Copy a safe reply", variant="outline"),
    NextAction(id="open_notebook", label="Open Notebook", variant="outline"),
]
# A live chunk is 10 s (T11). AskEvent carries the chunk index, not the span time.
LIVE_CHUNK_SECONDS = 10.0


class CompanionError(ValueError):
    """A client-correctable companion request error (mapped to HTTP 400)."""


class ConsentRequiredError(PermissionError):
    """Raised when an operation needs explicit, visible user consent."""


class CompanionNotFound(CompanionError):
    """A requested case/draft does not exist (mapped to HTTP 404)."""


@dataclass(frozen=True)
class DemoScenario:
    """Generated, fake demo material. No real person, vendor, account or media is used."""

    key: str
    title: str
    text: str
    amount_inr: int
    payee: str
    account_number: str
    ifsc: str


DEMO_SCENARIOS: dict[str, DemoScenario] = {
    "beneficiary_change": DemoScenario(
        key="beneficiary_change",
        title="Urgent beneficiary change (demo replay)",
        text=(
            "Sir, this is urgent. Please change the beneficiary bank account to the new one "
            "I am sending and process the payment today before the bank closes."
        ),
        amount_inr=284_000,
        payee="Demo Narmada Logistics (fictional)",
        account_number="99992222009917",
        ifsc="FAKC0000991",
    ),
    "urgent_bypass": DemoScenario(
        key="urgent_bypass",
        title="Secrecy and remote-access request (demo replay)",
        text=(
            "Keep this between us and do not tell the accounts team. Install AnyDesk and "
            "share the OTP so I can release the vendor payment before the audit."
        ),
        amount_inr=640_000,
        payee="Demo Sagar Traders (fictional)",
        account_number="99992222009918",
        ifsc="FAKC0000992",
    ),
    "cfo_call": DemoScenario(
        key="cfo_call",
        title="Deepfake CFO call: Urgent wire bypass (demo replay)",
        text=(
            "Priya, I am in an urgent board meeting and traveling. Transfer ₹48,50,000 immediately "
            "to the new account details I am sending. Bypass the checker process and "
            "keep this confidential between us until the acquisition closes."
        ),
        amount_inr=4_850_000,
        payee="Demo Apex Strategic Ltd (fictional)",
        account_number="99992222009919",
        ifsc="FAKC0000993",
    ),
}

_MOOD_BY_MODE: dict[CompanionMode, MascotMood] = {
    CompanionMode.SLEEP: MascotMood.SLEEPY,
    CompanionMode.ACTIVE: MascotMood.ATTENTIVE,
    CompanionMode.INVESTIGATING: MascotMood.FOCUSED,
    CompanionMode.ALERT: MascotMood.CALM_ALERT,
    CompanionMode.SCRIBE: MascotMood.WRITING,
    CompanionMode.DISABLED: MascotMood.OFF,
}
_MONITORING_SOURCES = frozenset(
    {CompanionSource.USER_SELECTED_LOOPBACK, CompanionSource.USER_SELECTED_MICROPHONE}
)


class CompanionService:
    """Stateful, process-local companion engine. One instance per FastAPI app."""

    def __init__(
        self,
        master: MasterData,
        repo: CaseRepository,
        cfg: PolicyConfig = DEFAULT_CONFIG,
        bus: CompanionBus | None = None,
    ) -> None:
        self._master = master
        self._repo = repo
        self._cfg = cfg
        self.bus = bus or CompanionBus()
        self._lock = threading.RLock()
        self._state = CompanionStateSnapshot()
        self._audit: deque[AuditRow] = deque(maxlen=AUDIT_CAPACITY)
        self._drafts: dict[str, dict[DraftKind, DraftArtifact]] = {}
        self._last_case_id: str | None = None
        # F03 live-call state (one call at a time)
        self._call_id: str | None = None
        self._call_case_id: str | None = None
        self._chips: dict[str, float] = {}
        self._quotes: dict[str, AskQuote] = {}
        self._coverage: Coverage = Coverage.USABLE
        self._seal: SealStatus = SealStatus.NOT_VERIFIED
        self._live_attached = False

    # ---------------------------------------------------------------- read helpers
    def snapshot(self) -> CompanionStateSnapshot:
        with self._lock:
            return self._state.model_copy(update={"last_event_id": self._last_event_id()})

    def _last_event_id(self) -> str | None:
        history = self.bus.history()
        return history[-1].event_id if history else None

    def audit(self) -> list[AuditRow]:
        with self._lock:
            return list(self._audit)

    def list_cases(self) -> list[CaseSummary]:
        out: list[CaseSummary] = []
        for case in self._repo.all_cases():
            decision = case.decision or decide(case, self._master, self._cfg)
            out.append(
                CaseSummary(
                    case_id=case.id,
                    title=case.title,
                    status=case.status,
                    band=decision.band,
                    queue=decision.queue,
                )
            )
        return out

    # ---------------------------------------------------------------- consent lifecycle
    def start_session(
        self, request: SessionStartRequest, actor: str = "emp_priya"
    ) -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        if request.consent is not True:
            raise ConsentRequiredError("explicit consent is required before any monitoring")
        with self._lock:
            # A fresh session never inherits a prior call's fan-in state.
            self._call_id = None
            self._call_case_id = None
            self._chips = {}
            now = utcnow()
            source = request.source
            demo = source == CompanionSource.DEMO_REPLAY
            label = request.label or _source_label(source)
            self._state = CompanionStateSnapshot(
                mode=CompanionMode.ACTIVE,
                hidden=False,
                monitoring=source in _MONITORING_SOURCES,
                session_id=f"session_{uuid.uuid4().hex[:12]}",
                consent_id=f"consent_{uuid.uuid4().hex[:12]}",
                source=source,
                source_label=label,
                started_at=now,
                updated_at=now,
                expires_at=now + SESSION_TTL,
                demo=demo,
                mode_label=DEMO_LABEL if demo else "LIVE — CONSENTED SOURCE",
            )
            self._record(
                "session.start",
                actor,
                f"source={source.value} monitoring={self._state.monitoring} consent=explicit",
            )
            event = self._publish(
                CompanionEventType.SESSION_STARTED,
                state=CompanionMode.ACTIVE,
                headline=_start_headline(source),
                explanation=(
                    "Satya processes only the source you selected. Audio stays in a short "
                    "in-memory buffer unless you explicitly preserve evidence."
                ),
                monitoring=self._state.monitoring,
                source=source,
                demo=demo,
                mode_label=self._state.mode_label,
            )
            return self.snapshot(), [event]

    def stop_session(
        self, actor: str = "emp_priya", reason: str = "user"
    ) -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        with self._lock:
            was_active = self._state.session_id is not None
            self._clear_session()
            if not was_active and self._state.mode == CompanionMode.SLEEP:
                return self.snapshot(), []
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.SLEEP, "updated_at": utcnow()}
            )
            self._record("session.stop", actor, f"reason={reason} monitoring=off")
            event = self._publish(
                CompanionEventType.SESSION_STOPPED,
                state=CompanionMode.SLEEP,
                headline="Sleep / DND — monitoring is off",
                explanation="Capture has been released. Satya is not watching anything.",
                monitoring=False,
                mode_label=None,
            )
            return self.snapshot(), [event]

    def sleep(
        self, actor: str = "emp_priya"
    ) -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        return self.stop_session(actor=actor, reason="sleep")

    def hide(self, actor: str = "emp_priya") -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        """Hide the window AND stop capture: hiding must never leave monitoring invisible."""
        with self._lock:
            self._clear_session()
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.SLEEP, "hidden": True, "updated_at": utcnow()}
            )
            self._record("ui.hide", actor, "capture released; monitoring=off")
            event = self._publish(
                CompanionEventType.STATE_CHANGED,
                state=CompanionMode.SLEEP,
                headline="Companion hidden — monitoring is off",
                explanation="Use the tray or the global shortcut to bring Satya back.",
                monitoring=False,
            )
            return self.snapshot(), [event]

    def show(self, actor: str = "emp_priya") -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        with self._lock:
            self._state = self._state.model_copy(update={"hidden": False, "updated_at": utcnow()})
            self._record("ui.show", actor, "window shown")
            mode = self._state.mode
            event = self._publish(
                CompanionEventType.STATE_CHANGED,
                state=mode,
                headline=(
                    "Satya is back" if mode != CompanionMode.DISABLED else "Companion disabled"
                ),
                explanation=(
                    "Still in Sleep / DND. Nothing is being watched until you choose a source."
                    if mode == CompanionMode.SLEEP
                    else ""
                ),
                monitoring=False,
            )
            return self.snapshot(), [event]

    def disable(
        self, actor: str = "emp_priya"
    ) -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        with self._lock:
            self._clear_session()
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.DISABLED, "hidden": True, "updated_at": utcnow()}
            )
            self._record("ui.disable", actor, "session resources released")
            event = self._publish(
                CompanionEventType.STATE_CHANGED,
                state=CompanionMode.DISABLED,
                headline="Companion disabled",
                explanation="All capture and session resources have been released.",
                monitoring=False,
            )
            return self.snapshot(), [event]

    def command(
        self, request: CommandRequest, actor: str = "emp_priya"
    ) -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        match request.type:
            case CommandType.SESSION_SLEEP | CommandType.SESSION_STOP:
                return self.stop_session(actor=actor, reason=request.type.value)
            case CommandType.UI_HIDE:
                return self.hide(actor=actor)
            case CommandType.UI_SHOW:
                return self.show(actor=actor)
            case CommandType.UI_DISABLE:
                return self.disable(actor=actor)
            case CommandType.DEMO_REPLAY:
                scenario = str(request.payload.get("scenario", "beneficiary_change"))
                return self.run_scenario(scenario, actor=actor)
        raise CompanionError(f"unsupported command: {request.type}")

    # ---------------------------------------------------------------- demo replay
    def run_scenario(
        self, scenario_key: str, actor: str = "emp_priya"
    ) -> tuple[CompanionStateSnapshot, list[CompanionEvent]]:
        scenario = DEMO_SCENARIOS.get(scenario_key)
        if scenario is None:
            raise CompanionError(f"unknown demo scenario: {scenario_key}")
        with self._lock:
            if self._state.source != CompanionSource.DEMO_REPLAY or not self._state.demo:
                # A replay is not live capture. The user's explicit action is the consent for
                # replay only; monitoring stays false and the label is always visible.
                now = utcnow()
                self._state = CompanionStateSnapshot(
                    mode=CompanionMode.ACTIVE,
                    hidden=False,
                    monitoring=False,
                    session_id=f"session_{uuid.uuid4().hex[:12]}",
                    consent_id=f"consent_{uuid.uuid4().hex[:12]}",
                    source=CompanionSource.DEMO_REPLAY,
                    source_label="Local replay fixture",
                    started_at=now,
                    updated_at=now,
                    expires_at=now + SESSION_TTL,
                    demo=True,
                    mode_label=DEMO_LABEL,
                )
                self._record("session.start", actor, "source=demo_replay monitoring=false")

            started = self._publish(
                CompanionEventType.ANALYSIS_STARTED,
                state=CompanionMode.INVESTIGATING,
                headline="Reviewing the replay fixture",
                explanation=(
                    "DEMO REPLAY — NOT LIVE CAPTURE. Only generated demo data is processed."
                ),
                monitoring=False,
                source=CompanionSource.DEMO_REPLAY,
                demo=True,
                mode_label=DEMO_LABEL,
            )
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.INVESTIGATING, "updated_at": utcnow()}
            )

            case = self.build_demo_case(scenario, actor=actor)
            self._repo.put(case)
            stored = self._repo.get(case.id) or case
            decision = stored.decision or decide(stored, self._master, self._cfg)
            self._last_case_id = stored.id

            self._state = self._state.model_copy(
                update={"mode": CompanionMode.ALERT, "updated_at": utcnow()}
            )
            explanation = explain_template(decision, Lang.EN).text
            alert = self._publish(
                CompanionEventType.ALERT_RAISED,
                state=CompanionMode.ALERT,
                headline=_alert_headline(decision.band),
                explanation=(
                    "This evidence does not establish who is speaking or acting. "
                    f"The band below comes only from the policy engine.\n\n{explanation}"
                )[:2000],
                band=decision.band,
                reason_codes=list(decision.reason_codes),
                info_codes=list(decision.info_codes),
                evidence_ids=[ev.id for ev in stored.evidence],
                demo=True,
                monitoring=False,
                source=CompanionSource.DEMO_REPLAY,
                mode_label=DEMO_LABEL,
            )
            self._record("demo.replay", actor, f"scenario={scenario.key} case={stored.id}")
            return self.snapshot(), [started, alert]

    def build_demo_case(self, scenario: DemoScenario, actor: str = "emp_priya") -> Case:
        """Build a fake case and extract asks deterministically. The band is decided later."""
        now = utcnow()
        case_id = f"case_demo_{scenario.key}"
        evidence_id = f"ev_demo_{scenario.key}"
        asks = extract_asks(scenario.text)
        signals = [
            Signal.make(
                ASK_TO_REASON[span.ask_type],
                source=SignalSource.DETERMINISTIC,
                evidence_ids=[evidence_id],
                detector="asks.extractor",
                detail={"lexicon_id": span.lexicon_id},
            )
            for span in asks
        ]

        if scenario.key == "cfo_call":
            signals.append(
                Signal.make(
                    ReasonCode.VOICE_LIKELY_SYNTHETIC,
                    source=SignalSource.ML,
                    evidence_ids=[evidence_id],
                    detector="voice_xlsr_l7@v1.0",
                    score=0.94,
                    detail={"windows": 6, "consecutive_over_hi": 4, "synthetic_probability": 0.94},
                )
            )
            signals.append(
                Signal.make(
                    ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC,
                    source=SignalSource.DETERMINISTIC,
                    evidence_ids=[evidence_id],
                    detector="satyapan.seal.voiceseal",
                    detail={"claimed_exec": "emp_rajesh_cfo", "seal_detected": False},
                )
            )
            channel = Channel.CALL_AUDIO
            filename = "cfo_deepfake_call.wav"
            media_type = "audio/wav"
        else:
            channel = Channel.WHATSAPP_TEXT
            filename = f"{scenario.key}.txt"
            media_type = "text/plain"

        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            channel=channel,
            filename=filename,
            media_type=media_type,
            sha256=hashlib.sha256(scenario.text.encode("utf-8")).hexdigest(),
            size_bytes=len(scenario.text.encode("utf-8")),
            captured_at=now,
            submitted_by=actor,
            storage_uri=f"demo://replay/{scenario.key}",
            excerpt=scenario.text[:300],
        )
        txn = PaymentAction(
            id=f"txn_demo_{scenario.key}",
            vendor_id=None,
            beneficiary_name=scenario.payee,
            account_number=scenario.account_number,
            ifsc=scenario.ifsc,
            amount_inr=scenario.amount_inr,
            rail=PaymentRail.NEFT,
            debit_account_masked="••••0000",
            requested_by_employee_id=None,
            created_by=actor,
            created_at=now,
        )
        return Case(
            id=case_id,
            title=scenario.title,
            kind=CaseKind.PAYMENT,
            created_at=now,
            created_by=actor,
            txn=txn,
            evidence=[evidence],
            signals=signals,
            notes=["DEMO REPLAY — generated fixture; all names and bank details are fake."],
        )

    # ---------------------------------------------------------------- live calls (F03)
    def start_call(
        self, request: CallStartRequest, state: AppState, actor: str = "emp_priya"
    ) -> tuple[str, str, list[CompanionEvent]]:
        """Start one listened call on an already-consented session. Never starts capture itself."""
        with self._lock:
            self._require_consented(request.consent_id)
            live = state.live()
            if self._call_id is not None:
                # A new, explicitly consented start supersedes a call that was never stopped
                # (crashed client, closed laptop lid). Its buffers are released first.
                live.stop_video(self._call_id)
                live.sessions.pop(self._call_id, None)
                self._record("call.superseded", actor, f"call={self._call_id} released")
                self._call_id = None
            attach_live_bus(live, self._ingest_live_event)
            call_id = f"call_{uuid.uuid4().hex[:10]}"
            maker = request.maker or actor
            session = live.start(call_id, maker)
            session.language = request.language
            title = f"Call on {request.app}" if request.app else "Live call"
            if request.source == CaptureSourceKind.REPLAY:
                title = "Demo call (replay)"
            session.case = session.case.model_copy(update={"title": title})
            state.repo.put(session.case)
            self._call_id = call_id
            self._call_case_id = session.case.id
            self._chips = {}
            self._quotes = {}
            self._coverage = Coverage.USABLE
            self._seal = SealStatus.NOT_VERIFIED
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.ACTIVE, "monitoring": True, "updated_at": utcnow()}
            )
            replay = request.source == CaptureSourceKind.REPLAY
            event = self._publish(
                CompanionEventType.CALL_STARTED,
                # A replayed recording is always labelled DEMO REPLAY — NOT LIVE CAPTURE.
                demo=replay,
                source=CompanionSource.DEMO_REPLAY if replay else None,
                mode_label=DEMO_LABEL if replay else None,
                state=CompanionMode.ACTIVE,
                headline="Listening to this call.",
                explanation=(
                    "Only this call, only on this laptop. Captions stay in memory and are "
                    "dropped when the call ends unless you keep them as evidence."
                ),
                call_id=call_id,
                case_id=session.case.id,
                coverage=self._coverage,
                seal=self._seal,
                monitoring=True,
            )
            self._record(
                "call.start",
                actor,
                f"call={call_id} case={session.case.id} "
                f"source={request.source.value} consent=explicit",
            )
            return call_id, session.case.id, [event]

    def stop_call(
        self,
        state: AppState,
        call_id: str | None = None,
        actor: str = "emp_priya",
    ) -> tuple[str, CompanionStateSnapshot, list[CompanionEvent]]:
        with self._lock:
            active = self._call_id
            if active is None:
                raise CompanionError("no call is being listened to")
            target = call_id or active
            if target != active:
                raise CompanionError("that is not the active call")
            state.live().stop_video(target)
            state.live().sessions.pop(target, None)
            self._call_id = None
            self._call_case_id = None
            self._chips = {}
            self._quotes = {}
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.ACTIVE, "monitoring": False, "updated_at": utcnow()}
            )
            event = self._publish(
                CompanionEventType.CALL_STOPPED,
                state=CompanionMode.ACTIVE,
                headline="Stopped listening to this call.",
                explanation="The call session and its in-memory audio buffer are released.",
                call_id=target,
                monitoring=False,
            )
            self._record("call.stop", actor, f"call={target} monitoring=off")
            return target, self.snapshot(), [event]

    def _ingest_live_event(self, call_id: str, event: LiveEvent) -> None:
        """Called synchronously by `CompanionLiveBus.publish`. No scores, no transcript text."""
        with self._lock:
            if call_id != self._call_id:
                return
            if isinstance(event, TranscriptEvent):
                # Captions never cross into the companion bus (it keeps a replayable history).
                # The desktop reads them from the per-call live stream, in memory only.
                return
            if isinstance(event, StatusEvent):
                self._publish(
                    CompanionEventType.CALL_STATUS,
                    state=self._state.mode,
                    headline=(event.message or "Call status")[:140],
                    explanation=event.message[:2000],
                    status_code=(event.code or "status")[:40],
                    call_id=call_id,
                    case_id=self._call_case_id,
                    monitoring=True,
                    next_actions=[],
                )
                self._record("call.status", "system", f"call={call_id} code={event.code}")
                return
            if isinstance(event, AskEvent):
                code = event.ask_type.value
                at_s = (
                    event.t_s
                    if event.t_s is not None
                    else float(event.chunk_index) * LIVE_CHUNK_SECONDS
                )
                if code not in self._chips:
                    self._chips[code] = at_s
                    self._quotes[code] = AskQuote(
                        code=code,  # type: ignore[arg-type]
                        text=event.span_text[:200],
                        at_s=at_s,
                    )
                chips = self._chips_list()
                self._state = self._state.model_copy(
                    update={"mode": CompanionMode.ACTIVE, "updated_at": utcnow()}
                )
                self._publish(
                    CompanionEventType.LIVE_CHIPS,
                    state=CompanionMode.ACTIVE,
                    headline=f"{len(chips)} payment trick word(s) heard so far",
                    explanation=(
                        "These are detected requests, not a band. Only the policy engine decides "
                        "the band. Missing a word does not make the call safe."
                    ),
                    chips=chips,
                    coverage=self._coverage,
                    seal=self._seal,
                    call_id=call_id,
                    case_id=self._call_case_id,
                    monitoring=True,
                    quotes=self._quotes_list(),
                )
                self._record(
                    "call.chips",
                    "system",
                    f"call={call_id} codes={','.join(self._chips)}",
                )
            elif isinstance(event, VoiceEvent):
                coverage = _coverage_for(event.label)
                if coverage == self._coverage:
                    return
                self._coverage = coverage
                self._publish(
                    CompanionEventType.COVERAGE_CHANGED,
                    state=self._state.mode,
                    headline=(
                        "Audio is clear enough to keep listening."
                        if coverage == Coverage.USABLE
                        else "Audio is unclear — I won't judge the voice."
                    ),
                    explanation=(
                        "Coverage is about audio quality only. It never raises a band and poor "
                        "audio never creates an alert by itself."
                    ),
                    chips=self._chips_list(),
                    coverage=coverage,
                    seal=self._seal,
                    call_id=call_id,
                    case_id=self._call_case_id,
                    monitoring=True,
                )
            elif isinstance(event, BandEvent):
                # Relay the policy engine's decision. The companion never edits this band.
                if band_rank(event.band) < band_rank(Band.VERIFY):
                    return
                self._state = self._state.model_copy(
                    update={"mode": CompanionMode.ALERT, "updated_at": utcnow()}
                )
                self._publish(
                    CompanionEventType.ALERT_RAISED,
                    state=CompanionMode.ALERT,
                    headline=_alert_headline(event.band),
                    explanation=self._band_explanation(event),
                    band=event.band,
                    reason_codes=list(event.reason_codes),
                    chips=self._chips_list(),
                    call_id=call_id,
                    case_id=self._call_case_id,
                    monitoring=True,
                    next_actions=list(_ALERT_ACTIONS),
                    quotes=self._quotes_list(),
                    approver_name=self._approver_name_for(self._call_case_id),
                )
                self._record(
                    "call.alert", "system", f"call={call_id} band={event.band.value} relayed"
                )

    def _quotes_list(self) -> list[AskQuote]:
        return sorted(self._quotes.values(), key=lambda q: (q.at_s or 0.0, q.code))[:7]

    def _chips_list(self) -> list[AskChip]:
        ordered = sorted(self._chips.items(), key=lambda item: (item[1], item[0]))
        return [AskChip(code=code, at_s=at_s) for code, at_s in ordered]

    def _band_explanation(self, event: BandEvent) -> str:
        lines = [_reason_line(code) for code in event.reason_codes]
        intro = "This does not prove who is speaking. The band comes only from the policy engine."
        return "\n\n".join([intro, *lines])[:2000]

    # ---------------------------------------------------------------- files (F03)
    def submit_file(
        self,
        state: AppState,
        *,
        filename: str | None,
        media_type: str,
        data: bytes,
        case_id: str | None,
        actor: str = "emp_priya",
    ) -> EvidenceSubmitResponse:
        """Vault intake -> detectors -> merge -> recompute. The band stays the policy's."""
        from satyapan.vault.intake import intake

        with self._lock:
            if self._state.session_id is None:
                raise ConsentRequiredError("start a consented session before handing Satya a file")
            case = self._repo.get(case_id) if case_id else None
            if case_id and case is None:
                raise CompanionNotFound(f"unknown case: {case_id}")
            if case is None:
                case = Case(
                    id=f"case_file_{uuid.uuid4().hex[:10]}",
                    title=f"File: {filename or 'untitled'}",
                    kind=CaseKind.DATA_REQUEST,
                    created_at=utcnow(),
                    created_by=actor,
                )
            channel = _channel_for(filename, media_type)
            excerpt = None
            if channel in (Channel.WHATSAPP_TEXT, Channel.MANUAL):
                excerpt = data.decode("utf-8", errors="replace")[:300]
            ev = intake(
                data,
                case_id=case.id,
                channel=channel,
                filename=filename,
                media_type=media_type or "application/octet-stream",
                submitted_by=actor,
                store=state.store(),
                log=state.custody,
                excerpt=excerpt,
            )
            case = case.model_copy(update={"evidence": [*case.evidence, ev]})
            ctx = PipelineContext(
                master=state.master,
                settings=state.settings,
                thresholds=state.thresholds,
                transcriber=state.transcriber(),
                live_phrasebook=True,
                video=state.video() if channel == Channel.VIDEO else None,
                text_model=state.text_model(),
                scorer=state.voice_scorer(),
                image=state.image_checker() if channel == Channel.IMAGE else None,
            )
            out = analyze_evidence(data, ev, case, ctx)
            case = recompute(merge_output(case, ev, out), state.master)
            state.repo.put(case, redecide=False)
            state.custody.append(
                case_id=case.id,
                evidence_id=ev.id,
                event=CustodyEvent.ANALYSIS,
                actor="system",
                payload={"detector": out.detector, "version": out.version, "error": out.error},
            )
            ask_codes = list(
                dict.fromkeys(s.code for s in out.signals if s.code in set(ASK_TO_REASON.values()))
            )
            event = self.note_case_updated(
                case,
                actor,
                headline=(
                    "Checked the file. The policy engine set the band."
                    if out.error is None
                    else "Checked what I could. The policy engine set the band."
                ),
            )
            self._record(
                "file.analyze",
                actor,
                f"case={case.id} evidence={ev.id} detector={out.detector} band_set=false",
            )
            return EvidenceSubmitResponse(
                request_id=f"req_file_{uuid.uuid4().hex[:10]}",
                accepted=True,
                evidence_id=ev.id,
                reason_codes=[],
                info_codes=ask_codes,
                ask_count=len(ask_codes),
                events=[event],
            )

    def note_case_updated(
        self, case: Case, actor: str, *, headline: str = "Case updated"
    ) -> CompanionEvent:
        """Relay the case's policy decision; never compute one here."""
        decision = case.decision or decide(case, self._master, self._cfg)
        self._last_case_id = case.id
        alerting = band_rank(decision.band) >= band_rank(Band.VERIFY)
        state = CompanionMode.ALERT if alerting else CompanionMode.ACTIVE
        self._state = self._state.model_copy(update={"mode": state, "updated_at": utcnow()})
        return self._publish(
            CompanionEventType.CASE_UPDATED,
            approver_name=self._approver_name_for(case.id) if alerting else None,
            state=state,
            headline=headline,
            explanation=explain_template(decision, Lang.EN).text,
            band=decision.band,
            reason_codes=list(decision.reason_codes),
            info_codes=list(decision.info_codes),
            evidence_ids=[ev.id for ev in case.evidence],
            case_id=case.id,
        )

    # ---------------------------------------------------------------- OOB (F03)
    def request_oob(self, state: AppState, case_id: str, actor: str = "emp_priya") -> OobTicket:
        """Challenge the transaction through the directory identity, never a message contact."""
        with self._lock:
            case = self._repo.get(case_id)
            if case is None:
                raise CompanionNotFound(f"unknown case: {case_id}")
            approver = self._resolve_approver(case)
            maker = self._master.employee(actor)
            oob_req, _token = state.oob().create(
                case, approver, maker.name if maker else "the maker", utcnow()
            )
            case = recompute(case.model_copy(update={"oob": oob_req}), self._master)
            state.repo.put(case, redecide=False)
            self._last_case_id = case.id
            channel = "email" if "ses" in set(oob_req.channels) else "console"
            ticket = OobTicket(
                oob_id=oob_req.id,
                case_id=case.id,
                approver_name=approver.name,
                channel=channel,
                inbox_url=f"/oob/inbox?oob_id={oob_req.id}",
                expires_at=oob_req.expires_at,
            )
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.ALERT, "updated_at": utcnow()}
            )
            self._publish(
                CompanionEventType.OOB_SENT,
                state=CompanionMode.ALERT,
                headline=f"Asked {approver.name} on their own phone.",
                explanation=(
                    "The approver and channel come only from the employee directory, never from "
                    "the call or the email. Silence is never approval."
                ),
                band=case.decision.band if case.decision else None,
                case_id=case.id,
                ticket=ticket,
                oob=OobSummary(oob_id=oob_req.id, approver_name=approver.name),
                next_actions=list(_ALERT_ACTIONS),
            )
            self._record(
                "oob.create",
                actor,
                f"case={case.id} oob={oob_req.id} "
                f"approver={approver.employee_id} channel={channel}",
            )
            return ticket

    def note_oob_result(
        self, case: Case, oob_req: object, reason: str | None = None
    ) -> list[CompanionEvent]:
        """Called by /oob/respond: emits `oob.result` then `case.updated`."""
        result = getattr(oob_req, "result", None)
        outcome = _oob_outcome(result, reason)
        if outcome is None:
            return []
        requester_id = getattr(oob_req, "requester_employee_id", None)
        employee = self._master.employee(requester_id)
        name = employee.name if employee else "the approver"
        approved = outcome == "approved"
        headline = {
            "approved": f"{name} confirmed this exact payment.",
            "rejected": f"{name} rejected this request. Keep the payment on hold.",
            "not_requested": f"{name} says they didn't ask for this. I've put it on hold.",
            "expired": f"No answer from {name} — that is not a yes. Keep it on hold.",
        }[outcome]
        decision = case.decision or decide(case, self._master, self._cfg)
        mode = CompanionMode.ACTIVE if approved else CompanionMode.ALERT
        self._state = self._state.model_copy(update={"mode": mode, "updated_at": utcnow()})
        summary = OobSummary(
            oob_id=str(getattr(oob_req, "id", "oob_unknown")),
            approver_name=name,
            outcome=outcome,  # type: ignore[arg-type]
        )
        first = self._publish(
            CompanionEventType.OOB_RESULT,
            state=mode,
            headline=headline,
            explanation=(
                "Approval only covers this exact request. Rejection, "
                "'I did not request this' and silence all leave the payment on hold."
            ),
            band=decision.band,
            reason_codes=list(decision.reason_codes),
            evidence_ids=[ev.id for ev in case.evidence],
            case_id=case.id,
            oob=summary,
        )
        second = self.note_case_updated(case, "system", headline="Case updated after OOB")
        return [first, second]

    def _approver_name_for(self, case_id: str | None) -> str | None:
        """Display name of who OOB-Confirm would ask for this case (directory only)."""
        case = self._repo.get(case_id) if case_id else None
        if case is None:
            return None
        try:
            return str(getattr(self._resolve_approver(case), "name", "")) or None
        except CompanionError:
            return None

    def _resolve_approver(self, case: Case) -> object:
        requester_id = case.oob.requester_employee_id if case.oob else None
        if requester_id is None and case.txn is not None:
            requester_id = case.txn.requested_by_employee_id
        employee = self._master.employee(requester_id)
        if employee is not None and employee.active:
            return employee
        senior = sorted(self._master.senior_approvers(), key=lambda e: e.employee_id)
        if senior:
            return senior[0]
        raise CompanionError("no approver in the employee directory for this case")

    # ---------------------------------------------------------------- text checks (finale)
    def check_text(self, text: str, *, app: str | None, source: str) -> ScreenFinding:
        """Screen Guard / clipboard: what payment tricks are visible in this text?

        Deterministic and read-only: the same context filter, frozen lexicon and live phrasebook
        as calls, plus a vendor-master comparison. Nothing is stored and no band is set; the
        user can hand the text to Satya as evidence, and then the policy engine decides.
        """
        from satyapan.asks.phrasebook import extract_cues, extract_live_asks
        from satyapan.context import strip_context

        cleaned = strip_context(text).cleaned
        quotes: dict[str, AskQuote] = {}
        for span in extract_live_asks(cleaned):
            code = span.ask_type.value
            if code not in quotes:
                quotes[code] = AskQuote(code=code, text=span.text[:200])  # type: ignore[arg-type]
        cues = list(dict.fromkeys(c.code for c in extract_cues(text)))

        accounts = _accounts_in(text)
        vendors: list[str] = []
        known: set[str] = set()
        for vendor in self._master.vendors.values():
            names = {vendor.legal_name.lower()}
            first = vendor.legal_name.split()[0]
            if len(first) >= 5:
                names.add(first.lower())
            lower = text.lower()
            if any(_word_in(name, lower) for name in names):
                vendors.append(vendor.legal_name)
            known.update(acct.account_number for acct in vendor.accounts)
        unknown = [a for a in accounts if a not in known]
        meeting = _meeting_in(text)
        suspicious = bool(quotes) or bool(vendors and unknown)
        finding = ScreenFinding(
            app=app,
            meeting=meeting,
            asks=sorted(quotes.values(), key=lambda q: q.code),
            cues=cues,
            accounts_masked=[_mask(a) for a in accounts][:6],
            unknown_accounts_masked=[_mask(a) for a in unknown][:6],
            vendors=vendors[:6],
            suspicious=suspicious,
        )
        if suspicious:
            with self._lock:
                self._record(
                    f"{source}.finding",
                    "system",
                    f"asks={','.join(quotes) or '-'} vendors={len(vendors)} "
                    f"unknown_accounts={len(unknown)} text_stored=false",
                )
        return finding

    # ---------------------------------------------------------------- report pack (F03)
    def report_pack(
        self,
        case_id: str,
        *,
        utr: str | None = None,
        money_left_at: datetime | None = None,
    ) -> ReportPackV2:
        """Golden-hour pack: five drafts, all MANUAL_ONLY. Nothing is ever filed.

        `utr` / `money_left_at` are maker-entered at report time (the payment already left), so
        the 1930 script can start with the UTR. They only fill text; they never touch a band."""
        case = self._repo.get(case_id)
        if case is None:
            raise CompanionNotFound(f"unknown case: {case_id}")
        txn = case.txn
        utr = utr or (txn.utr if txn and txn.utr else None) or "Not provided — ask the maker"
        amount = _format_inr(txn.amount_inr) if txn else "Not provided"
        payee = txn.beneficiary_masked if txn else "Not provided"
        evidence = [f"{ev.id} · SHA-256 {ev.sha256}" for ev in case.evidence] or [
            "No evidence attached yet"
        ]
        channels = sorted({ev.channel.value for ev in case.evidence}) or ["not recorded"]

        def rfield(
            label: str,
            value: str,
            source: str,
            *,
            evidence_id: str | None = None,
            copy: bool = True,
            sensitive: bool = False,
        ) -> ReportField:
            return ReportField(
                label=label,
                value=value,
                source=source,  # type: ignore[arg-type]
                evidence_id=evidence_id,
                copy=copy,
                sensitive=sensitive,
            )

        sections = [
            ReportSection(
                id="helpline_1930",
                title="1930 helpline — call script",
                destination="1930 (national cyber-fraud helpline)",
                deadline_hint="Golden hour — call now",
                body=(
                    f"UTR {utr}. I want to report a suspected deepfake payment fraud. "
                    f"Amount {amount}. Beneficiary {payee}. Case {case.id}. "
                    "The request came on a call and was not verified independently."
                ),
                fields=[
                    rfield("UTR", utr, "maker_entered"),
                    rfield("Amount", amount, "maker_entered"),
                    rfield("Beneficiary (masked)", payee, "vendor_master", sensitive=True),
                    rfield("Case", case.id, "system"),
                ],
                open_url="tel:1930",
                applies=True,
                status="DRAFT_REQUIRES_HUMAN_REVIEW",
            ),
            ReportSection(
                id="bank_fraud_desk",
                title="Bank fraud desk — email draft",
                destination="Your bank's fraud desk (address from the bank's own website)",
                deadline_hint="Same day",
                body=(
                    f"Request: please hold or recall {amount} sent to {payee}. UTR: {utr}. "
                    "This payment followed a suspected impersonation call. Evidence files are "
                    f"listed with their SHA-256 hashes below. Case {case.id}."
                ),
                fields=[
                    rfield("UTR", utr, "maker_entered"),
                    rfield("Amount", amount, "maker_entered"),
                    rfield("Beneficiary (masked)", payee, "vendor_master", sensitive=True),
                    rfield("Evidence", "; ".join(evidence), "vault"),
                ],
                open_url="mailto:frauddesk@bank.example",
                applies=True,
                status="DRAFT_REQUIRES_HUMAN_REVIEW",
            ),
            ReportSection(
                id="ncrp_portal",
                title="NCRP portal — field helper",
                destination="cybercrime.gov.in (the human logs in with their own OTP)",
                deadline_hint="As soon as possible",
                body=(
                    "Copy each field in the portal's own order. Satya never logs in, never fills "
                    "the form and never clicks Submit."
                ),
                fields=[
                    rfield("Category", "Online Financial Fraud / impersonation", "system"),
                    rfield("Amount lost", amount, "maker_entered"),
                    rfield("Platform/channel", ", ".join(channels), "vault"),
                    rfield("UTR", utr, "maker_entered"),
                    rfield("Case", case.id, "system"),
                ],
                open_url="https://cybercrime.gov.in",
                applies=True,
                status="DRAFT_REQUIRES_HUMAN_REVIEW",
            ),
            ReportSection(
                id="cert_in",
                title="CERT-In — incident email",
                destination="incident@cert-in.org.in (confirm applicability with IT/legal)",
                deadline_hint="6 hours if applicable",
                body=(
                    "Body-corporate incident notification draft. Whether this incident qualifies "
                    "is a legal call — check with IT/legal before sending."
                ),
                fields=[
                    rfield(
                        "Incident type",
                        "Identity theft / impersonation (suspected)",
                        "user_confirmed",
                    ),
                    rfield("Case", case.id, "system"),
                ],
                open_url="mailto:incident@cert-in.org.in",
                applies=False,
                status="DRAFT_REQUIRES_HUMAN_REVIEW",
            ),
            ReportSection(
                id="bsa_s63_part_a",
                title="BSA 2023 §63 — Part A draft",
                destination="PDF export; a human signs. Part B needs an expert.",
                deadline_hint=None,
                body=(
                    "Part A lists the SHA-256 hash of each retained evidence file, device "
                    "particulars and the lawful-control statement. Draft only."
                ),
                fields=[
                    *[
                        rfield(
                            f"SHA-256 · {ev.id}",
                            ev.sha256,
                            "vault",
                            evidence_id=ev.id,
                            sensitive=False,
                        )
                        for ev in case.evidence
                    ],
                    rfield("Signatory", "A human must sign — Satya cannot", "system", copy=False),
                ],
                open_url=None,
                applies=True,
                status="DRAFT_REQUIRES_HUMAN_REVIEW",
            ),
        ]
        return ReportPackV2(
            case_id=case.id,
            generated_at=utcnow(),
            money_left_at=money_left_at or (txn.created_at if txn else None),
            sections=sections,
            submission=MANUAL_ONLY,  # type: ignore[arg-type]
            auto_submit=False,
        )

    # ---------------------------------------------------------------- evidence intake
    def submit_evidence(
        self, request: EvidenceSubmitRequest, actor: str = "emp_priya"
    ) -> EvidenceSubmitResponse:
        if request.consent is not True:
            raise ConsentRequiredError("explicit consent is required for evidence intake")
        with self._lock:
            self._require_active_session(request.session_id)
            spans = extract_asks(request.text)
            codes = [ASK_TO_REASON[s.ask_type] for s in spans]
            unique_codes = list(dict.fromkeys(codes))
            started = self._publish(
                CompanionEventType.ANALYSIS_STARTED,
                state=CompanionMode.INVESTIGATING,
                headline="Checking the submitted text",
                explanation="Only the text you submitted is processed. No screen or audio capture.",
                monitoring=False,
                source=request.source,
                mode_label=self._state.mode_label,
            )
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.INVESTIGATING, "updated_at": utcnow()}
            )
            received = self._publish(
                CompanionEventType.EVIDENCE_RECEIVED,
                state=CompanionMode.INVESTIGATING,
                headline=(
                    f"{len(spans)} request pattern(s) found"
                    if spans
                    else "No request pattern found in this text"
                ),
                explanation=(
                    "These are detected requests, not a policy band. Enter the pending payment "
                    "in Satyapan so the policy engine can decide a band. Absence of a pattern "
                    "does not make the message safe."
                ),
                info_codes=unique_codes,
                evidence_ids=[request.evidence_id],
                source=request.source,
                mode_label=self._state.mode_label,
            )
            self._state = self._state.model_copy(
                update={"mode": CompanionMode.ACTIVE, "updated_at": utcnow()}
            )
            done = self._publish(
                CompanionEventType.ANALYSIS_COMPLETED,
                state=CompanionMode.ACTIVE,
                headline="Check complete — policy band unchanged",
                explanation="The companion cannot set or lower a band.",
                monitoring=self._state.monitoring,
                source=request.source,
                mode_label=self._state.mode_label,
            )
            self._record(
                "evidence.submit",
                actor,
                f"evidence={request.evidence_id} source={request.source.value} "
                f"asks={len(spans)} band_set=false",
            )
            return EvidenceSubmitResponse(
                request_id=request.request_id,
                accepted=True,
                evidence_id=request.evidence_id,
                info_codes=unique_codes,
                ask_count=len(spans),
                events=[started, received, done],
            )

    # ---------------------------------------------------------------- drafts
    def draft(self, kind: DraftKind, case_id: str, actor: str = "emp_priya") -> DraftArtifact:
        with self._lock:
            case = self._repo.get(case_id)
            if case is None:
                raise CompanionNotFound(f"unknown case: {case_id}")
            decision = case.decision or decide(case, self._master, self._cfg)
            # Scribe pauses new capture by default; the user can explicitly resume later.
            self._clear_session()
            self._state = self._state.model_copy(
                update={
                    "mode": CompanionMode.SCRIBE,
                    "monitoring": False,
                    "updated_at": utcnow(),
                }
            )
            if kind == DraftKind.SECTION_63:
                fields: dict[str, str | int | bool | None] = {
                    "case_title": case.title,
                    "record_description": "USER_CONFIRMED_DESCRIPTION_REQUIRED",
                    "production_method": "CAPTURE_METHOD_AND_TRANSFORMS_REQUIRED",
                    "device_particulars": "Local demo workstation (not a certified device)",
                    "hash_profile": "SHA-256, canonical JSON manifest (demo)",
                    "evidence_count": len(case.evidence),
                    "prescribed_form_version": "COUNSEL_VERIFIED_VERSION_REQUIRED",
                    "certificate_status": "DRAFT_REQUIRES_COUNSEL_AND_SIGNATORY_REVIEW",
                    "signatory": None,
                    "reason_codes": ",".join(c.value for c in decision.reason_codes),
                }
                disclaimers = [
                    "Draft only. A qualified person must review the Section 63 form, "
                    "statements and signatory before any use.",
                    "A local hash chain shows retained bytes did not change; it does not prove "
                    "who spoke or that the recording is complete.",
                ]
            else:
                txn = case.txn
                fields = {
                    "submission": MANUAL_ONLY,
                    "review_status": "DRAFT_REQUIRES_HUMAN_REVIEW",
                    "utr": txn.utr if txn else None,
                    "utr_missing": not bool(txn and txn.utr),
                    "amount_inr": txn.amount_inr if txn else None,
                    "payee_masked": txn.beneficiary_masked if txn else None,
                    "loss_amount_inr": None,
                    "pronunciation_helper": "1930 → one nine three zero",
                    "note": "Do not invent a UTR, loss amount or caller identity.",
                }
                disclaimers = [
                    "MANUAL_ONLY: no code path dials, transmits or files this draft.",
                    "The operator must confirm every field with the real record and then "
                    "submit through the official process.",
                ]
            draft = DraftArtifact(
                draft_id=f"draft_{kind.value}_{uuid.uuid4().hex[:10]}",
                kind=kind,
                case_id=case.id,
                fields=fields,
                disclaimers=disclaimers,
            )
            self._drafts.setdefault(case.id, {})[kind] = draft
            self._publish(
                CompanionEventType.DRAFT_READY,
                state=CompanionMode.SCRIBE,
                headline="Draft ready — human review required",
                explanation="Capture is paused while you review this editable draft.",
                band=decision.band,
                reason_codes=list(decision.reason_codes),
                evidence_ids=[ev.id for ev in case.evidence],
                monitoring=False,
                mode_label=MANUAL_ONLY,
            )
            self._record("draft.create", actor, f"kind={kind.value} case={case.id} manual_only")
            return draft

    # ---------------------------------------------------------------- workspace
    def workspace(self, case_id: str | None = None) -> WorkspaceSnapshot:
        case: Case | None
        if case_id:
            case = self._repo.get(case_id)
        else:
            case = self._repo.get(self._last_case_id) if self._last_case_id else None
            if case is None:
                all_cases = self._repo.all_cases()
                case = all_cases[0] if all_cases else None
        if case is None:
            raise CompanionNotFound(f"unknown case: {case_id}")
        decision = case.decision or decide(case, self._master, self._cfg)
        txn = case.txn
        refs = [
            EvidenceRef(
                evidence_id=ev.id,
                channel=ev.channel,
                filename=ev.filename,
                size_bytes=ev.size_bytes,
                sha256_short=ev.sha256[:12],
                excerpt=ev.excerpt,
            )
            for ev in case.evidence
        ]
        drafts = list(self._drafts.get(case.id, {}).values())
        return WorkspaceSnapshot(
            case_id=case.id,
            title=case.title,
            kind=case.kind.value,
            status=case.status,
            band=decision.band,
            floor_band=decision.floor_band,
            action_type=decision.action_type,
            queue=decision.queue,
            reason_codes=list(decision.reason_codes),
            info_codes=list(decision.info_codes),
            explanation=explain_template(decision, Lang.EN).text,
            payee_masked=txn.beneficiary_masked if txn else None,
            amount_inr=txn.amount_inr if txn else None,
            evidence=refs,
            drafts=drafts,
            audit=self.audit(),
            trace=PolicyTrace(
                floor_band=decision.floor_band,
                action_type=decision.action_type,
                signals=[
                    TraceSignal(
                        code=sig.code,
                        group=sig.group.value,
                        strength=sig.strength.value,
                        source=sig.source.value,
                        target=sig.target.value,
                        detector=sig.detector,
                        evidence_ids=list(sig.evidence_ids),
                    )
                    for sig in case.signals
                ],
                grey=decision.grey,
                clearance_methods=[m.value for m in decision.clearance.methods],
                clearance_who=[r.value for r in decision.clearance.who],
                clearance_notes=list(decision.clearance.notes),
                policy_version=decision.policy_version,
            ),
        )

    # ---------------------------------------------------------------- internals
    def _publish(
        self,
        event_type: CompanionEventType,
        *,
        state: CompanionMode,
        headline: str,
        explanation: str = "",
        band: Band | None = None,
        reason_codes: list[ReasonCode] | None = None,
        info_codes: list[ReasonCode] | None = None,
        evidence_ids: list[str] | None = None,
        monitoring: bool = False,
        source: CompanionSource | None = None,
        demo: bool = False,
        mode_label: str | None = None,
        case_id: str | None = None,
        call_id: str | None = None,
        chips: list[AskChip] | None = None,
        coverage: Coverage | None = None,
        seal: SealStatus | None = None,
        oob: OobSummary | None = None,
        ticket: OobTicket | None = None,
        report: ReportPackV2 | None = None,
        next_actions: list[NextAction] | None = None,
        quotes: list[AskQuote] | None = None,
        status_code: str | None = None,
        screen: ScreenFinding | None = None,
        approver_name: str | None = None,
    ) -> CompanionEvent:
        payload = CompanionPayload(
            state=state,
            mascot_mood=_MOOD_BY_MODE[state],
            headline=headline,
            explanation=explanation,
            band=band,
            reason_codes=reason_codes or [],
            info_codes=info_codes or [],
            evidence_ids=evidence_ids or [],
            next_actions=next_actions or list(_DEFAULT_ACTIONS),
            monitoring=monitoring,
            source=source or self._state.source,
            demo=demo,
            mode_label=mode_label if mode_label is not None else self._state.mode_label,
            case_id=case_id,
            call_id=call_id,
            chips=chips or [],
            coverage=coverage,
            seal=seal,
            oob=oob,
            ticket=ticket,
            report=report,
            quotes=quotes or [],
            status_code=status_code,
            screen=screen,
            approver_name=approver_name,
        )
        event = CompanionEvent(
            type=event_type,
            session_id=self._state.session_id,
            payload=payload,
        )
        return self.bus.publish(event)

    def _clear_session(self) -> None:
        self._call_id = None
        self._call_case_id = None
        self._chips = {}
        self._quotes = {}
        self._state = self._state.model_copy(
            update={
                "session_id": None,
                "consent_id": None,
                "monitoring": False,
                "source": None,
                "source_label": None,
                "started_at": None,
                "expires_at": None,
                "demo": False,
                "mode_label": None,
                "updated_at": utcnow(),
            }
        )

    def _require_consented(self, consent_id: str) -> None:
        if self._state.session_id is None or self._state.consent_id is None:
            raise ConsentRequiredError("start a consented session before listening to a call")
        if consent_id != self._state.consent_id:
            raise ConsentRequiredError("consent_id does not match the active consented session")

    def _require_active_session(self, session_id: str | None) -> None:
        if self._state.session_id is None:
            raise CompanionError("start a consented session before submitting evidence")
        if session_id is not None and session_id != self._state.session_id:
            raise CompanionError("session_id does not match the active consented session")

    def _record(self, action: str, actor: str, detail: str) -> None:
        self._audit.append(AuditRow(actor=actor, action=action, detail=detail))


_ACCOUNT_RE = re.compile(r"(?<![\d-])\d(?:[ -]?\d){8,17}(?![\d-])")
_ACCOUNT_KEY_RE = re.compile(r"(a/c|acct|account|acc\.?\s*no|beneficiary)", re.IGNORECASE)


def _accounts_in(text: str) -> list[str]:
    """Bank-account-looking numbers. 11+ digits anywhere; 9-10 digits only right after an
    account keyword (so phone numbers do not count)."""
    out: list[str] = []
    for m in _ACCOUNT_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group(0))
        if len(digits) < 9 or len(digits) > 18:
            continue
        if len(digits) < 11 and not _ACCOUNT_KEY_RE.search(
            text[max(0, m.start() - 40) : m.start()]
        ):
            continue
        if digits not in out:
            out.append(digits)
    return out


def _word_in(needle: str, haystack: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _mask(account: str) -> str:
    return f"••••{account[-4:]}"


def _meeting_in(text: str) -> str | None:
    lower = text.lower()
    if "meet.google.com" in lower or "google meet" in lower:
        return "Google Meet"
    if "teams.microsoft.com" in lower or "microsoft teams" in lower:
        return "Microsoft Teams"
    if "zoom.us" in lower or "zoom meeting" in lower:
        return "Zoom"
    return None


def _source_label(source: CompanionSource) -> str:
    return {
        CompanionSource.DEMO_REPLAY: "Local replay fixture",
        CompanionSource.USER_SELECTED_EMAIL: "Selected email/text",
        CompanionSource.USER_SELECTED_LOOPBACK: "Selected app audio (loopback)",
        CompanionSource.USER_SELECTED_MICROPHONE: "Microphone",
    }[source]


def _start_headline(source: CompanionSource) -> str:
    return {
        CompanionSource.DEMO_REPLAY: "Replay fixtures only — not live capture",
        CompanionSource.USER_SELECTED_EMAIL: "Ready for the email you select",
        CompanionSource.USER_SELECTED_LOOPBACK: "Watching the app audio you selected",
        CompanionSource.USER_SELECTED_MICROPHONE: "Microphone is on — you can stop anytime",
    }[source]


def _alert_headline(band: Band) -> str:
    """Plain-language, non-accusatory headline. Never names a speaker or a detector score."""
    if band == Band.HOLD:
        return "Pause this payment and verify independently"
    if band == Band.VERIFY:
        return "This request needs independent verification"
    return "No blocking finding — still verify with the saved contact"


def _format_inr(amount: int) -> str:
    """Indian digit grouping: 4850000 -> '₹48,50,000'."""
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = [tail]
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{sign}₹{','.join(groups)}"


def _channel_for(filename: str | None, media_type: str) -> Channel:
    from satyapan.filetypes import channel_for

    return channel_for(filename, media_type)
    return Channel.MANUAL


def _coverage_for(label: VoiceLabel) -> Coverage:
    """Audio quality only. A synthetic-sounding voice is a verdict, not poor coverage."""
    if label == VoiceLabel.INCONCLUSIVE:
        return Coverage.DEGRADED
    return Coverage.USABLE


def _oob_outcome(result: object, reason: str | None) -> str | None:
    value = getattr(result, "value", result)
    if value == "APPROVED":
        return "approved"
    if value == "EXPIRED":
        return "expired"
    if value == "DENIED":
        return "not_requested" if reason == "not_requested" else "rejected"
    return None


def _reason_line(code: ReasonCode) -> str:
    try:
        return reason_text(code, Lang.EN)
    except KeyError:  # a new code without a template must not break the live stream
        return code.value.replace("_", " ").capitalize()


# Re-exported for tests and the router.
__all__ = [
    "AUDIT_CAPACITY",
    "DEMO_LABEL",
    "DEMO_SCENARIOS",
    "CompanionError",
    "CompanionNotFound",
    "CompanionService",
    "ConsentRequiredError",
    "DemoScenario",
]
