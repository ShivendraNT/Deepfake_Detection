"""Live-call endpoints (T11). Extension -> backend: 10 s audio chunks and on-device voice scores.
Backend -> side panel: server-sent events (GET /live/{call_id}/events)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
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
    t_start_s: float | None = Form(None),
    t_end_s: float | None = Form(None),
    state: AppState = Depends(get_state),
) -> list[dict[str, Any]]:
    if call_id not in state.live().sessions:
        raise HTTPException(status_code=404, detail="unknown or stopped call")
    data = await audio.read()
    # Whisper takes seconds: run it in a worker thread so SSE and other requests keep flowing.
    events = await run_in_threadpool(
        state.live().handle_chunk,
        call_id,
        chunk_index,
        data,
        audio.content_type or "audio/webm",
        t_start_s,
        t_end_s,
    )
    if call_id not in state.live().sessions:  # the call was stopped while we transcribed
        return [e.model_dump(mode="json") for e in events]
    state.repo.put(state.live().sessions[call_id].case)
    return [e.model_dump(mode="json") for e in events]


@router.post("/{call_id}/voice")
def voice(
    call_id: str, windows: list[VoiceWindowResult], state: AppState = Depends(get_state)
) -> list[dict[str, Any]]:
    if call_id not in state.live().sessions:
        raise HTTPException(status_code=404, detail="unknown or stopped call")
    events = state.live().handle_voice(call_id, windows)
    state.repo.put(state.live().sessions[call_id].case)
    return [e.model_dump(mode="json") for e in events]


@router.post("/{call_id}/video")
async def video(
    call_id: str,
    frames: list[UploadFile] = File(...),
    times: str = Form(...),
    state: AppState = Depends(get_state),
) -> list[dict[str, Any]]:
    """Screen frames of the call (finale video check). JPEG only, at most 64 per request,
    timestamps in seconds on the capture clock. Frames live in memory for one window only."""
    from satyapan.video.frames import MAX_FRAMES_PER_POST, decode_jpeg

    if call_id not in state.live().sessions:
        raise HTTPException(status_code=404, detail="unknown or stopped call")
    try:
        ts = [float(t) for t in json.loads(times)]
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="times must be a JSON list of seconds") from exc
    if len(ts) != len(frames) or not 0 < len(frames) <= MAX_FRAMES_PER_POST:
        raise HTTPException(status_code=422, detail="one timestamp per frame, 1-64 frames")
    blobs = [await f.read() for f in frames]

    def work() -> list[Any]:
        decoded = []
        for t, blob in zip(ts, blobs, strict=True):
            try:
                decoded.append((t, decode_jpeg(blob)))
            except ValueError:
                continue  # a corrupt frame is skipped; never stitched or invented
        return state.live().handle_video(call_id, sorted(decoded, key=lambda x: x[0]))

    events = await run_in_threadpool(work)
    if call_id in state.live().sessions:
        state.repo.put(state.live().sessions[call_id].case)
    return [e.model_dump(mode="json") for e in events]


@router.get("/{call_id}/events")
async def events(call_id: str, state: AppState = Depends(get_state)) -> StreamingResponse:
    bus = state.live().bus
    queue = bus.subscribe(call_id)

    async def gen() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {ev.model_dump_json()}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            bus.unsubscribe(call_id, queue)  # client went away

    return StreamingResponse(gen(), media_type="text/event-stream")
