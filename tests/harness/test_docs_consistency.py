"""Docs match the code: module map paths exist, TS types mirror contracts, rules present."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from satyapan import contracts

ROOT = Path(__file__).resolve().parents[2]


def test_module_map_paths_exist() -> None:
    text = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    start = text.index("**Module map**")
    table = text[start : text.index("## 4.", start)]
    paths = re.findall(r"^\| `([^`]+)` \|", table, flags=re.M)
    assert len(paths) >= 40
    for p in paths:
        assert (ROOT / p).exists(), f"module map lists missing path {p}"


def test_every_python_module_is_in_the_module_map() -> None:
    text = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for py in (ROOT / "src" / "satyapan").rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if py.name == "__init__.py" or rel in ("src/satyapan/settings.py",):
            continue
        parent = py.parent.relative_to(ROOT).as_posix() + "/"
        assert f"`{rel}`" in text or f"`{parent}`" in text, f"{rel} missing from module map"


@pytest.mark.parametrize(
    "model", ["Case", "Decision", "PaymentAction", "Signal", "Evidence", "ClearanceRequirement"]
)
def test_console_types_mirror_contracts(model: str) -> None:
    ts = (ROOT / "console" / "src" / "types.ts").read_text(encoding="utf-8")
    block = ts[ts.index(f"export interface {model} ") :]
    block = block[: block.index("\n}")]
    for field in getattr(contracts, model).model_fields:
        assert re.search(rf"\b{field}\??:", block), f"types.ts {model} lacks field {field}"


def test_agents_md_states_the_non_negotiables() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
    for phrase in [
        "only `src/satyapan/policy/` sets the band",
        "raise-only",
        "signal.make",
        "no auto-reporting",
        "network only in `src/satyapan/adapters/`",
        "makers never see raw scores",
        "3 failed attempts",
        "make task t=",
    ]:
        assert phrase in text, phrase


def test_replay_events_match_contract() -> None:
    from satyapan.contracts import LIVE_EVENT_ADAPTER

    lines = (
        (ROOT / "extension" / "replay" / "sample_events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    events = [LIVE_EVENT_ADAPTER.validate_json(line) for line in lines if line.strip()]
    assert {e.type for e in events} == {"status", "voice", "transcript", "ask", "band"}
    assert all(getattr(e, "score", None) is None for e in events)


def test_glossary_and_decisions_cover_key_terms() -> None:
    g = (ROOT / "docs" / "GLOSSARY.md").read_text(encoding="utf-8")
    for term in ["Floor", "OOB-Confirm", "UTR", "Grey flag", "Prompt injection"]:
        assert term in g
    d = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^### ADR-\d{3}", d, flags=re.M)) >= 15
