"""Citizen Scam Check (T24 + finale): coarse output only; rate-limited in production.

POST /scam-check        {"text": ..., "lang": "en"|"hi"}       pasted message
POST /scam-check/file   multipart: file=@..., lang=en|hi        screenshot, voice note, photo,
                                                                video, e-mail or PDF
POST /scam-check/money-sent  {"utr": ..., "amount_inr": ...}     golden-hour drafts (1930 script,
                                                                bank message, portal fields)
All run on this device and keep nothing (no vault, no case store). Nothing is ever submitted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from satyapan.api.auth import get_state
from satyapan.api.state import AppState
from satyapan.contracts.enums import Lang
from satyapan.contracts.report import TransactionFacts

router = APIRouter()
IST = timezone(timedelta(hours=5, minutes=30))  # no DST; no tzdata needed on Windows


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
