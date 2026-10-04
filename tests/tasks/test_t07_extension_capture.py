"""T07 acceptance (static checks). The real acceptance is manual: scores logged on a Meet tab
while the user still hears the call — record it in docs/STATUS.md notes."""

from __future__ import annotations

import json

import pytest

from tests.helpers import ROOT, require_not_stub

pytestmark = pytest.mark.task("T07")


def test_service_worker_uses_tab_capture_stream_id() -> None:
    sw = require_not_stub("extension/service_worker.js", "T07")
    assert "chrome.tabCapture.getMediaStreamId" in sw
    assert "chrome.offscreen.createDocument" in sw


def test_offscreen_keeps_audio_audible_and_resamples() -> None:
    off = require_not_stub("extension/offscreen.js", "T07")
    assert "chromeMediaSource" in off and "'tab'" in off.replace('"', "'")
    assert "destination" in off, "captured stream MUST be routed back to AudioContext.destination"
    assert "16000" in off
    assert "classifyWindows" in off or "voice_rules" in off


def test_manifest_permissions() -> None:
    m = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    assert m["manifest_version"] == 3
    assert {"tabCapture", "offscreen", "sidePanel"} <= set(m["permissions"])
