"""Live-call endpoints (T11). Extension -> backend: 10 s audio chunks and on-device voice scores.
Backend -> side panel: server-sent events (GET /live/{call_id}/events)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from satyapan.api.auth import Actor, get_actor, get_state
from satyapan.api.state import AppState
from satyapan.contracts.live import VoiceWindowResult

router = APIRouter(prefix="/live")


@router.post("/{call_id}/start")
def start(
    call_id: str, state: AppState = Depends(get_state), actor: Actor = Depends(get_actor)
) -> dict[str, Any]:
    session = state.live().start(call_id, actor.employee.employee_id)
    state.repo.put(session.case)
    return {"call_id": call_id, "case_id": session.case.id}


@router.post("/{call_id}/chunk")
async def chunk(
    call_id: str,
    chunk_index: int = Form(...),
    audio: UploadFile = File(...),
    state: AppState = Depends(get_state),
) -> list[dict[str, Any]]:
    data = await audio.read()
    events = state.live().handle_chunk(
        call_id, chunk_index, data, audio.content_type or "audio/webm"
    )
    return [e.model_dump(mode="json") for e in events]


@router.post("/{call_id}/voice")
def voice(
    call_id: str, windows: list[VoiceWindowResult], state: AppState = Depends(get_state)
) -> list[dict[str, Any]]:
    events = state.live().handle_voice(call_id, windows)
    return [e.model_dump(mode="json") for e in events]


@router.get("/{call_id}/events")
async def events(call_id: str, state: AppState = Depends(get_state)) -> StreamingResponse:
    queue = state.live().bus.subscribe(call_id)

    async def gen() -> AsyncIterator[str]:
        while True:
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=15)
                yield f"data: {ev.model_dump_json()}\n\n"
            except TimeoutError:
                yield ": keep-alive\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
