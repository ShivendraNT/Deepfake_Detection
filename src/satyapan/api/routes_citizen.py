"""Citizen Scam Check (T24 + finale): coarse output only; rate-limited in production.

GET  /check  (= /scam-check.html)                               the consumer page itself
POST /scam-check        {"text": ..., "lang": "en"|"hi"}       pasted message
POST /scam-check/file   multipart: file=@..., lang=en|hi        screenshot, voice note, photo,
                                                                video, e-mail or PDF
POST /scam-check/money-sent  {"utr": ..., "amount_inr": ...}     golden-hour drafts (1930 script,
                                                                bank message, portal fields)
All run on this device and keep nothing (no vault, no case store). Nothing is ever submitted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from satyapan.api.auth import get_state
from satyapan.api.state import AppState
from satyapan.contracts.enums import Lang
from satyapan.contracts.report import TransactionFacts

router = APIRouter()
PUBLIC = Path(__file__).resolve().parents[3] / "console" / "public"
PAGE = PUBLIC / "scam-check.html"
MOBILE_PAGE = PUBLIC / "mobile.html"
POCKET_PAGE = PUBLIC / "pocket.html"
POCKET_MANIFEST = PUBLIC / "pocket.webmanifest"
POCKET_ICON_192 = PUBLIC / "satya-192.png"
POCKET_ICON_512 = PUBLIC / "satya-512.png"
IST = timezone(timedelta(hours=5, minutes=30))  # no DST; no tzdata needed on Windows


@router.get("/check", include_in_schema=False)
@router.get("/scam-check.html", include_in_schema=False)
def scam_check_page() -> FileResponse:
    """The consumer page, served by the same local engine (a phone on the same Wi-Fi can open
    http://<laptop-ip>:8000/check when the engine runs with `make live`)."""
    return FileResponse(PAGE, media_type="text/html")


@router.get("/mobile", include_in_schema=False)
@router.get("/m", include_in_schema=False)
def mobile_companion_page() -> FileResponse:
    """A read-only phone mirror of the live companion (same Wi-Fi, no microphone, no capture).

    It relays `/companion/events` (chips, policy band, OOB) and can stop listening or send an
    OOB-Confirm. It never computes a band and never starts capture."""
    return FileResponse(
        MOBILE_PAGE,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/pocket", include_in_schema=False)
@router.get("/app", include_in_schema=False)
def pocket_page() -> FileResponse:
    """Satya Pocket: the phone app client (check, live, report, help).

    It calls the same local engine over the hotspot and displays its answer. It never opens the
    microphone, never captures a phone call, and never computes a band."""
    return FileResponse(
        POCKET_PAGE,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/pocket.webmanifest", include_in_schema=False)
def pocket_manifest() -> FileResponse:
    """Installable app metadata (Add to Home Screen). No service worker: LAN HTTP cannot use one."""
    return FileResponse(POCKET_MANIFEST, media_type="application/manifest+json")


@router.get("/satya-192.png", include_in_schema=False)
def pocket_icon_192() -> FileResponse:
    return FileResponse(POCKET_ICON_192, media_type="image/png")


@router.get("/satya-512.png", include_in_schema=False)
def pocket_icon_512() -> FileResponse:
    return FileResponse(POCKET_ICON_512, media_type="image/png")


class ScamCheckIn(BaseModel):
    text: str = Field(max_length=5000)
    lang: Lang = Lang.EN


@router.post("/scam-check")
def scam_check_route(body: ScamCheckIn, state: AppState = Depends(get_state)) -> dict[str, Any]:
    from satyapan.citizen.check import citizen_check

    out = citizen_check(state, body.text.encode("utf-8"), "message.txt", "text/plain", body.lang)
    return out.model_dump(mode="json")


@router.post("/scam-check/file")
async def scam_check_file(
    file: UploadFile = File(...),
    lang: Lang = Form(Lang.EN),
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    from satyapan.citizen.check import citizen_check

    data = await file.read()
    try:
        out = citizen_check(state, data, file.filename, file.content_type or "", lang)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        del data  # nothing is kept
    return out.model_dump(mode="json")


class MoneySentIn(BaseModel):
    utr: str = Field(min_length=6, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
    amount_inr: int = Field(gt=0, le=10_000_000_000)
    sent_at: datetime | None = None  # a browser's local time is read as IST
    rail: Literal["UPI", "IMPS", "NEFT", "RTGS", "CARD", "WALLET", "OTHER"] = "UPI"
    your_bank: str = Field("", max_length=80)
    your_account_last4: str = Field("", max_length=4, pattern=r"^\d{0,4}$")
    to_upi: str = Field("", max_length=80)
    to_account: str = Field("", max_length=40)
    to_ifsc: str = Field("", max_length=20)
    to_name: str = Field("", max_length=80)
    scammer_phone: str = Field("", max_length=20)
    what_happened: str = Field("", max_length=1000)
    lang: Lang = Lang.EN


@router.post("/scam-check/money-sent")
def money_sent(body: MoneySentIn) -> dict[str, Any]:
    """Drafts only (MANUAL_ONLY): the person calls 1930 and files on the portal themselves."""
    from satyapan.report.citizen import build_citizen_pack

    sent = body.sent_at
    if sent is not None and sent.tzinfo is None:
        sent = sent.replace(tzinfo=IST)
    facts = TransactionFacts(
        utr=body.utr,
        amount_inr=body.amount_inr,
        sent_at=sent,
        rail=body.rail,
        debit_account_masked=f"••••{body.your_account_last4}" if body.your_account_last4 else "",
        beneficiary_name=body.to_name.strip() or "the fraudster",
        beneficiary_account=body.to_account.strip() or None,
        beneficiary_ifsc=body.to_ifsc.strip().upper() or None,
        beneficiary_upi=body.to_upi.strip() or None,
        beneficiary_bank=None,
    )
    pack = build_citizen_pack(
        facts,
        your_bank=body.your_bank,
        scammer_phone=body.scammer_phone,
        story=body.what_happened,
        lang=body.lang,
    )
    return pack.model_dump(mode="json")
