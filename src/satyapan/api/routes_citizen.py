"""Citizen Scam Check (T24 + finale): coarse output only; rate-limited in production.

POST /scam-check        {"text": ..., "lang": "en"|"hi"}       pasted message
POST /scam-check/file   multipart: file=@..., lang=en|hi        screenshot, voice note, photo,
                                                                video, e-mail or PDF
Both run every detector on this device and keep nothing (no vault, no case store).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from satyapan.api.auth import get_state
from satyapan.api.state import AppState
from satyapan.contracts.enums import Lang

router = APIRouter()


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
