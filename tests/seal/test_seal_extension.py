"""The side-panel seal chip (reducer event `seal` + view model) passes its node tests, and the
existing T10 controls are still present (the chip is additive)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from tests.helpers import ROOT


def test_seal_chip_node_tests() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    r = subprocess.run(
        [node, "--test", str(ROOT / "extension" / "tests" / "seal_chip.test.mjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_seal_chip_is_additive() -> None:
    html = (ROOT / "extension" / "sidepanel.html").read_text(encoding="utf-8")
    assert 'id="seal-chip"' in html and "hidden" in html
    for el in ("voice-meter", "ask-chips", "suggested-line", "btn-confirm", "band-banner"):
        assert f'id="{el}"' in html
