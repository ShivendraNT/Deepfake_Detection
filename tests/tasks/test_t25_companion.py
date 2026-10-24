"""T25 acceptance: Desktop Guardian Companion contract and event tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.task("T25")


def test_t25_spec_exists() -> None:
    """Verify that the T25 specification and grand finals architecture are present."""
    from pathlib import Path

    assert Path("docs/tasks/T25-desktop-companion.md").exists()
    assert Path("docs/GRAND_FINALS_ARCHITECTURE.md").exists()
