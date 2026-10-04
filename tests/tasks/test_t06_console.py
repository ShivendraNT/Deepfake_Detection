"""T06 acceptance (Python side). The real UI tests run with `make console-test` (vitest).
This file checks structure once console/src/App.tsx is no longer a stub."""

from __future__ import annotations

import pytest

from tests.helpers import ROOT, require_not_stub

pytestmark = pytest.mark.task("T06")


def test_app_is_implemented_and_uses_api_client() -> None:
    app = require_not_stub("console/src/App.tsx", "T06")
    assert "CaseList" in app and "CaseView" in app and "RoleSwitcher" in app


def test_components_exist() -> None:
    require_not_stub("console/src/App.tsx", "T06")
    for name in (
        "CaseList",
        "CaseView",
        "BandBadge",
        "TransactionCard",
        "ReasonCodes",
        "EvidenceList",
        "RoleSwitcher",
    ):
        assert (ROOT / "console" / "src" / "components" / f"{name}.tsx").exists(), name


def test_maker_never_renders_scores() -> None:
    require_not_stub("console/src/App.tsx", "T06")
    text = (ROOT / "console" / "src" / "components" / "CaseView.tsx").read_text(encoding="utf-8")
    assert "score" not in text or "canSeeScores" in text, "only checker/security may see scores"
