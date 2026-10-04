"""No auto-reporting: no submit endpoints, no network in the report module, MANUAL_ONLY packs."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "satyapan"
FORBIDDEN_ROUTE_WORDS = ("submit", "file-complaint", "auto-report", "ncrp", "1930", "cybercrime")


def test_no_reporting_routes(client) -> None:
    paths = [p.lower() for p in client.get("/openapi.json").json()["paths"]]
    assert "/cases" in paths
    for p in paths:
        assert not any(w in p for w in FORBIDDEN_ROUTE_WORDS), (
            f"route {p} looks like auto-reporting"
        )


def test_report_module_has_no_network_or_subprocess() -> None:
    for py in (SRC / "report").rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                assert not m.startswith(
                    (
                        "satyapan.adapters",
                        "subprocess",
                        "smtplib",
                        "urllib",
                        "httpx",
                        "requests",
                        "boto3",
                    )
                ), f"{py.name} imports {m}"


def test_no_confirmed_fraud_set_by_system_in_source() -> None:
    # The engine may suggest SUSPECTED_FRAUD (OOB denied) but never CONFIRMED_FRAUD.
    engine = (SRC / "policy" / "engine.py").read_text(encoding="utf-8")
    assert "suggested_status = CaseStatus.CONFIRMED_FRAUD" not in engine
