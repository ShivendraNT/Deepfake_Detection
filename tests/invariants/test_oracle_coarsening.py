"""Makers never see raw scores (oracle-abuse mitigation)."""

from __future__ import annotations

from satyapan.api.views import case_view
from satyapan.contracts import Role


def test_maker_view_has_no_scores(repo) -> None:
    for case in repo.all_cases():
        view = case_view(case, Role.MAKER)
        for s in view["signals"]:
            assert s["score"] is None
            assert not any(k.startswith(("score", "consecutive")) for k in s["detail"])


def test_checker_view_keeps_scores(repo) -> None:
    view = case_view(repo.get("case_s06"), Role.CHECKER)
    assert any(s["score"] is not None for s in view["signals"])
