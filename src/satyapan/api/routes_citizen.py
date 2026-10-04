"""Citizen Scam Check (stretch S1, T24). Coarse output only; rate-limited in production."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from satyapan.contracts.enums import Lang

router = APIRouter()


class ScamCheckIn(BaseModel):
    text: str = Field(max_length=5000)
    lang: Lang = Lang.EN


@router.post("/scam-check")
def scam_check_route(body: ScamCheckIn) -> dict[str, Any]:
    from satyapan.citizen.rules import scam_check

    return scam_check(body.text, body.lang).model_dump(mode="json")
