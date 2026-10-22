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
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import timedelta

from satyapan.api.companion.bus import CompanionBus
from satyapan.api.companion.models import (
    MANUAL_ONLY,
    AuditRow,
    CaseSummary,
    CommandRequest,
    CommandType,
    CompanionEvent,
    CompanionEventType,
    CompanionMode,
    CompanionPayload,
    CompanionSource,
    CompanionStateSnapshot,
    DraftArtifact,
    DraftKind,
    EvidenceRef,
    EvidenceSubmitRequest,
    EvidenceSubmitResponse,
    MascotMood,
    NextAction,
    SessionStartRequest,
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
    Lang,
    PaymentRail,
    ReasonCode,
    SignalSource,
)
from satyapan.contracts.evidence import Evidence, Signal
from satyapan.contracts.transaction import PaymentAction
from satyapan.explain.templates import explain_template
from satyapan.master.store import MasterData
from satyapan.policy.config import DEFAULT_CONFIG, PolicyConfig
from satyapan.policy.engine import decide
from satyapan.repository import CaseRepository

SESSION_TTL = timedelta(hours=8)
AUDIT_CAPACITY = 200
DEMO_LABEL = "DEMO REPLAY — NOT LIVE CAPTURE"
_DEFAULT_ACTIONS = [
    NextAction(id="oob_verify", label="Verify using a saved contact", variant="primary"),
    NextAction(id="open_scribe", label="Prepare an incident draft", variant="outline"),
    NextAction(id="open_workspace", label="View details", variant="outline"),
]


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
        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            channel=Channel.WHATSAPP_TEXT,
            filename=f"{scenario.key}.txt",
            media_type="text/plain",
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
            next_actions=list(_DEFAULT_ACTIONS),
            monitoring=monitoring,
            source=source or self._state.source,
            demo=demo,
            mode_label=mode_label if mode_label is not None else self._state.mode_label,
        )
        event = CompanionEvent(
            type=event_type,
            session_id=self._state.session_id,
            payload=payload,
        )
        return self.bus.publish(event)

    def _clear_session(self) -> None:
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

    def _require_active_session(self, session_id: str | None) -> None:
        if self._state.session_id is None:
            raise CompanionError("start a consented session before submitting evidence")
        if session_id is not None and session_id != self._state.session_id:
            raise CompanionError("session_id does not match the active consented session")

    def _record(self, action: str, actor: str, detail: str) -> None:
        self._audit.append(AuditRow(actor=actor, action=action, detail=detail))


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
