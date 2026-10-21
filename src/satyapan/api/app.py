"""FastAPI app factory. PRE-IMPLEMENTED (T01). Run: `make run`, then open http://127.0.0.1:8000/docs."""

from __future__ import annotations

import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from satyapan.api import (
    routes_cases,
    routes_citizen,
    routes_dashboard,
    routes_live,
    routes_reports,
    routes_seal,
    routes_verify,
)
from satyapan.api.state import AppState
from satyapan.settings import Settings, get_settings

_TASK_RE = re.compile(r"(T\d{2})")


def create_app(settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Satyapan — Payment Verification Desk", version="0.1.0")
    app.state.satyapan = state or AppState.build(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"chrome-extension://.*",
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
    ):
        app.include_router(r.router)
    return app


def __getattr__(name: str) -> FastAPI:
    # `uvicorn satyapan.api.app:app` builds the app lazily (imports stay side-effect free).
    if name == "app":
        return create_app()
    raise AttributeError(name)
