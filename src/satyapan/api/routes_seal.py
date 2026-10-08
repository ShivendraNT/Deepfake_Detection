"""Satyapan Seal endpoints (C14): passkey enrolment, Voice Seal registry + upload verification,
Intent Seal. Design: docs/SEAL.md. The seal package is imported lazily so the core API still
starts without the `seal` extra (numpy/scipy/webauthn); then these routes answer 503.

  POST /passkeys/{employee_id}/register/options   WebAuthn creation options (self only)
  POST /passkeys/{employee_id}/register           verify + store the new passkey
  POST /seal/sessions                             passkey-signed SEAL-START -> session
  POST /seal/sessions/{session_id}/keys           disclose K_e after epoch e (TESLA checks)
  GET  /seal/meetings/{meeting}                   sessions + disclosed keys for receivers
  POST /seal/verify-upload                        voice note / recording -> verification
  POST /intent/challenge                          canonical intent from the case's txn
  POST /intent/verify                             passkey assertion over that intent
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from satyapan.api.auth import Actor, get_actor, get_state
from satyapan.api.routes_cases import _get_case
from satyapan.api.state import AppState
from satyapan.contracts.enums import CustodyEvent, Role, SealSessionKind
from satyapan.contracts.seal import PaymentIntent

router = APIRouter()


def _services(state: AppState) -> Any:
    try:
        return state.seal()
    except ImportError as e:  # pragma: no cover - only without the seal extra
        raise HTTPException(status_code=503, detail="seal extra not installed") from e


def _refuse(e: Exception, status: int = 409) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "reason": getattr(e, "reason", type(e).__name__),
            "detail": getattr(e, "detail", ""),
        },
    )


# ------------------------------------------------------------------ passkeys


class CredentialIn(BaseModel):
    credential: dict[str, Any]


@router.post("/passkeys/{employee_id}/register/options")
def passkey_options(
    employee_id: str, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    if actor.employee.employee_id != employee_id:
        raise HTTPException(status_code=403, detail="enrol your own passkey only")
    svc = _services(state)
    out: dict[str, Any] = svc.passkeys.registration_options(
        employee_id, actor.employee.name, svc.clock()
    )
    return out


@router.post("/passkeys/{employee_id}/register")
def passkey_register(
    employee_id: str,
    body: CredentialIn,
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    from satyapan.seal.passkey import PasskeyError
    from satyapan.seal.softauth import b64u

    if actor.employee.employee_id != employee_id:
        raise HTTPException(status_code=403, detail="enrol your own passkey only")
    svc = _services(state)
    try:
        cred = svc.passkeys.register(employee_id, body.credential, svc.clock())
    except PasskeyError as e:
        raise _refuse(e) from e
    return {"employee_id": employee_id, "enrolled": True, "credential_id": b64u(cred.credential_id)}


# ------------------------------------------------------------------ Voice Seal registry


class SessionIn(BaseModel):
    meeting: str = Field(description="Meet URL/code, or a voice-note id for kind=voice_note")
    kind: SealSessionKind = SealSessionKind.MEETING
    commitment: str = Field(description="lowercase hex of H(K_0)")
    t0_ms: int
    epoch_ms: int = 5000
    n_epochs: int
    params_id: str
    assertion: dict[str, Any]


@router.post("/seal/sessions")
def start_session(
    body: SessionIn, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    from satyapan.seal.registry import RegistryError

    svc = _services(state)
    try:
        s = svc.registry.start_session(
            employee_id=actor.employee.employee_id,
            kind=body.kind,
            meeting=body.meeting,
            commitment_hex=body.commitment,
            t0_ms=body.t0_ms,
            epoch_ms=body.epoch_ms,
            n_epochs=body.n_epochs,
            params_id=body.params_id,
            assertion=body.assertion,
            now=svc.clock(),
        )
    except RegistryError as e:
        raise _refuse(e) from e
    out: dict[str, Any] = s.model_dump(mode="json")
    return out


class KeyIn(BaseModel):
    epoch: int = Field(ge=0)
    key: str


@router.post("/seal/sessions/{session_id}/keys")
def disclose_key(
    session_id: str, body: KeyIn, state: AppState = Depends(get_state)
) -> dict[str, Any]:
    """No login needed: a key authenticates itself through the hash chain."""
    from satyapan.seal.registry import RegistryError

    svc = _services(state)
    try:
        s = svc.registry.disclose(session_id, body.epoch, body.key, svc.clock())
    except RegistryError as e:
        raise _refuse(e, 404 if e.reason == "unknown_session" else 409) from e
    out: dict[str, Any] = s.model_dump(mode="json")
    return out


@router.get("/seal/meetings/{meeting:path}")
def meeting_sessions(meeting: str, state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    svc = _services(state)
    try:
        views = svc.registry.meeting(meeting)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [v.model_dump(mode="json") for v in views]


@router.post("/seal/verify-upload")
async def verify_upload(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    claimed_employee_id: str | None = Form(default=None),
    first_epoch: int = Form(default=0, ge=0),
    max_offset_s: float = Form(default=30.0, ge=0, le=600),
    state: AppState = Depends(get_state),
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    """Check a voice note / recording against one session, or against the claimed executive's
    recent sessions (Bonferroni over the sessions tried). Makers get statuses, not raw z."""
    from satyapan.seal.registry import RegistryError
    from satyapan.seal.signals import voice_seal_signals
    from satyapan.seal.verify_upload import decode_audio, strip_scores, verify_samples
    from satyapan.seal.voiceseal import SealParams

    svc = _services(state)
    if session_id:
        try:
            sessions = [svc.registry.get(session_id)]
        except RegistryError as e:
            raise _refuse(e, 404) from e
    elif claimed_employee_id:
        from satyapan.seal.service import MAX_SESSIONS_TO_TRY

        sessions = sorted(
            svc.registry.sessions_for(claimed_employee_id), key=lambda s: s.started_at
        )[-MAX_SESSIONS_TO_TRY:]
    else:
        raise HTTPException(status_code=422, detail="give session_id or claimed_employee_id")
    data = await file.read()
    try:
        samples = await run_in_threadpool(decode_audio, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    def check_all() -> list[Any]:
        scale = 1.0 / max(1, len(sessions))
        return [
            verify_samples(
                samples,
                keys=svc.registry.keys(s.id),
                binding=s.binding,
                params=SealParams.from_id(s.params_id),
                first_epoch=first_epoch,
                max_offset_s=max_offset_s,
                session=s,
                alpha_scale=scale,
            )
            for s in sessions
        ]

    results = await run_in_threadpool(check_all) if sessions else []
    best = next((v for v in results if v.sealed), None) or max(
        results, key=lambda v: v.acquisition_statistic or -1e9, default=None
    )
    claimed = claimed_employee_id or (sessions[0].employee_id if session_id else None)
    signals = voice_seal_signals(
        results,
        claimed_employee_id=claimed,
        claimed_enrolled=bool(claimed) and svc.passkeys.enrolled(claimed),
        speech_seconds=best.speech_seconds if best else 0.0,
    )
    if best is not None and actor.role == Role.MAKER:
        best = strip_scores(best)
    return {
        "verification": best.model_dump(mode="json") if best else None,
        "sessions_checked": len(results),
        "signals": [s.model_dump(mode="json") for s in signals],
        "claimed_employee_id": claimed,
    }


# ------------------------------------------------------------------ Intent Seal


class IntentChallengeIn(BaseModel):
    case_id: str


@router.post("/intent/challenge")
def intent_challenge(
    body: IntentChallengeIn, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    """Build the canonical intent from the case's TRUSTED transaction (never from typed text)."""
    from satyapan.seal.intent import IntentError, make_intent
    from satyapan.seal.passkey import PasskeyError

    svc = _services(state)
    case = _get_case(state, body.case_id)
    txn = case.txn
    if txn is None or not txn.account_number or not txn.requested_by_employee_id:
        raise HTTPException(status_code=422, detail="case has no bank payment with a requester")
    action = f"PAY_{case.decision.action_type.value}" if case.decision else "PAY"
    intent = make_intent(
        case_id=case.id,
        requester=txn.requested_by_employee_id,
        amount_inr=txn.amount_inr,
        account_number=txn.account_number,
        ifsc=txn.ifsc,
        action=action,
        now=svc.clock(),
    )
    try:
        out: dict[str, Any] = svc.intents.issue(intent)
    except (IntentError, PasskeyError) as e:
        raise _refuse(e) from e
    return out


class IntentVerifyIn(BaseModel):
    intent: PaymentIntent
    assertion: dict[str, Any]


@router.post("/intent/verify")
def intent_verify(
    body: IntentVerifyIn, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    """Accept only if the requester's passkey signed exactly this intent. Every attempt, accepted
    or refused, is written to the case's custody chain (a refused tamper is evidence too)."""
    from satyapan.seal.intent import IntentError, display_text, intent_challenge

    svc = _services(state)
    payload = {
        "intent_seal": "pending",
        "nonce": body.intent.nonce,
        "challenge_sha256": intent_challenge(body.intent).hex(),
        "amount_inr": body.intent.amount_inr,
        "account_masked": body.intent.beneficiary.account_masked,
    }
    try:
        v = svc.intents.verify(body.intent, body.assertion, svc.clock())
    except IntentError as e:
        if body.intent.case_id in {c.id for c in state.repo.all_cases()}:
            state.custody.append(
                case_id=body.intent.case_id,
                event=CustodyEvent.ANALYSIS,
                actor=actor.employee.employee_id,
                payload={**payload, "intent_seal": "refused", "reason": e.reason},
            )
        raise _refuse(e) from e
    state.custody.append(
        case_id=body.intent.case_id,
        event=CustodyEvent.ANALYSIS,
        actor=actor.employee.employee_id,
        payload={**payload, "intent_seal": "approved", "sign_count": v.sign_count},
    )
    return {
        "accepted": True,
        "display_text": display_text(v.intent),
        "verified_at": v.verified_at.isoformat(),
        "note": "Approval recorded. On its own it does not clear a HOLD (checker rules apply).",
    }
