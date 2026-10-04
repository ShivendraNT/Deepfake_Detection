"""T01 acceptance: skeleton, contracts, fixtures, mock API. (DONE — pre-implemented.)"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.task("T01")

MAKER = {"X-Demo-User": "emp_priya", "X-Demo-Role": "maker"}
CHECKER = {"X-Demo-User": "emp_arjun", "X-Demo-Role": "checker"}


def test_health(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_get_cases_returns_12_fixtures(client) -> None:
    cases = client.get("/cases").json()
    assert len(cases) == 12
    assert {c["band"] for c in cases} == {"PASS", "VERIFY", "HOLD"}


def test_case_view_maker_has_no_scores(client) -> None:
    case = client.get("/cases/case_s06", headers=MAKER).json()
    assert case["decision"]["band"] == "HOLD"
    assert all(s["score"] is None for s in case["signals"])


def test_case_view_checker_has_scores(client) -> None:
    case = client.get("/cases/case_s06", headers=CHECKER).json()
    assert any(s["score"] is not None for s in case["signals"])


def test_unknown_case_404(client) -> None:
    assert client.get("/cases/case_nope", headers=MAKER).status_code == 404


def test_wrong_role_rejected(client) -> None:
    r = client.get(
        "/cases/case_s01", headers={"X-Demo-User": "emp_priya", "X-Demo-Role": "checker"}
    )
    assert r.status_code == 403


def test_create_case_runs_policy(client) -> None:
    body = {
        "title": "New payee, large",
        "kind": "PAYMENT",
        "txn": {
            "id": "txn_new1",
            "vendor_id": None,
            "beneficiary_name": "Unknown Traders",
            "account_number": "99991234567890",
            "ifsc": "FAKZ0000001",
            "amount_inr": 75000,
            "rail": "NEFT",
            "created_by": "emp_priya",
            "created_at": "2026-10-05T11:00:00+05:30",
        },
    }
    r = client.post("/cases", json=body, headers=MAKER)
    assert r.status_code == 201
    d = r.json()["decision"]
    assert d["band"] == "VERIFY" and d["action_type"] == "N2"


def test_not_implemented_routes_return_501_with_task_id(client) -> None:
    r = client.get("/cases/case_s12/report?variant=MONEY_SENT", headers=CHECKER)
    if r.status_code == 501:
        assert r.json()["task"] == "T16"
    else:  # T16 done
        assert r.status_code == 200


def test_vendors_and_employees(client) -> None:
    assert len(client.get("/vendors").json()) == 5
    names = {e["employee_id"] for e in client.get("/employees").json()}
    assert {"emp_priya", "emp_arjun", "emp_rajesh", "emp_meera", "emp_sunil"} <= names


def test_custody_endpoint(client) -> None:
    r = client.get("/cases/case_s01/custody").json()
    assert r["chain_ok"] is True
