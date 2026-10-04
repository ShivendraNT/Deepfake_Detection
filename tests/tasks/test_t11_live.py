"""T11 acceptance: live transcript path with a FAKE transcriber (no audio, no Whisper needed).
The end-to-end latency target (ask chips <= 13 s after speech) is measured manually on the M4."""

from __future__ import annotations

import asyncio

import pytest

from satyapan.adapters.base import FakeTranscriber
from satyapan.contracts import AskEvent, BandEvent, TranscriptEvent, VoiceEvent, VoiceWindowResult
from satyapan.live.service import LiveService
from satyapan.voice.rules import VoiceThresholds
from tests.helpers import api_ok

pytestmark = pytest.mark.task("T11")

TH = VoiceThresholds(tau_hi=0.9, tau_lo=0.6, model_version="test")
LINES = [
    "Priya, confidential acquisition hai, kisi ko mat batana.",
    "Naye account mein aaj hi 48 lakh transfer karo.",
    "Naye account mein jaldi karo, kisi ko mat batana.",
]


def _svc(master) -> LiveService:  # type: ignore[no-untyped-def]
    return LiveService(master=master, transcriber=FakeTranscriber(LINES), thresholds=TH)


def test_chunks_produce_transcript_ask_and_band_events(master) -> None:
    svc = _svc(master)
    svc.start("call1", "emp_priya")
    ev1 = svc.handle_chunk("call1", 0, b"fake-webm", "audio/webm")
    assert any(isinstance(e, TranscriptEvent) for e in ev1)
    asks1 = {e.ask_type.value for e in ev1 if isinstance(e, AskEvent)}
    assert asks1 == {"A4"}
    ev2 = svc.handle_chunk("call1", 1, b"fake-webm", "audio/webm")
    asks2 = {e.ask_type.value for e in ev2 if isinstance(e, AskEvent)}
    assert asks2 == {"A1"}
    bands = [e for e in ev2 if isinstance(e, BandEvent)]
    assert bands and bands[-1].band == "HOLD"  # A4 + money movement (A1) -> HOLD
    assert bands[-1].suggested_line


def test_repeated_asks_not_re_emitted(master) -> None:
    svc = _svc(master)
    svc.start("call2", "emp_priya")
    for i in range(2):
        svc.handle_chunk("call2", i, b"x", "audio/webm")
    ev3 = svc.handle_chunk("call2", 2, b"x", "audio/webm")
    assert not [e for e in ev3 if isinstance(e, AskEvent)]


def test_voice_windows_two_consecutive_over_hi(master) -> None:
    svc = _svc(master)
    svc.start("call3", "emp_priya")
    w = [
        VoiceWindowResult(
            call_id="call3",
            window_index=i,
            t_start_s=5 * i,
            t_end_s=5 * i + 5,
            score=s,
            speech_seconds=5,
            model_version="test",
        )
        for i, s in enumerate([0.3, 0.95, 0.97])
    ]
    events = svc.handle_voice("call3", w)
    voice = [e for e in events if isinstance(e, VoiceEvent)]
    assert voice[-1].label == "likely_synthetic" and voice[-1].score is None
    assert any(isinstance(e, BandEvent) and e.band == "VERIFY" for e in events)


def test_event_bus_delivers(master) -> None:
    svc = _svc(master)
    svc.start("call4", "emp_priya")
    q = svc.bus.subscribe("call4")
    svc.handle_chunk("call4", 0, b"x", "audio/webm")
    first = asyncio.run(asyncio.wait_for(q.get(), timeout=1))
    assert first.call_id == "call4"


def test_api_chunk_route(client) -> None:
    client.app.state.satyapan.transcriber_override = FakeTranscriber(LINES)
    assert api_ok(client.post("/live/call5/start"), "T11").status_code == 200
    r = client.post(
        "/live/call5/chunk",
        data={"chunk_index": "0"},
        files={"audio": ("c.webm", b"x", "audio/webm")},
    )
    assert r.status_code == 200
    assert any(e["type"] == "ask" for e in r.json())
