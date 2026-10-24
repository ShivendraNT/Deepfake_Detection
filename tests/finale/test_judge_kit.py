"""The judge kit and the automated dry run are part of the deliverable.

These are not detector tests: they prove the two commands a judge will run stay runnable and
keep returning the expected shape. Fake data only; no network.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import dry_run  # noqa: E402
import judge_kit  # noqa: E402


def test_judge_kit_scoreboard_is_complete() -> None:
    report = judge_kit.build_report()
    assert report["email"] == {**report["email"], "n": 10, "exact": 10, "failures": []}
    assert report["invoice"] == {**report["invoice"], "n": 6, "exact": 6, "failures": []}
    assert report["demo"]["n"] == 12
    assert report["demo"]["matches"] == 12
    assert report["demo"]["changed"] == 8
    assert set(report["ask"]["configs"]) == {
        "frozen lexicon v1.0",
        "context v1.2",
        "product (shipped)",
    }
    assert report["ask"]["data"]["asks"]["n"] == 92
    assert report["ask"]["data"]["benign"]["n"] == 157
    assert report["alert"]["split"] == "test"
    assert report["alert"]["routine"]["hold"]["n"] == 200
    assert report["alert"]["attack"]["ge_verify"]["n"] == 98
    assert report["alert"]["by_scenario"]
    assert report["limits"]


def test_dry_run_story_is_green() -> None:
    run = dry_run.one_run(1)
    assert run["ok"] is True
    assert len(run["steps"]) == 11
    assert all(step["ok"] for step in run["steps"])
    assert run["band"] == "HOLD"
    assert run["oob"] == "DENIED"
    assert run["report_sections"] == 5


def test_labelled_kit_mode_scores(tmp_path: Path, capsys: pytest.Capsys) -> None:
    kit = tmp_path / "kit.jsonl"
    kit.write_text(
        '{"id":"safe","text":"Dear Priya, please find our monthly invoice attached. '
        'Total 2,10,000 as per the usual terms. Regards, Kaveri.","vendor_id":"V001",'
        '"amount":210000,"expected":"PASS"}\n'
        '{"id":"scam","text":"Keep this between us. Transfer the payment to the new account '
        'and skip the approval.","vendor_id":"V001","amount":4850000,"expected":"HOLD"}\n',
        encoding="utf-8",
    )
    args = argparse.Namespace(
        labels=str(kit),
        vendor_id="V001",
        new_payee=False,
        amount=210_000,
        account=None,
        ifsc=None,
        beneficiary=None,
    )
    assert judge_kit.labels_check(args) == 0
    out = capsys.readouterr().out
    assert "Exact band match" in out
    assert "safe" in out
    assert "scam" in out
