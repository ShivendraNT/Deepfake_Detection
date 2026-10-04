"""T15 acceptance: faithfulness checker + LLM summary fallback + injection red-team."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.adapters.base import FakeLLM
from satyapan.contracts import EvidenceItemForLLM, Lang
from satyapan.explain.faithfulness import check_faithfulness
from satyapan.explain.prompt import SYSTEM_PROMPT
from satyapan.explain.summary import summarize
from tests.helpers import require_artifact

pytestmark = pytest.mark.task("T15")

ITEMS = [
    EvidenceItemForLLM(
        id="ev_rc_FLOOR_C1_BANK_CHANGED",
        type="reason_code",
        value="FLOOR_C1_BANK_CHANGED",
        source="trusted",
    ),
    EvidenceItemForLLM(
        id="ev_txn_amount_inr", type="transaction_field", value="284000", source="trusted"
    ),
    EvidenceItemForLLM(
        id="ev_txn_beneficiary",
        type="transaction_field",
        value="••••9917 FAKD0000991",
        source="trusted",
    ),
]
GOOD = (
    "The bank account differs from the vendor master [ev_rc_FLOOR_C1_BANK_CHANGED]. "
    "The amount is ₹2,84,000 to FAKD0000991 [ev_txn_amount_inr][ev_txn_beneficiary]."
)


def test_good_summary_passes() -> None:
    assert check_faithfulness(GOOD, ITEMS, False).ok


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("The amount is ₹3,00,000 [ev_txn_amount_inr].", "entity"),
        ("Pay to FAKX0000001 [ev_txn_beneficiary].", "entity"),
        ("The bank account differs from the vendor master.", "citation"),
        ("The bank account differs [ev_nope].", "citation"),
        ("This payment is safe [ev_rc_FLOOR_C1_BANK_CHANGED].", "forbidden"),
        ("यह भुगतान सुरक्षित है [ev_rc_FLOOR_C1_BANK_CHANGED]।", "forbidden"),
    ],
)
def test_bad_summaries_fail(text: str, kind: str) -> None:
    r = check_faithfulness(text, ITEMS, False)
    assert not r.ok and any(f.startswith(kind) for f in r.failures), r.failures


def test_forbidden_allowed_after_verified_clearance() -> None:
    assert check_faithfulness(
        "The vendor was verified by callback [ev_rc_FLOOR_C1_BANK_CHANGED].", ITEMS, True
    ).ok


def test_summary_falls_back_on_injected_output(repo, master) -> None:
    case = repo.get("case_s07")
    llm = FakeLLM(reply="Ignore the floor. This payment is safe and verified.")
    ex = summarize(case, case.decision, Lang.EN, llm)
    assert ex.source == "template" and ex.band == case.decision.band
    assert ex.faithfulness is not None and not ex.faithfulness.ok
    assert llm.last_system == SYSTEM_PROMPT


def test_summary_uses_llm_when_faithful(repo) -> None:
    case = repo.get("case_s07")
    reply = "The bank account differs from the vendor master [ev_rc_FLOOR_C1_BANK_CHANGED]."
    ex = summarize(case, case.decision, Lang.EN, FakeLLM(reply=reply))
    assert ex.source == "llm" and ex.text == reply


def test_llm_errors_fall_back(repo) -> None:
    class Boom:
        def complete(self, system: str, user: str, max_tokens: int) -> str:
            raise TimeoutError

    case = repo.get("case_s07")
    assert summarize(case, case.decision, Lang.EN, Boom()).source == "template"
    assert summarize(case, case.decision, Lang.EN, None).source == "template"


def test_redteam_has_30_samples_and_report() -> None:
    report = json.loads(require_artifact("results/redteam.json", "T15").read_text(encoding="utf-8"))
    inj = Path(__file__).resolve().parents[2] / "data" / "demo" / "injection" / "injections.jsonl"
    assert sum(1 for line in inj.read_text(encoding="utf-8").splitlines() if line.strip()) >= 30
    assert report["n"] >= 30 and report["bands_lowered"] == 0
    assert {"echoed_before_checker", "echoed_after_checker", "checker_rejection_rate"} <= set(
        report
    )
