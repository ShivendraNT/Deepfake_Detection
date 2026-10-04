"""T22 acceptance: 10/10 successful logged dry runs + the offline demo-call tab."""

from __future__ import annotations

import csv

import pytest

from tests.helpers import ROOT, require_artifact, require_not_stub

pytestmark = pytest.mark.task("T22")


def test_ten_successful_dry_runs() -> None:
    p = require_artifact("results/dry_runs.csv", "T22")
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert len(rows) >= 10
    for r in rows:
        for col in ("moment1_voice_alert", "oob_hold", "moment2_floor_verify", "pack_utr_first"):
            assert r[col].strip().lower() == "yes", f"run {r['run']}: {col}={r[col]}"


def test_offline_demo_call_tab() -> None:
    html = require_not_stub("extension/demo_call.html", "T22")
    assert "<audio" in html


def test_consent_template_present() -> None:
    assert (ROOT / "docs" / "consent" / "VOICE_CLONE_CONSENT_TEMPLATE.md").exists()
