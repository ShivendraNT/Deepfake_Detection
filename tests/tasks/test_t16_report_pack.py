"""T16 acceptance: UTR-first report pack, manual only, both variants."""

from __future__ import annotations

import pytest

from satyapan.contracts import CaseStatus
from satyapan.report.pack import ReportNotUnlockedError, build_report_pack, format_inr, render_html
from tests.helpers import DEMO_DAY, api_ok

pytestmark = pytest.mark.task("T16")


@pytest.mark.parametrize(
    ("n", "s"),
    [
        (4850000, "₹48,50,000"),
        (620000, "₹6,20,000"),
        (999, "₹999"),
        (100000, "₹1,00,000"),
        (12345678, "₹1,23,45,678"),
    ],
)
def test_format_inr(n: int, s: str) -> None:
    assert format_inr(n) == s


def test_money_sent_pack_is_utr_first(repo, master) -> None:
    case = repo.get("case_s12")
    pack = build_report_pack(case, master, [], "MONEY_SENT", "emp_arjun", DEMO_DAY)
    first_line = pack.call_script_1930.splitlines()[0]
    assert "FAKEUTR620001" in first_line and "₹6,20,000" in first_line
    assert pack.facts.utr == "FAKEUTR620001"
    assert (
        pack.bank_email.subject.startswith("URGENT: fraud")
        and "FAKEUTR620001" in pack.bank_email.subject
    )
    labels = [f.label for f in pack.ncrp_draft]
    assert labels[:2] == ["Incident date/time", "Category"]
    assert len(pack.evidence_index) == len(case.evidence)
    assert {i.sha256 for i in pack.evidence_index} == {e.sha256 for e in case.evidence}
    assert pack.submission == "MANUAL_ONLY"


def test_attempted_requires_suspected(repo, master) -> None:
    case = repo.get("case_s07")  # OPEN
    with pytest.raises(ReportNotUnlockedError):
        build_report_pack(case, master, [], "ATTEMPTED", "emp_arjun", DEMO_DAY)
    sus = case.model_copy(update={"status": CaseStatus.SUSPECTED_FRAUD})
    pack = build_report_pack(sus, master, [], "ATTEMPTED", "emp_arjun", DEMO_DAY)
    assert pack.call_script_1930 is None and "99997777009917" in pack.bank_email.body


def test_money_sent_requires_confirmed_and_utr(repo, master) -> None:
    case = repo.get("case_s06").model_copy(update={"status": CaseStatus.SUSPECTED_FRAUD})
    with pytest.raises(ReportNotUnlockedError):
        build_report_pack(case, master, [], "MONEY_SENT", "emp_arjun", DEMO_DAY)


def test_html_escapes_attacker_text(repo, master) -> None:
    case = repo.get("case_s12")
    txn = case.txn.model_copy(update={"beneficiary_name": "<script>alert(1)</script>"})
    pack = build_report_pack(
        case.model_copy(update={"txn": txn}), master, [], "MONEY_SENT", "emp_arjun", DEMO_DAY
    )
    html = render_html(pack)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert html.index("FAKEUTR620001") < html.index("NCRP")


def test_api_report_html(client) -> None:
    h = {"X-Demo-User": "emp_arjun", "X-Demo-Role": "checker"}
    r = api_ok(
        client.get("/cases/case_s12/report?variant=MONEY_SENT&format=html", headers=h), "T16"
    )
    assert r.status_code == 200 and "FAKEUTR620001" in r.text
    maker = {"X-Demo-User": "emp_priya", "X-Demo-Role": "maker"}
    assert client.get("/cases/case_s12/report", headers=maker).status_code == 403
