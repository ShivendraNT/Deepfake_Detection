"""T20 acceptance: paraphrase prompts, meaning-preservation filters, agreement stats."""

from __future__ import annotations

import pytest

from research.attacks.filters import FilterDecision, cohen_kappa, cosine, discard_rate, filter_pair
from research.attacks.paraphrase import PROMPTS, build_prompt
from tests.helpers import require_artifact

pytestmark = pytest.mark.task("T20")


def test_build_prompt() -> None:
    msgs = build_prompt("P1", "caller: hello")
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == PROMPTS["P1"]
    assert msgs[1] == {"role": "user", "content": "caller: hello"}
    with pytest.raises(ValueError):
        build_prompt("P1", "   ")


def test_prompts_never_contain_scam_content() -> None:
    for p in PROMPTS.values():
        low = p.lower()
        assert not any(
            w in low for w in ("otp", "password", "anydesk", "gift card", "scam", "fraud")
        )


def test_cosine() -> None:
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        cosine([0, 0], [1, 0])


@pytest.mark.parametrize(
    ("emb", "judge", "keep", "reason"),
    [
        ([1.0, 0.0], True, True, "ok"),
        ([0.0, 1.0], True, False, "low_cosine"),
        ([1.0, 0.0], False, False, "judge_rejected"),
        ([1.0, 0.0], None, False, "judge_missing"),
    ],
)
def test_filter_pair(emb, judge, keep, reason) -> None:
    d = filter_pair([1.0, 0.0], emb, judge)
    assert (d.keep, d.reason) == (keep, reason)


def test_kappa_and_discard() -> None:
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)
    ds = [FilterDecision(True, 0.9, True, "ok"), FilterDecision(False, 0.5, True, "low_cosine")]
    assert discard_rate(ds) == 0.5


def test_attack_stats_committed() -> None:
    p = require_artifact("results/attack_filter_stats.json", "T20")
    assert "discard_rate" in p.read_text(encoding="utf-8")
