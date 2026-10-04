"""T23 acceptance: 5-slide deck with honest numbers + backup recording."""

from __future__ import annotations

import re

import pytest

from tests.helpers import require_artifact, require_not_stub

pytestmark = pytest.mark.task("T23")


def test_outline_has_five_slides_and_every_number_has_n() -> None:
    text = require_not_stub("docs/pitch/DECK_OUTLINE.md", "T23")
    assert len(re.findall(r"^## Slide \d", text, flags=re.M)) == 5
    for line in text.splitlines():
        if "%" in line and "EER" in line:
            assert "n=" in line or "arXiv" in line, f"number without n or citation: {line}"


def test_deck_and_recording_exist() -> None:
    require_artifact("docs/pitch/deck.pdf", "T23")
    require_artifact("docs/pitch/backup_recording.md", "T23")
