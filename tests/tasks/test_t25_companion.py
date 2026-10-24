"""T25 acceptance: Desktop Guardian Companion contract, safety and desktop-integrity tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.task("T25")

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = {
    "score",
    "scores",
    "confidence",
    "probability",
    "risk_score",
    "risk_band",
    "z_score",
}


# --------------------------------------------------------------------------- helpers
def _start(client, source: str = "demo_replay", consent: bool = True, label: str | None = None):
    body: dict[str, Any] = {"version": "1", "consent": consent, "source": source}
    if label:
        body["label"] = label
    return client.post("/companion/session/start", json=body)


def _command(client, command_type: str, payload: dict[str, Any] | None = None):
    return client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_test_001",
            "type": command_type,
            "payload": payload or {},
        },
    )


def _sse_events(response) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in response.text.split("\n\n"):
        data_lines = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data_lines:
            events.append(json.loads("\n".join(data_lines)))
    return events


def _assert_no_scores(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert str(key).lower() not in FORBIDDEN, f"raw score leaked through {key}"
            _assert_no_scores(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_scores(child)


# --------------------------------------------------------------------------- docs
def test_t25_spec_exists() -> None:
    """Verify that the T25 specification and grand finals architecture are present."""
    assert Path("docs/tasks/T25-desktop-companion.md").exists()
    assert Path("docs/GRAND_FINALS_ARCHITECTURE.md").exists()


# --------------------------------------------------------------------------- health/state
def test_health_declares_policy_authority_and_manual_only(client) -> None:
    body = client.get("/companion/health").json()
    assert body["status"] == "ok"
    assert body["policy_authority"] == "satyapan.policy"
    assert body["manual_only"] is True
    assert body["raw_scores_visible"] is False
    assert body["default_mode"] == "SLEEP"


def test_default_state_is_sleep_dnd_and_not_monitoring(client) -> None:
    body = client.get("/companion/state").json()
    assert body["mode"] == "SLEEP"
    assert body["monitoring"] is False
    assert body["hidden"] is False
    assert body["session_id"] is None
    assert body["raw_scores_visible"] is False
    assert body["manual_only"] is True
    assert body["policy_authority"] == "satyapan.policy"


def test_session_start_requires_explicit_consent(client) -> None:
    response = _start(client, consent=False)
    assert response.status_code == 403
    assert client.get("/companion/state").json()["mode"] == "SLEEP"


def test_consented_loopback_session_turns_monitoring_on(client) -> None:
    response = _start(client, source="user_selected_loopback", label="Meet tab")
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["mode"] == "ACTIVE"
    assert body["state"]["monitoring"] is True
    assert body["state"]["consent_id"].startswith("consent_")
    assert body["state"]["session_id"].startswith("session_")
    assert body["state"]["expires_at"] is not None
    event = body["events"][0]
    assert event["version"] == "1"
    assert event["type"] == "session.started"
    assert event["payload"]["monitoring"] is True


def test_selected_email_session_is_not_continuous_monitoring(client) -> None:
    body = _start(client, source="user_selected_email").json()
    assert body["state"]["monitoring"] is False
    assert body["state"]["mode"] == "ACTIVE"


def test_stop_session_fails_closed_and_is_idempotent(client) -> None:
    assert _start(client, source="user_selected_microphone").status_code == 200
    stopped = client.post("/companion/session/stop")
    assert stopped.status_code == 200
    assert stopped.json()["state"]["mode"] == "SLEEP"
    assert stopped.json()["state"]["monitoring"] is False
    again = client.post("/companion/session/stop")
    assert again.status_code == 200
    assert again.json()["events"] == []


def test_hide_releases_capture_before_hiding(client) -> None:
    assert _start(client, source="user_selected_loopback").status_code == 200
    body = _command(client, "ui.hide").json()
    assert body["state"]["hidden"] is True
    assert body["state"]["monitoring"] is False
    assert body["state"]["session_id"] is None
    assert body["state"]["mode"] == "SLEEP"


def test_disable_releases_resources(client) -> None:
    assert _start(client, source="user_selected_loopback").status_code == 200
    body = _command(client, "ui.disable").json()
    assert body["state"]["mode"] == "DISABLED"
    assert body["state"]["hidden"] is True
    assert body["state"]["monitoring"] is False


# --------------------------------------------------------------------------- band authority
def test_command_cannot_supply_a_band_top_level(client) -> None:
    response = client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_band_top",
            "type": "session.sleep",
            "band": "HOLD",
        },
    )
    assert response.status_code == 422


def test_command_payload_cannot_supply_a_band_or_score(client) -> None:
    for key, value in (("band", "HOLD"), ("score", 0.99), ("confidence", 0.9)):
        response = client.post(
            "/companion/commands",
            json={
                "version": "1",
                "request_id": "req_band_payload",
                "type": "session.sleep",
                "payload": {key: value},
            },
        )
        assert response.status_code == 422, key


def test_alert_band_is_the_policy_engine_decision(client) -> None:
    from satyapan.api.companion.service import DEMO_SCENARIOS
    from satyapan.policy.engine import decide

    body = _command(client, "demo.replay", {"scenario": "beneficiary_change"}).json()
    alerts = [e for e in body["events"] if e["type"] == "alert.raised"]
    assert len(alerts) == 1
    alert = alerts[0]["payload"]
    assert alert["band"] in {"PASS", "VERIFY", "HOLD"}

    app_state = client.app.state.satyapan
    service = app_state.companion()
    case = service.build_demo_case(DEMO_SCENARIOS["beneficiary_change"])
    expected = decide(case, app_state.master)
    assert alert["band"] == expected.band.value
    assert alert["band"] == "VERIFY"  # new payee above de-minimis + payee-change ask
    assert "ASK_PAYEE_CHANGE" in alert["reason_codes"]


def test_urgent_bypass_replay_reaches_hold_through_policy(client) -> None:
    body = _command(client, "demo.replay", {"scenario": "urgent_bypass"}).json()
    alert = [e for e in body["events"] if e["type"] == "alert.raised"][0]["payload"]
    assert alert["band"] == "HOLD"
    assert {"ASK_CREDENTIAL", "ASK_REMOTE_ACCESS"}.issubset(set(alert["reason_codes"]))


def test_unknown_demo_scenario_is_rejected(client) -> None:
    response = _command(client, "demo.replay", {"scenario": "not_a_scenario"})
    assert response.status_code == 400


def test_demo_replay_is_visibly_labeled_and_not_live(client) -> None:
    body = _command(client, "demo.replay").json()
    alert = [e for e in body["events"] if e["type"] == "alert.raised"][0]["payload"]
    assert alert["demo"] is True
    assert alert["mode_label"] == "DEMO REPLAY — NOT LIVE CAPTURE"
    assert alert["monitoring"] is False
    assert body["state"]["source"] == "demo_replay"


# --------------------------------------------------------------------------- no raw scores
def test_no_raw_scores_in_state_or_events(client) -> None:
    body = _command(client, "demo.replay").json()
    _assert_no_scores(body)
    state = client.get("/companion/state").json()
    _assert_no_scores(state)


def test_payload_model_rejects_score_fields() -> None:
    from satyapan.api.companion.models import CompanionPayload

    with pytest.raises(ValidationError):
        CompanionPayload(
            state="ACTIVE",
            mascot_mood="attentive",
            headline="x",
            score=0.99,
        )


def test_event_version_is_pinned() -> None:
    from satyapan.api.companion.models import CompanionEvent

    with pytest.raises(ValidationError):
        CompanionEvent(
            version="2",
            type="state.changed",
            payload={
                "state": "SLEEP",
                "mascot_mood": "sleepy",
                "headline": "x",
            },
        )


def test_bounded_bus_replays_and_drops_old_history() -> None:
    from satyapan.api.companion.bus import CompanionBus
    from satyapan.api.companion.models import CompanionEvent, CompanionPayload

    bus = CompanionBus(history_capacity=2)
    for _ in range(3):
        bus.publish(
            CompanionEvent(
                type="state.changed",
                payload=CompanionPayload(state="SLEEP", mascot_mood="sleepy", headline="resting"),
            )
        )
    history = bus.history()
    assert len(history) == 2
    assert history[-1].event_id == "evt_00000003"
    assert bus.history("evt_00000002")[-1].event_id == "evt_00000003"


# --------------------------------------------------------------------------- SSE
def test_sse_replay_only_drains_history_and_closes(client) -> None:
    _command(client, "demo.replay")
    response = client.get("/companion/events", params={"replay_only": "true"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(response)
    assert len(events) >= 2
    assert [e["event_id"] for e in events] == sorted(e["event_id"] for e in events)
    assert all(e["version"] == "1" for e in events)
    _assert_no_scores(events)


def test_sse_last_event_id_resumes_after_that_event(client) -> None:
    _command(client, "demo.replay")
    all_events = _sse_events(client.get("/companion/events", params={"replay_only": "true"}))
    first_id = all_events[0]["event_id"]
    resumed = _sse_events(
        client.get(
            "/companion/events",
            params={"replay_only": "true"},
            headers={"Last-Event-ID": first_id},
        )
    )
    assert [e["event_id"] for e in resumed] == [e["event_id"] for e in all_events[1:]]


def test_sse_replay_only_is_empty_when_nothing_happened(client) -> None:
    response = client.get("/companion/events", params={"replay_only": "true"})
    assert response.status_code == 200
    assert _sse_events(response) == []


# --------------------------------------------------------------------------- evidence
def test_evidence_requires_consent_and_an_active_session(client) -> None:
    body = {
        "version": "1",
        "request_id": "req_ev_001",
        "source": "user_selected_email",
        "consent": False,
        "evidence_id": "ev_text_001",
        "text": "share the OTP",
    }
    assert client.post("/companion/evidence", json=body).status_code == 403
    body["consent"] = True
    assert client.post("/companion/evidence", json=body).status_code == 400


def test_evidence_intake_extracts_asks_without_setting_a_band(client) -> None:
    _start(client, source="user_selected_email")
    response = client.post(
        "/companion/evidence",
        json={
            "version": "1",
            "request_id": "req_ev_002",
            "source": "user_selected_email",
            "consent": True,
            "evidence_id": "ev_text_002",
            "text": "Keep this between us, install AnyDesk and share the OTP today.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["band_set_by_companion"] is False
    assert body["reason_codes"] == []
    assert body["ask_count"] >= 2
    assert "ASK_CREDENTIAL" in body["info_codes"]
    payloads = [e["payload"] for e in body["events"]]
    assert all(p["band"] is None for p in payloads)
    assert any("not a policy band" in p["explanation"] for p in payloads)


# --------------------------------------------------------------------------- drafts
def test_unknown_case_draft_is_404(client) -> None:
    response = client.post(
        "/companion/drafts",
        json={"version": "1", "kind": "helpline_1930", "case_id": "case_does_not_exist"},
    )
    assert response.status_code == 404


def test_section63_draft_is_human_review_only(client) -> None:
    body = client.post(
        "/companion/drafts",
        json={"version": "1", "kind": "section63", "case_id": "case_s01"},
    ).json()
    assert body["status"] == "DRAFT_REQUIRES_HUMAN_REVIEW"
    assert body["submission"] == "MANUAL_ONLY"
    assert body["auto_submit"] is False
    assert body["fields"]["prescribed_form_version"] == "COUNSEL_VERIFIED_VERSION_REQUIRED"
    assert any("Draft only" in d for d in body["disclaimers"])
    assert client.get("/companion/state").json()["mode"] == "SCRIBE"


def test_1930_draft_never_invents_a_utr_and_stays_manual(client) -> None:
    body = client.post(
        "/companion/drafts",
        json={"version": "1", "kind": "helpline_1930", "case_id": "case_s01"},
    ).json()
    assert body["submission"] == "MANUAL_ONLY"
    assert body["fields"]["utr"] is None
    assert body["fields"]["utr_missing"] is True
    assert body["fields"]["loss_amount_inr"] is None
    assert body["fields"]["pronunciation_helper"] == "1930 → one nine three zero"
    assert body["auto_submit"] is False


# --------------------------------------------------------------------------- workspace
def test_workspace_masks_payee_and_hides_raw_scores(client) -> None:
    cases = client.get("/companion/cases").json()
    assert cases
    case_id = cases[0]["case_id"]
    body = client.get("/companion/workspace", params={"case_id": case_id}).json()
    assert body["case_id"] == case_id
    assert body["raw_scores_visible"] is False
    assert body["manual_only"] is True
    assert body["policy_authority"] == "satyapan.policy"
    assert body["payee_masked"] is None or "••••" in body["payee_masked"]
    assert body["payee_masked"] is None or "99990000001111" not in body["payee_masked"]
    _assert_no_scores(body)


def test_workspace_follows_the_latest_demo_case(client) -> None:
    _command(client, "demo.replay", {"scenario": "urgent_bypass"})
    body = client.get("/companion/workspace").json()
    assert body["case_id"] == "case_demo_urgent_bypass"
    assert body["band"] == "HOLD"


def test_audit_feed_is_checker_security_only(client) -> None:
    assert _command(client, "ui.hide").status_code == 200
    assert client.get("/companion/audit").status_code == 403
    response = client.get(
        "/companion/audit",
        headers={"X-Demo-User": "emp_meera", "X-Demo-Role": "security"},
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert any(row["action"] == "ui.hide" for row in rows)
    assert response.json()["raw_scores_visible"] is False


# --------------------------------------------------------------------------- desktop integrity
def _desktop(path: str) -> str:
    file = ROOT / "desktop" / path
    assert file.exists(), f"missing desktop file: {path}"
    return file.read_text(encoding="utf-8")


def test_desktop_package_and_build_config_exist() -> None:
    package = json.loads(_desktop("package.json"))
    assert "dev" in package["scripts"]
    assert "build" in package["scripts"]
    assert "electron" in {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    assert "framer-motion" in package["dependencies"]
    assert (ROOT / "desktop" / "electron.vite.config.ts").exists()
    assert (ROOT / "desktop" / "tailwind.config.cjs").exists()


def test_electron_window_is_frameless_transparent_and_sandboxed() -> None:
    main = _desktop("main/index.ts") + _desktop("main/windows.ts")
    assert "transparent: true" in main
    assert "frame: false" in main
    assert "alwaysOnTop" in main
    assert "contextIsolation: true" in main
    assert "nodeIntegration: false" in main
    assert "sandbox: true" in main
    assert "nodeIntegration: true" not in main


def test_preload_uses_a_narrow_typed_bridge() -> None:
    preload = _desktop("preload/index.ts")
    assert "contextBridge.exposeInMainWorld" in preload
    assert '"satyapan"' in preload or "'satyapan'" in preload
    assert "ipcRenderer.on" in preload
    assert "nodeIntegration" not in preload


def test_main_fails_closed_on_hide_and_quit() -> None:
    main = _desktop("main/index.ts") + _desktop("main/ipc.ts") + _desktop("main/tray.ts")
    assert "session/stop" in main, "hiding/quitting must stop the consented session"
    assert "before-quit" in main


def test_renderer_has_mascot_consent_and_workspace() -> None:
    app = _desktop("renderer/src/App.tsx")
    assert "Companion" in app
    assert "Workspace" in app
    assert (ROOT / "desktop" / "renderer" / "src" / "companion" / "ConsentCard.tsx").exists()
    assert (ROOT / "desktop" / "renderer" / "src" / "companion" / "Mascot.tsx").exists()
    assert (ROOT / "desktop" / "renderer" / "src" / "workspace" / "Workspace.tsx").exists()


def test_renderer_has_labeled_replay_and_mockable_clients() -> None:
    mock = _desktop("renderer/src/companion/mockClient.ts")
    assert "DEMO REPLAY — NOT LIVE CAPTURE" in mock
    assert "CaptureSource" in _desktop("renderer/src/companion/CaptureSource.ts")
    assert "ReportDraftClient" in _desktop("renderer/src/companion/ReportDraftClient.ts")


def test_desktop_has_no_real_bank_or_person_data() -> None:
    blob = "\n".join(
        _desktop(path)
        for path in (
            "renderer/src/companion/mockClient.ts",
            "renderer/src/App.tsx",
            "main/index.ts",
        )
    )
    assert "FAK" in blob or "demo" in blob.lower()
    assert "@gmail.com" not in blob
