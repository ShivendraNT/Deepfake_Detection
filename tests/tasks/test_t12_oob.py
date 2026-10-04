"""T12 acceptance: OOB-Confirm token binding, deny -> HOLD + SUSPECTED_FRAUD, replay/expiry."""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta

import pytest

from satyapan.adapters.base import InAppMailer
from satyapan.contracts import Band, CaseStatus, OOBResult
from satyapan.policy import apply_decision, decide
from satyapan.workflows.oob import (
    OOBService,
    TokenExpiredError,
    TokenReplayError,
    UnknownTokenError,
    WrongResponderError,
    beneficiary_hash,
    binding_hash,
    oob_message,
)
from tests.helpers import DEMO_DAY, api_ok

pytestmark = pytest.mark.task("T12")


def _create(repo, master):  # type: ignore[no-untyped-def]
    mailer = InAppMailer()
    svc = OOBService(mailer=mailer)
    case = repo.get("case_s06")
    req, token = svc.create(case, master.employee("emp_rajesh"), "Priya", DEMO_DAY)
    return svc, mailer, case, req, token


def test_binding_and_token_hash(repo, master) -> None:
    _, _, case, req, token = _create(repo, master)
    t = case.txn
    bh = beneficiary_hash(t.account_number, t.ifsc, t.upi_id)
    assert req.binding_hash == binding_hash(case.id, t.amount_inr, bh, req.nonce)
    assert req.token_sha256 == hashlib.sha256(token.encode()).hexdigest()
    assert token not in req.model_dump_json()
    assert req.expires_at - req.created_at == timedelta(minutes=10)


def test_binding_changes_with_amount() -> None:
    bh = beneficiary_hash("99998888004821", "FAKM0000482", None)
    assert binding_hash("case_1", 100, bh, "n") != binding_hash("case_1", 101, bh, "n")


def test_message_and_mail(repo, master) -> None:
    _, mailer, _, req, token = _create(repo, master)
    assert "₹48,50,000" in req.message_text and "••••4821" in req.message_text
    assert mailer.outbox[0]["to"] == "rajesh@demo-industries.example"
    assert f"/oob/{token}" in mailer.outbox[0]["body"]


def test_live_call_message_without_txn(repo, master) -> None:
    from tests.helpers import make_case

    msg = oob_message(make_case(kind="LIVE_CALL"), master.employee("emp_rajesh"), "Priya")
    assert "call" in msg.lower()


def test_deny_turns_case_hold_and_suspected(repo, master) -> None:
    svc, _, case, _, token = _create(repo, master)
    res = svc.respond(token, False, "emp_rajesh", DEMO_DAY + timedelta(minutes=1))
    assert res.result == OOBResult.DENIED and res.spent
    case = case.model_copy(update={"oob": res})
    case = apply_decision(case, decide(case, master))
    assert case.decision.band == Band.HOLD and case.status == CaseStatus.SUSPECTED_FRAUD


def test_replay_rejected(repo, master) -> None:
    svc, _, _, _, token = _create(repo, master)
    svc.respond(token, True, "emp_rajesh", DEMO_DAY)
    with pytest.raises(TokenReplayError):
        svc.respond(token, True, "emp_rajesh", DEMO_DAY)


def test_expired(repo, master) -> None:
    svc, _, _, _, token = _create(repo, master)
    with pytest.raises(TokenExpiredError):
        svc.respond(token, True, "emp_rajesh", DEMO_DAY + timedelta(minutes=11))


def test_wrong_responder_and_unknown(repo, master) -> None:
    svc, _, _, _, token = _create(repo, master)
    with pytest.raises(WrongResponderError):
        svc.respond(token, True, "emp_priya", DEMO_DAY)
    with pytest.raises(UnknownTokenError):
        svc.respond("not-a-token", True, "emp_rajesh", DEMO_DAY)


def test_api_flow(client) -> None:
    maker = {"X-Demo-User": "emp_priya", "X-Demo-Role": "maker"}
    cfo = {"X-Demo-User": "emp_rajesh", "X-Demo-Role": "requester"}
    r = api_ok(
        client.post(
            "/cases/case_s06/oob", json={"requester_employee_id": "emp_rajesh"}, headers=maker
        ),
        "T12",
    )
    assert r.status_code == 200
    inbox = client.get("/oob/inbox", headers=cfo).json()
    token = re.search(r"/oob/([A-Za-z0-9_\-]+)", inbox[-1]["body"]).group(1)
    r = client.post("/oob/respond", json={"token": token, "approve": False}, headers=cfo)
    assert r.json()["result"] == "DENIED"
    case = client.get("/cases/case_s06", headers=maker).json()
    assert case["decision"]["band"] == "HOLD" and case["status"] == "SUSPECTED_FRAUD"
