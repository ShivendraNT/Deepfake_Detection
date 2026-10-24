"""Finale: real live calls (local speech, phrasebook, cues), Screen Guard text checks, the
approver phone page, golden-hour report options and the expert policy trace.

Fake demo world only (`*.example`, `FAK...`, `9999...`). No network, no model weights, no media
files in the repo: WAV bytes are synthesised in memory and replay files go to `tmp_path`.
"""

from __future__ import annotations

import io
import math
import re
import struct
import wave
from dataclasses import dataclass
from typing import Any

import pytest

from satyapan.adapters.base import FakeTranscriber, TranscriptResult
from satyapan.adapters.transcribe_local import (
    UnavailableTranscriber,
    build_transcriber,
    clean_text,
    decode_wav,
)
from satyapan.asks.extractor import extract_asks
from satyapan.asks.lexicon import LEXICON_VERSION
from satyapan.asks.phrasebook import extract_cues, extract_live_asks
from satyapan.context import strip_context

FORBIDDEN = {"score", "scores", "confidence", "probability", "risk_score", "z_score"}

SCAM_LINE = "Don't involve Rajesh in this, it stays between us. Pay into the new account today."
CUE_LINE = "I'm stuck in a board meeting, I can't talk long. It is 48 lakh rupees."


# --------------------------------------------------------------------------- helpers
def _state(client: Any) -> Any:
    return client.app.state.satyapan


def _start_session(client: Any) -> str:
    response = client.post(
        "/companion/session/start",
        json={"version": "1", "consent": True, "source": "user_selected_loopback"},
    )
    assert response.status_code == 200, response.text
    consent_id: str = response.json()["state"]["consent_id"]
    return consent_id


def _start_call(client: Any, consent_id: str, **extra: Any) -> dict[str, Any]:
    body = {"version": "1", "source": "loopback", "consent_id": consent_id, **extra}
    response = client.post("/companion/calls/start", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def _events(client: Any, event_type: str) -> list[Any]:
    history = _state(client).companion().bus.history()
    return [event for event in history if event.type.value == event_type]


def _assert_no_scores(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert str(key).lower() not in FORBIDDEN, f"raw score leaked at {path}.{key}"
            _assert_no_scores(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_scores(child, f"{path}[{index}]")


def _wav(seconds: float, rate: int, channels: int = 1, width: int = 2) -> bytes:
    frames = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        if width == 2:
            samples = [int(8000 * math.sin(2 * math.pi * 220 * i / rate)) for i in range(frames)]
            data = b"".join(struct.pack("<" + "h" * channels, *([s] * channels)) for s in samples)
        else:
            data = bytes([128] * frames * channels)
        wav.writeframes(data)
    return buf.getvalue()


@dataclass
class RaisingTranscriber:
    error: Exception

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        raise self.error


# --------------------------------------------------------------------------- speech engine
def test_decode_wav_resamples_to_16k_mono() -> None:
    samples = decode_wav(_wav(0.5, 8000, channels=2))
    assert samples.dtype.name == "float32"
    assert abs(samples.size - 8000) <= 1  # 0.5 s at 16 kHz
    assert 0.1 < float(abs(samples).max()) <= 1.0


def test_decode_wav_rejects_non_pcm16_and_garbage() -> None:
    with pytest.raises(ValueError):
        decode_wav(b"not a wav at all")
    with pytest.raises(ValueError):
        decode_wav(_wav(0.1, 16000, width=1))


def test_clean_text_drops_whisper_hallucinations_only() -> None:
    assert clean_text("Thank you.") == ""
    assert clean_text("  Thanks for watching ") == ""
    assert clean_text("[Music]") == ""
    assert clean_text("  Thank you   for the   invoice ") == "Thank you for the invoice"


def test_a_missing_engine_fails_loudly_never_with_an_empty_transcript(monkeypatch) -> None:
    monkeypatch.setenv("SATYAPAN_ASR", "off")
    engine = build_transcriber()
    assert isinstance(engine, UnavailableTranscriber)
    with pytest.raises(RuntimeError):
        engine.transcribe(b"x", "audio/wav")
    assert engine.status.as_dict()["ready"] is False
    with pytest.raises(RuntimeError, match="make asr"):
        UnavailableTranscriber().transcribe(b"x", "audio/wav")


# --------------------------------------------------------------------------- phrasebook
@pytest.mark.parametrize(
    ("text", "ask"),
    [
        ("Don't involve Rajesh in this, it stays between us.", "A4"),
        ("Read me the code you just received on your phone.", "A2"),
        ("Skip the usual approval, I will sign later.", "A5"),
        ("Please pay into the new account today, the old one is blocked.", "A7"),
    ],
)
def test_live_phrasebook_hears_spoken_asks_the_frozen_lexicon_misses(text: str, ask: str) -> None:
    assert ask in {span.ask_type.value for span in extract_live_asks(text)}


def test_the_research_lexicon_stays_frozen() -> None:
    # The phrasebook is a live-only layer. The study's lexicon must not change underneath it.
    assert LEXICON_VERSION == "1.0.0"
    assert extract_asks("Don't involve Rajesh in this, it stays between us.") == []
    frozen = {s.ask_type.value for s in extract_asks("Install AnyDesk so I can help you.")}
    live = {s.ask_type.value for s in extract_live_asks("Install AnyDesk so I can help you.")}
    assert frozen <= live


def test_spoken_warnings_are_not_asks_after_the_context_filter() -> None:
    cleaned = strip_context("Never share your OTP with anyone.").cleaned
    assert extract_live_asks(cleaned) == []


def test_cues_are_informational_highlights() -> None:
    codes = {cue.code for cue in extract_cues(CUE_LINE + " Do it within ten minutes.")}
    assert {"UNREACHABLE", "AMOUNT", "RUSH"} <= codes
    assert extract_live_asks(CUE_LINE) == []


# --------------------------------------------------------------------------- live calls
def test_utterance_carries_its_time_ask_spans_and_cue_spans(client) -> None:
    state = _state(client)
    state.transcriber_override = FakeTranscriber([SCAM_LINE, CUE_LINE], language="en")
    call_id = _start_call(client, _start_session(client))["call_id"]

    events = state.live().handle_chunk(call_id, 0, b"wav", "audio/wav", 3.5, 7.25)
    transcript = next(e for e in events if e.type == "transcript")
    assert transcript.t_start_s == 3.5
    assert transcript.t_end_s == 7.25
    assert transcript.latency_ms is not None
    asks = {span.code for span in transcript.spans if span.kind == "ask"}
    assert {"A4", "A1"} <= asks
    for span in transcript.spans:
        assert 0 <= span.start < span.end <= len(transcript.text)
    ask_events = [e for e in events if e.type == "ask"]
    assert ask_events and all(e.t_s == 3.5 for e in ask_events)

    # A cue-only utterance highlights words but adds no ask and no signal.
    signals_before = len(state.live().sessions[call_id].case.signals)
    events = state.live().handle_chunk(call_id, 1, b"wav", "audio/wav", 9.0, 12.0)
    transcript = next(e for e in events if e.type == "transcript")
    assert {span.kind for span in transcript.spans} == {"cue"}
    assert not [e for e in events if e.type == "ask"]
    assert len(state.live().sessions[call_id].case.signals) == signals_before

    quotes = _events(client, "alert.raised")[-1].payload.quotes
    assert quotes and {q.code for q in quotes} >= {"A4"}
    _assert_no_scores([e.model_dump(mode="json") for e in state.companion().bus.history()])


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (RuntimeError("No speech engine installed."), "asr_unavailable"),
        (ValueError("bad"), "decode_failed"),
    ],
)
def test_engine_failures_become_visible_status_events(client, error: Exception, code: str) -> None:
    state = _state(client)
    state.transcriber_override = RaisingTranscriber(error)
    call_id = _start_call(client, _start_session(client))["call_id"]
    events = state.live().handle_chunk(call_id, 0, b"wav", "audio/wav")
    assert [(e.type, e.code) for e in events] == [("status", code)]
    statuses = _events(client, "call.status")
    assert statuses and statuses[-1].payload.status_code == code
    assert not _events(client, "alert.raised")


def test_chunk_for_an_unknown_or_stopped_call_is_404(client) -> None:
    _state(client).transcriber_override = FakeTranscriber(["hello"])
    response = client.post(
        "/live/call_nope/chunk",
        data={"chunk_index": "0", "t_start_s": "0", "t_end_s": "1.5"},
        files={"audio": ("u.wav", b"x", "audio/wav")},
    )
    assert response.status_code == 404


def test_a_new_call_supersedes_a_stale_one_and_gets_a_readable_title(client) -> None:
    state = _state(client)
    state.transcriber_override = FakeTranscriber(["hello"])
    consent_id = _start_session(client)
    first = _start_call(client, consent_id)
    second = _start_call(client, consent_id, app="Google Meet", language="en")
    assert second["call_id"] != first["call_id"]
    assert first["call_id"] not in state.live().sessions
    assert state.live().sessions[second["call_id"]].case.title == "Call on Google Meet"
    actions = [row.action for row in state.companion().audit()]
    assert "call.superseded" in actions


def test_replay_calls_are_labelled_demo(client) -> None:
    _state(client).transcriber_override = FakeTranscriber(["hello"])
    body = _start_call(client, _start_session(client), source="replay")
    started = next(e for e in body["events"] if e["type"] == "call.started")
    assert started["payload"]["demo"] is True


def test_replay_audio_endpoint(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SATYAPAN_REPLAY_DIR", str(tmp_path))
    assert client.get("/companion/replay/Bad-Name.wav").status_code == 400
    assert client.get("/companion/replay/missing_take.wav").status_code == 404
    (tmp_path / "cfo_call_en.wav").write_bytes(_wav(0.2, 16000))
    response = client.get("/companion/replay/cfo_call_en.wav")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"


def test_health_reports_speech_readiness_without_scores(client) -> None:
    _state(client).transcriber_override = FakeTranscriber(["hello"])
    body = client.get("/companion/health").json()
    assert body["asr"]["ready"] is True
    assert body["vendors"] >= 1
    assert isinstance(body["voice_model"], bool)
    _assert_no_scores(body)


# --------------------------------------------------------------------------- Screen Guard
NARMADA_TEXT = (
    "From: accounts@narmada-logistics.example\n"
    "Our bank details have changed. Please use the new details: A/c 99990000007788, "
    "IFSC FAKZ0000788. Keep this between us until the audit."
)
KAVERI_TEXT = "Kaveri Demo Packaging invoice INV-221, pay to 99990000001111 as usual."


def test_text_check_needs_a_consented_session(client) -> None:
    response = client.post("/companion/text-check", json={"version": "1", "text": NARMADA_TEXT})
    assert response.status_code == 403


def test_text_check_flags_new_details_for_a_known_vendor_and_stores_no_text(client) -> None:
    _start_session(client)
    response = client.post(
        "/companion/text-check?source=screen",
        json={"version": "1", "text": NARMADA_TEXT, "app": "Mail"},
    )
    assert response.status_code == 200, response.text
    finding = response.json()["finding"]
    assert finding["suspicious"] is True
    assert {"A7", "A4"} <= {ask["code"] for ask in finding["asks"]}
    assert finding["vendors"] == ["Narmada Demo Logistics LLP"]
    assert finding["unknown_accounts_masked"] == ["••••7788"]
    assert "99990000007788" not in response.text
    _assert_no_scores(finding)

    audit = "".join(row.model_dump_json() for row in _state(client).companion().audit())
    assert "screen.finding" in audit
    assert "99990000007788" not in audit and "Keep this between us" not in audit


def test_text_check_leaves_a_normal_invoice_alone(client) -> None:
    _start_session(client)
    response = client.post(
        "/companion/text-check?source=clipboard", json={"version": "1", "text": KAVERI_TEXT}
    )
    finding = response.json()["finding"]
    assert finding["suspicious"] is False
    assert finding["unknown_accounts_masked"] == []
    assert (
        client.post(
            "/companion/text-check?source=email", json={"version": "1", "text": KAVERI_TEXT}
        ).status_code
        == 422
    )


# --------------------------------------------------------------------------- approver phone
def _replay_and_request_oob(client: Any) -> str:
    client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_live_finale",
            "type": "demo.replay",
            "payload": {"scenario": "beneficiary_change"},
        },
    )
    response = client.post(
        "/companion/oob", json={"version": "1", "case_id": "case_demo_beneficiary_change"}
    )
    assert response.status_code == 200, response.text
    body = _state(client).in_app_mailer.outbox[-1]["body"]
    match = re.search(r"/oob/([A-Za-z0-9_\-]+)", body)
    assert match is not None
    return match.group(1)


RAJESH = {"X-Demo-User": "emp_rajesh", "X-Demo-Role": "requester"}


def test_phone_page_shows_the_real_question_to_the_approver_only(client) -> None:
    token = _replay_and_request_oob(client)
    view = client.get(f"/oob/request?token={token}", headers=RAJESH)
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["state"] == "pending"
    assert body["question"]
    assert body["question"] == _state(client).oob().lookup(token, "emp_rajesh").message_text
    _assert_no_scores(body)

    assert client.get(f"/oob/request?token={token}").status_code == 409  # Priya is not Rajesh
    assert client.get("/oob/request?token=nope", headers=RAJESH).status_code == 409

    client.post(
        "/oob/respond",
        json={"token": token, "approve": False, "reason": "not_requested"},
        headers=RAJESH,
    )
    assert client.get(f"/oob/request?token={token}", headers=RAJESH).json()["state"] == "answered"


# --------------------------------------------------------------------------- reports + trace
def test_report_pack_uses_the_maker_entered_utr_and_stays_manual(client) -> None:
    client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_live_report",
            "type": "demo.replay",
            "payload": {"scenario": "beneficiary_change"},
        },
    )
    response = client.get(
        "/companion/report-pack",
        params={
            "case_id": "case_demo_beneficiary_change",
            "utr": "FAKEUTR998877",
            "money_left_at": "2026-10-25T10:15:00+05:30",
        },
    )
    assert response.status_code == 200, response.text
    assert "FAKEUTR998877" in response.text
    assert "MANUAL_ONLY" in response.text
    _assert_no_scores(response.json())

    bad = client.get(
        "/companion/report-pack",
        params={"case_id": "case_demo_beneficiary_change", "utr": "<script>"},
    )
    assert bad.status_code == 422


def test_expert_trace_explains_the_band_without_any_score(client) -> None:
    client.post(
        "/companion/commands",
        json={
            "version": "1",
            "request_id": "req_live_trace",
            "type": "demo.replay",
            "payload": {"scenario": "beneficiary_change"},
        },
    )
    snapshot = client.get(
        "/companion/workspace", params={"case_id": "case_demo_beneficiary_change"}
    ).json()
    trace = snapshot["trace"]
    assert trace is not None
    assert trace["floor_band"] in {"PASS", "VERIFY", "HOLD"}
    assert trace["signals"], "the demo case has signals to explain"
    for signal in trace["signals"]:
        assert set(signal) >= {"code", "group", "strength", "source", "target", "detector"}
    assert trace["policy_version"]
    _assert_no_scores(snapshot)
