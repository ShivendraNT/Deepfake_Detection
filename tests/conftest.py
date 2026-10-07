"""Shared pytest setup. HARNESS FILE — do not edit without leader approval.

1. Task tests are marked @pytest.mark.task("T07"). While a task is not implemented, its code
   raises NotImplementedError and the test is reported as SKIPPED (not failed).
2. `pytest --task T07` (or `make task T=T07`) runs ONLY T07's tests and is STRICT: a
   NotImplementedError is a FAILURE, so you see red until you implement it.
3. Tasks marked `done` in docs/STATUS.md are always strict (a done task may never skip).
4. Unit tests cannot open network connections (mark a test @pytest.mark.network to allow it).
   Loopback (`127.0.0.1` / `::1` / `localhost`) is allowed: it is how asyncio builds its
   in-process self-pipe (Windows `socket.socketpair` fallback) and reaches nothing outside
   the machine. Real hostnames stay blocked.
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

ROOT = Path(__file__).resolve().parents[1]

settings.register_profile(
    "repo",
    max_examples=200,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("repo")


def _done_tasks() -> set[str]:
    status = ROOT / "docs" / "STATUS.md"
    if not status.exists():
        return set()
    done = set()
    for line in status.read_text(encoding="utf-8").splitlines():
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"t\d{2}", cells[0]) and "done" in cells:
            done.add(cells[0].upper())
    return done


DONE_TASKS = _done_tasks()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--task",
        default=None,
        help="Run only tests marked @pytest.mark.task('<ID>'); NotImplementedError = failure.",
    )


def _task_of(item: pytest.Item) -> str | None:
    m = item.get_closest_marker("task")
    return str(m.args[0]).upper() if m and m.args else None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    task = config.getoption("--task")
    if not task:
        return
    task = str(task).upper()
    keep = [it for it in items if _task_of(it) == task]
    drop = [it for it in items if _task_of(it) != task]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):  # type: ignore[no-untyped-def]
    outcome = yield
    rep = outcome.get_result()
    task = _task_of(item)
    if task is None or call.excinfo is None:
        return
    if not call.excinfo.errisinstance(NotImplementedError):
        return
    strict = (
        (item.config.getoption("--task") or "").upper() == task
        or task in DONE_TASKS
        or os.environ.get("SATYAPAN_STRICT") == "1"
    )
    if strict:
        return
    rep.outcome = "skipped"
    rep.longrepr = (str(item.path), item.location[1] or 0, f"Skipped: {task} not implemented yet")


_BLOCKED = (
    "Network access is disabled in unit tests. Use a fake adapter "
    "(satyapan.adapters.base) or mark the test @pytest.mark.network."
)


def _is_loopback(address: object) -> bool:
    """True for an in-process/loopback peer (asyncio self-pipe, local fixtures)."""
    if not isinstance(address, tuple) or not address or not isinstance(address[0], str):
        return False
    host = address[0]
    return host == "localhost" or host == "::1" or host.startswith("127.")


@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("network"):
        return

    real_connect = socket.socket.connect

    def guard_connect(self: socket.socket, address: object) -> None:
        if _is_loopback(address):
            real_connect(self, address)  # type: ignore[arg-type]
            return
        raise RuntimeError(_BLOCKED)

    def guard_blocked(*args: object, **kwargs: object) -> None:
        raise RuntimeError(_BLOCKED)

    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket, "create_connection", guard_blocked)


# ---------------------------------------------------------------- shared fixtures


@pytest.fixture(scope="session")
def demo_dir() -> Path:
    return ROOT / "data" / "demo"


@pytest.fixture(scope="session")
def master(demo_dir: Path):  # type: ignore[no-untyped-def]
    from satyapan.master import load_master

    return load_master(demo_dir)


@pytest.fixture()
def repo(master, demo_dir: Path):  # type: ignore[no-untyped-def]
    from satyapan.repository import CaseRepository

    return CaseRepository.from_fixtures(master, demo_dir / "cases")


@pytest.fixture()
def client():  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from satyapan.api.app import create_app
    from satyapan.settings import Settings

    return TestClient(create_app(Settings()))
