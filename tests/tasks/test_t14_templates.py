"""T14 acceptance: every reason code has EN + HI text; no false-reassurance words."""

from __future__ import annotations

import re

import pytest

from satyapan.contracts import Lang, ReasonCode
from satyapan.explain.templates import explain_template, reason_text
from tests.helpers import api_ok

pytestmark = pytest.mark.task("T14")

FORBIDDEN = re.compile(r"\b(safe|legitimate|verified|genuine|authentic)\b", re.I)
FORBIDDEN_HI = ("सुरक्षित", "वैध", "सत्यापित", "असली", "प्रामाणिक")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@pytest.mark.parametrize("code", list(ReasonCode))
def test_every_code_has_both_languages(code: ReasonCode) -> None:
    en, hi = reason_text(code, Lang.EN), reason_text(code, Lang.HI)
    assert en.strip() and hi.strip()
    assert DEVANAGARI.search(hi), f"{code} Hindi text must be Devanagari"
    assert not FORBIDDEN.search(en), f"{code} EN text must not reassure"
    assert not any(w in hi for w in FORBIDDEN_HI), f"{code} HI text must not reassure"
    assert len(en) <= 300 and len(hi) <= 300


def test_template_explanation(repo) -> None:
    d = repo.get("case_s07").decision
    ex = explain_template(d, Lang.EN)
    assert ex.text.startswith("Band: VERIFY") and ex.source == "template"
    assert reason_text(ReasonCode.FLOOR_C1_BANK_CHANGED, Lang.EN) in ex.text
    assert explain_template(d, Lang.HI).text.startswith("स्तर: VERIFY")


def test_api_explanation(client) -> None:
    r = api_ok(client.get("/cases/case_s07/explanation?lang=hi"), "T14")
    assert r.status_code == 200 and r.json()["lang"] == "hi"
