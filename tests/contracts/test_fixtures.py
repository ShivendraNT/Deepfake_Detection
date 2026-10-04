"""Demo fixtures are valid, clearly fake, and decide exactly as documented."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from satyapan.contracts import PaymentAction
from satyapan.policy import decide_rules_only


def test_twelve_cases_match_expected_bands(repo, master, demo_dir: Path) -> None:
    expected = json.loads((demo_dir / "expected_decisions.json").read_text(encoding="utf-8"))
    cases = repo.all_cases()
    assert len(cases) == 12
    for c in cases:
        assert c.decision is not None
        assert c.decision.band.value == expected[c.id]["full"], c.id
        assert decide_rules_only(c, master).band.value == expected[c.id]["rules_only"], c.id


def test_payment_action_example_validates(demo_dir: Path) -> None:
    PaymentAction.model_validate_json((demo_dir / "payment_action.example.json").read_text())


def test_master_loads(master) -> None:
    assert len(master.vendors) == 5
    assert master.employee("emp_priya").roles == ["maker"]
    assert {e.employee_id for e in master.senior_approvers()} == {"emp_rajesh", "emp_sunil"}


def test_all_demo_data_is_obviously_fake(demo_dir: Path) -> None:
    with (demo_dir / "vendor_master.csv").open() as fh:
        for row in csv.DictReader(fh):
            assert row["ifsc"].startswith("FAK")
            assert row["account_number"].startswith("9999")
            assert row["phone_on_file"].startswith("+91-00000")
            assert row["email_domain"].endswith(".example")
            assert row["gstin"].startswith("00")
    text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in demo_dir.rglob("*")
        if p.is_file() and p.suffix in {".json", ".csv", ".txt", ".eml", ".jsonl"}
    )
    for ifsc in re.findall(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", text):
        assert ifsc.startswith("FAK"), ifsc
    for acct in re.findall(r"\b\d{14}\b", text):
        assert acct.startswith("9999"), acct


def test_no_media_files_in_repo(demo_dir: Path) -> None:
    banned = {".wav", ".mp3", ".ogg", ".opus", ".m4a", ".mp4", ".webm", ".flac"}
    root = demo_dir.parents[1]
    found = [
        p
        for d in (
            "data",
            "extension",
            "research",
            "docs",
            "results",
            "console/src",
            "console/public",
        )
        if (root / d).exists()
        for p in (root / d).rglob("*")
        if p.suffix.lower() in banned
    ]
    assert found == [], f"media files must never be committed: {found}"
