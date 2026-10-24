"""F03 acceptance: companion backend glue (calls, live fan-in, files, OOB, report pack).

Every test uses the fake demo world (`*.example`, `FAK...`, `9999...`). No network.
The companion may relay a policy band; it may never compute one or expose a raw score.
"""

from __future__ import annotations

import json
import re
from typing import Any

from satyapan.adapters.base import FakeTranscriber
from satyapan.contracts.live import VoiceWindowResult

FORBIDDEN = {
    "score",
    "scores",
    "confidence",
    "probability",
    "risk_score",
    "risk_band",
    "z_score",
}

CALL_TEXT = "Keep this between us. Transfer the payment to the new account and skip the approval."


# --------------------------------------------------------------------------- helpers
def _state(client: Any) -> Any:
    return client.app.state.satyapan


def _start_session(client: Any, source: str = "user_selected_loopback") -> str:
    response = client.post(
        "/companion/session/start",
        json={"version": "1", "consent": True, "source": source},
    )
    assert response.status_code == 200, response.text
    return response.json()["state"]["consent_id"]


def _start_call(client: Any, consent_id: str) -> dict[str, Any]:
    response = client.post(
        "/companion/calls/start",
        json={"version": "1", "source": "loopback", "consent_id": consent_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _events(client: Any) -> list[Any]:
    return _state(client).companion().bus.history()


def _of_type(client: Any, event_type: str) -> list[Any]:
    return [event for event in _events(client) if event.type.value == event_type]


def _assert_no_scores(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert str(key).lower() not in FORBIDDEN, f"raw score leaked at {path}.{key}"
            _assert_no_scores(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_scores(child, f"{path}[{index}]")


def _sse_events(response: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in response.text.split("\n\n"):
        data = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data:
            events.append(json.loads("\n".join(data)))
    return events


# --------------------------------------------------------------------------- calls
def test_calls_start_is_rejected_without_a_consented_session(client) -> None:
    response = client.post(
        "/companion/calls/start",
        json={"version": "1", "source": "loopback", "consent_id": "consent_missing"},
    )
    assert response.status_code == 403
    assert _events(client) == []


def test_calls_start_rejects_a_consent_id_that_is_not_active(client) -> None:
    _start_session(client)
    response = client.post(
        "/companion/calls/start",
        json={"version": "1", "source": "loopback", "consent_id": "consent_wrong"},
    )
    assert response.status_code == 403
    assert _of_type(client, "call.started") == []


def test_calls_start_and_stop_emit_lifecycle_events_without_scores(client) -> None:
    consent_id = _start_session(client)
    body = _start_call(client, consent_id)
    _assert_no_scores(body)
    assert body["call_id"].startswith("call_")
    assert body["case_id"].startswith("case_live_")
    started = [e for e in body["events"] if e["type"] == "call.started"]
    assert len(started) == 1
    assert started[0]["payload"]["call_id"] == body["call_id"]
    assert started[0]["payload"]["case_id"] == body["case_id"]

    stopped = client.post(
        "/companion/calls/stop",
        json={"version": "1", "call_id": body["call_id"]},
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["call_id"] == body["call_id"]
    assert [e["type"] for e in stopped.json()["events"]] == ["call.stopped"]
    assert _of_type(client, "call.stopped")
    assert _of_type(client, "alert.raised") == []
    _assert_no_scores(stopped.json())
    _assert_no_scores([e.model_dump(mode="json") for e in _events(client)])


# --------------------------------------------------------------------------- live fan-in
def test_live_chips_accumulate_and_the_policy_band_is_relayed_unchanged(client) -> None:
    state = _state(client)
    state.transcriber_override = FakeTranscriber([CALL_TEXT])
    consent_id = _start_session(client)
    body = _start_call(client, consent_id)
    call_id = body["call_id"]

    live_events = state.live().handle_chunk(call_id, 0, b"fake-audio", "audio/webm")
    assert [event.type for event in live_events if event.type == "band"] == ["band"]

    chips_events = _of_type(client, "live.chips")
    assert chips_events, "ask events must be fanned into the companion bus"
    codes = {chip.code for chip in chips_events[-1].payload.chips}
    assert {"A1", "A4", "A5"}.issubset(codes)
    assert all(chip.at_s is not None for chip in chips_events[-1].payload.chips)

    alerts = _of_type(client, "alert.raised")
    assert len(alerts) == 1
    policy_band = state.live().sessions[call_id].last_band
    assert alerts[0].payload.band == policy_band
    assert policy_band.value in {"VERIFY", "HOLD"}
    assert "ASK_SECRECY" in [code.value for code in alerts[0].payload.reason_codes]
    assert [action.id for action in alerts[0].payload.next_actions] == [
        "verify",
        "copy_reply",
        "open_notebook",
    ]
    assert alerts[0].payload.chips  # the alert repeats the chips it is about

    # Privacy: the transcript (the most sensitive part of a call) never crosses the boundary.
    blob = "".join(event.model_dump_json() for event in _events(client))
    assert CALL_TEXT not in blob
    _assert_no_scores([event.model_dump(mode="json") for event in _events(client)])


def test_voice_coverage_is_relayed_as_quality_only(client) -> None:
    state = _state(client)
    state.transcriber_override = FakeTranscriber(["hello"])
    consent_id = _start_session(client)
    call_id = _start_call(client, consent_id)["call_id"]
    live = state.live()
    live.start(call_id, "emp_priya") if call_id not in live.sessions else None

    window = VoiceWindowResult(
        call_id=call_id,
        window_index=0,
        t_start_s=0.0,
        t_end_s=5.0,
        score=0.0,
        speech_seconds=0.5,  # too short: inconclusive audio, never a "fake voice" conclusion
        model_version="demo",
    )
    live.handle_voice(call_id, [window])

    coverage = _of_type(client, "coverage.changed")
    assert coverage, "a voice label change must be relayed as coverage"
    assert coverage[-1].payload.coverage == "degraded"
    assert coverage[-1].payload.seal == "not_verified"
    _assert_no_scores([event.model_dump(mode="json") for event in _events(client)])


# --------------------------------------------------------------------------- OOB
def _token_from_outbox(state: Any) -> str:
    body = state.in_app_mailer.outbox[-1]["body"]
    match = re.search(r"/oob/([A-Za-z0-9_\-]+)", body)
    assert match is not None, body
    return match.group(1)


def test_oob_uses_the_directory_contact_and_emits_oob_sent(client) -> None:
    client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_f03_replay",
            "type": "demo.replay",
            "payload": {"scenario": "beneficiary_change"},
        },
    )
    response = client.post(
        "/companion/oob", json={"version": "1", "case_id": "case_demo_beneficiary_change"}
    )
    assert response.status_code == 200, response.text
    ticket = response.json()
    _assert_no_scores(ticket)
    # Rajesh is the first senior approver in the directory. Nothing came from message text.
    assert ticket["approver_name"] == "Rajesh Iyer"
    assert ticket["channel"] == "console"
    assert ticket["oob_id"].startswith("oob_")
    state = _state(client)
    assert state.in_app_mailer.outbox[-1]["to"] == "rajesh@demo-industries.example"

    sent = _of_type(client, "oob.sent")
    assert len(sent) == 1
    assert sent[0].payload.ticket is not None
    assert sent[0].payload.ticket.oob_id == ticket["oob_id"]
    assert sent[0].payload.oob is not None
    assert sent[0].payload.oob.approver_name == "Rajesh Iyer"


def test_oob_not_requested_emits_result_and_case_updated(client) -> None:
    client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_f03_replay",
            "type": "demo.replay",
            "payload": {"scenario": "beneficiary_change"},
        },
    )
    ticket = client.post(
        "/companion/oob", json={"version": "1", "case_id": "case_demo_beneficiary_change"}
    ).json()
    token = _token_from_outbox(_state(client))
    response = client.post(
        "/oob/respond",
        json={"token": token, "approve": False, "reason": "not_requested"},
        headers={"X-Demo-User": "emp_rajesh", "X-Demo-Role": "requester"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"] == "DENIED"
    assert response.json()["reason"] == "not_requested"

    results = _of_type(client, "oob.result")
    assert len(results) == 1
    assert results[0].payload.oob is not None
    assert results[0].payload.oob.outcome == "not_requested"
    assert results[0].payload.band == "HOLD"
    updated = _of_type(client, "case.updated")
    assert updated
    assert updated[-1].payload.case_id == ticket["case_id"]
    _assert_no_scores([event.model_dump(mode="json") for event in _events(client)])


# --------------------------------------------------------------------------- files
def test_files_requires_consent_and_relays_the_policy_decision(client) -> None:
    refused = client.post(
        "/companion/files",
        files={"file": ("note.txt", b"Share the OTP", "text/plain")},
    )
    assert refused.status_code == 403

    _start_session(client, source="user_selected_email")
    response = client.post(
        "/companion/files",
        files={"file": ("note.txt", b"Keep this between us and share the OTP", "text/plain")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] is True
    assert body["band_set_by_companion"] is False
    assert body["evidence_id"].startswith("ev_")
    assert set(body["info_codes"]) >= {"ASK_SECRECY", "ASK_CREDENTIAL"}

    updated = _of_type(client, "case.updated")
    assert updated, "file intake must emit case.updated"
    payload = updated[-1].payload
    saved = _state(client).repo.get(payload.case_id)
    assert saved is not None
    assert saved.decision is not None
    assert payload.band == saved.decision.band  # relayed, not computed
    _assert_no_scores(body)
    _assert_no_scores([event.model_dump(mode="json") for event in _events(client)])


# --------------------------------------------------------------------------- report pack
def test_report_pack_is_five_manual_only_drafts(client) -> None:
    client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_f03_replay",
            "type": "demo.replay",
            "payload": {"scenario": "urgent_bypass"},
        },
    )
    response = client.get("/companion/report-pack", params={"case_id": "case_demo_urgent_bypass"})
    assert response.status_code == 200, response.text
    pack = response.json()
    assert pack["version"] == "2"
    assert pack["submission"] == "MANUAL_ONLY"
    assert pack["auto_submit"] is False
    ids = [section["id"] for section in pack["sections"]]
    assert ids == [
        "helpline_1930",
        "bank_fraud_desk",
        "ncrp_portal",
        "cert_in",
        "bsa_s63_part_a",
    ]
    assert all(section["status"] == "DRAFT_REQUIRES_HUMAN_REVIEW" for section in pack["sections"])
    helpline = pack["sections"][0]
    assert helpline["open_url"] == "tel:1930"
    # A missing UTR is never invented.
    utr = next(field for field in helpline["fields"] if field["label"] == "UTR")
    assert "Not provided" in utr["value"]
    bsa = pack["sections"][-1]
    assert any(field["label"].startswith("SHA-256") for field in bsa["fields"])
    _assert_no_scores(pack)


def test_report_pack_unknown_case_is_404(client) -> None:
    response = client.get("/companion/report-pack", params={"case_id": "case_missing"})
    assert response.status_code == 404


# --------------------------------------------------------------------------- oracle abuse
def test_no_companion_response_or_sse_event_contains_a_raw_score(client) -> None:
    consent_id = _start_session(client)
    call = _start_call(client, consent_id)
    client.post("/companion/calls/stop", json={"version": "1", "call_id": call["call_id"]})
    client.post("/companion/oob", json={"version": "1", "case_id": call["case_id"]})
    report = client.get("/companion/report-pack", params={"case_id": call["case_id"]})
    assert report.status_code == 200

    _assert_no_scores(client.get("/companion/state").json())
    _assert_no_scores(call)
    _assert_no_scores(report.json())
    _assert_no_scores([event.model_dump(mode="json") for event in _events(client)])
    _assert_no_scores(_sse_events(client.get("/companion/events", params={"replay_only": "true"})))


def test_a_personal_call_gets_consumer_actions_not_an_approver(client, monkeypatch) -> None:
    """No company approver (SATYAPAN_PROFILE=personal or an empty directory): the alert tells
    the person what to do themselves. The band is still the policy's, unchanged."""
    monkeypatch.setenv("SATYAPAN_PROFILE", "personal")
    state = _state(client)
    state.transcriber_override = FakeTranscriber([CALL_TEXT])
    call_id = _start_call(client, _start_session(client))["call_id"]
    state.live().handle_chunk(call_id, 0, b"fake-audio", "audio/webm")
    alert = _of_type(client, "alert.raised")[0].payload
    assert alert.band == state.live().sessions[call_id].last_band
    assert [a.id for a in alert.next_actions] == ["copy_reply", "call_1930", "open_check"]
    assert alert.approver_name is None
    assert alert.headline.startswith(("Stop:", "Don't act yet"))
    assert "call back on a number you already have" in alert.explanation
    _assert_no_scores([event.model_dump(mode="json") for event in _events(client)])
