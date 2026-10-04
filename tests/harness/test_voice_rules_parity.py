"""Python and JavaScript voice-window rules give identical labels."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from satyapan.voice.rules import VoiceThresholds, classify_windows

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    {"scores": [0.3, 0.95, 0.91], "tauHi": 0.9, "tauLo": 0.6, "speech": 15},
    {"scores": [0.95, 0.2, 0.95], "tauHi": 0.9, "tauLo": 0.6, "speech": 15},
    {"scores": [0.1, 0.2], "tauHi": 0.9, "tauLo": 0.6, "speech": 10},
    {"scores": [0.1], "tauHi": 0.9, "tauLo": 0.6, "speech": 2},
    {"scores": [0.65, 0.7], "tauHi": 0.9, "tauLo": 0.6, "speech": 10},
    {"scores": [], "tauHi": 0.9, "tauLo": 0.6, "speech": 0},
    {"scores": [0.9, 0.9], "tauHi": 0.9, "tauLo": 0.6, "speech": 10},
]


def _py(c: dict) -> str:  # type: ignore[type-arg]
    th = VoiceThresholds(tau_hi=c["tauHi"], tau_lo=c["tauLo"], model_version="t")
    return classify_windows(c["scores"], th, c["speech"]).label.value


def test_python_rules_expected() -> None:
    assert [_py(c) for c in CASES] == [
        "likely_synthetic",
        "inconclusive",
        "no_signs",
        "inconclusive",
        "inconclusive",
        "inconclusive",
        "likely_synthetic",
    ]


def test_js_matches_python() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    out = subprocess.run(
        [node, str(ROOT / "extension" / "tests" / "parity_cli.mjs"), json.dumps(CASES)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=ROOT / "extension",
    )
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [_py(c) for c in CASES]
