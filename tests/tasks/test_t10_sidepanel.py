"""T10 acceptance: side panel renders from a recorded event stream (JSON replay).
The reducer extension/lib/panel_state.js is tested with node's built-in test runner."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from tests.helpers import ROOT, require_not_stub

pytestmark = pytest.mark.task("T10")


def test_panel_reducer_node_tests() -> None:
    require_not_stub("extension/lib/panel_state.js", "T10")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    r = subprocess.run(
        [node, "--test", str(ROOT / "extension" / "tests" / "panel_state.test.mjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_sidepanel_has_required_controls() -> None:
    html = require_not_stub("extension/sidepanel.html", "T10")
    for el in (
        "voice-meter",
        "transcript",
        "ask-chips",
        "suggested-line",
        "btn-confirm",
        "btn-link-payment",
        "protection-indicator",
    ):
        assert f'id="{el}"' in html, el
