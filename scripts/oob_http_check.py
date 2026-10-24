"""Pre-demo check: the phone page and its real HTTP endpoints, against a running engine.

    make live                       # terminal 1
    make oob-check                  # terminal 2 (or scripts/satya.py oob-check)

It runs the same chain the approver's phone runs:
  health -> demo case -> POST /companion/oob -> GET /api/oob/inbox -> token
  -> GET /oob (the served page) -> GET /api/oob/request -> POST /api/oob/respond
     with "I did not request this" -> DENIED / HOLD.

It uses only fake demo data (`*.example`, `FAK...`, `9999...`). It does not start or stop a
session unless it had to start one; it answers its own test request as Rajesh, so it leaves no
pending request behind. Run it on the demo laptop before the judges arrive.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

import httpx

RAJESH = {
    "X-Demo-User": "emp_rajesh",
    "X-Demo-Role": "requester",
    "Content-Type": "application/json",
}
TOKEN_RE = re.compile(r"/oob/([A-Za-z0-9_\-]+)")
CASE = "case_demo_beneficiary_change"


def _step(name: str, fn: Any) -> Any:
    try:
        result = fn()
        print(f"  ok   {name}")
        return result
    except Exception as exc:  # noqa: BLE001 - the check must report, not traceback
        print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the OOB phone page over real HTTP")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    client = httpx.Client(base_url=args.base.rstrip("/"), timeout=15)
    print(f"OOB phone-page check against {args.base}")

    health = _step("health", lambda: client.get("/companion/health").json())
    assert health["status"] == "ok"
    assert health["policy_authority"] == "satyapan.policy"
    assert health["manual_only"] is True

    state = client.get("/companion/state").json()
    started = False
    if not state.get("session_id"):
        _step(
            "start a consented session",
            lambda: client.post(
                "/companion/session/start",
                json={"version": "1", "consent": True, "source": "user_selected_loopback"},
            ).raise_for_status(),
        )
        started = True

    _step(
        "demo case",
        lambda: client.post(
            "/companion/commands",
            json={
                "version": "1",
                "request_id": "req_oob_check",
                "type": "demo.replay",
                "payload": {"scenario": "beneficiary_change"},
            },
        ).raise_for_status(),
    )
    _step(
        "create an OOB request",
        lambda: client.post(
            "/companion/oob", json={"version": "1", "case_id": CASE}
        ).raise_for_status(),
    )
    inbox = _step("phone inbox", lambda: client.get("/api/oob/inbox", headers=RAJESH).json())
    assert isinstance(inbox, list) and inbox
    token = None
    for message in reversed(inbox):
        match = TOKEN_RE.search(str(message.get("body", "")))
        if match:
            token = match.group(1)
            break
    assert token, "no /oob/<token> link in the approver inbox"

    page = _step("served page", lambda: client.get("/oob").text)
    assert "/api/oob/respond" in page, "the page is not the one that calls /api/oob/*"

    request = _step(
        "exact question",
        lambda: client.get("/api/oob/request", params={"token": token}, headers=RAJESH).json(),
    )
    assert request["state"] == "pending"
    assert request["question"]
    print(f"       question: {request['question']}")

    answer = _step(
        "approver says not me",
        lambda: client.post(
            "/api/oob/respond",
            json={"token": token, "approve": False, "reason": "not_requested"},
            headers=RAJESH,
        ).json(),
    )
    assert answer["result"] == "DENIED"
    assert answer["case_band"] == "HOLD"
    assert answer.get("reason") == "not_requested"

    if started:
        _step(
            "stop the session we started",
            lambda: client.post(
                "/companion/session/stop", json={"version": "1"}
            ).raise_for_status(),
        )
    print(json.dumps({"result": "PASS", "band": answer["case_band"]}, indent=1))
    print("OOB phone-page check: OK")


if __name__ == "__main__":
    main()
