"""FastAPI app factory. PRE-IMPLEMENTED (T01). Run: `make run`, then open http://127.0.0.1:8000/docs."""

from __future__ import annotations

import os
import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from satyapan.api import (
    routes_cases,
    routes_citizen,
    routes_companion,
    routes_dashboard,
    routes_live,
    routes_reports,
    routes_seal,
    routes_verify,
)
from satyapan.api.state import AppState
from satyapan.settings import Settings, get_settings

_TASK_RE = re.compile(r"(T\d{2})")


def _warm_speech_engine(state: AppState) -> None:
    """`make run` sets SATYAPAN_ASR_WARMUP=1: load Whisper now, in the background, so the first
    sentence of the demo call is not slow. Off by default (tests never load a model)."""
    if os.environ.get("SATYAPAN_ASR_WARMUP") != "1":
        return
    warm = getattr(state.transcriber(), "warm_up", None)
    if warm is None:
        return

    def run() -> None:
        try:
            warm()
        except Exception:  # noqa: BLE001 - the error is reported by /companion/health
            return

    threading.Thread(target=run, name="asr-warmup", daemon=True).start()


def create_app(settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _warm_speech_engine(app.state.satyapan)
        yield

    app = FastAPI(title="Satyapan — Payment Verification Desk", version="0.1.0", lifespan=lifespan)
    app.state.satyapan = state or AppState.build(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotImplementedError)
    async def not_implemented(_: Request, exc: NotImplementedError) -> JSONResponse:
        msg = str(exc)
        m = _TASK_RE.search(msg)
        return JSONResponse(
            status_code=501,
            content={
                "detail": "not implemented yet",
                "task": m.group(1) if m else None,
                "hint": msg,
            },
        )

    for r in (
        routes_dashboard,
        routes_cases,
        routes_verify,
        routes_reports,
        routes_live,
        routes_citizen,
        routes_seal,
        routes_companion,
    ):
        app.include_router(r.router)
        app.include_router(r.router, prefix="/api")
    return app


def __getattr__(name: str) -> FastAPI:
    # `uvicorn satyapan.api.app:app` builds the app lazily (imports stay side-effect free).
    if name == "app":
        return create_app()
    raise AttributeError(name)
