"""Consumer Scam Check for any forwarded file (finale): band + what to do + why, no scores,
nothing kept, and an honest list of what this device could not check."""

from __future__ import annotations

import io
import json

from PIL import Image

from satyapan.imagecheck import ocr


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(buf, "PNG")
    return buf.getvalue()


def test_a_pasted_message_gets_why_and_never_a_score(client) -> None:
    r = client.post("/scam-check", json={"text": "Share the OTP you received to stop the "
                                                 "account block", "lang": "en"})  # fmt: skip
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == "HOLD" and body["why"]
    assert "score" not in json.dumps(body).lower()


def test_a_screenshot_is_read_and_judged(client, monkeypatch) -> None:
    monkeypatch.setattr(ocr, "read_text", lambda rgb: "CBI officer: you are under digital "
                        "arrest on this video call, transfer the money now")  # fmt: skip
    r = client.post("/scam-check/file", files={"file": ("chat.png", _png(), "image/png")},
                    data={"lang": "en"})  # fmt: skip
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == "HOLD"
    assert "police_video_arrest" in body["rule_hits"]
    assert body["heard_or_read"].startswith("CBI officer")
    assert "score" not in json.dumps(body).lower()


def test_hindi_and_what_could_not_be_checked(client, monkeypatch) -> None:
    def off(rgb):
        raise ocr.OcrUnavailable("text-in-image reading is off")

    monkeypatch.setattr(ocr, "read_text", off)
    r = client.post("/scam-check/file", files={"file": ("p.png", _png(), "image/png")},
                    data={"lang": "hi"})  # fmt: skip
    body = r.json()
    assert any("OCR" in x for x in body["not_checked"])
    assert body["action_text"] and any("ऀ" <= ch <= "ॿ" for ch in body["action_text"])


def test_nothing_is_kept(client, monkeypatch) -> None:
    state = client.app.state.satyapan
    before = len(state.repo.all_cases())
    monkeypatch.setattr(ocr, "read_text", lambda rgb: "")
    r = client.post("/scam-check/file", files={"file": ("p.png", _png(), "image/png")})
    assert r.status_code == 200
    assert len(state.repo.all_cases()) == before  # no case, no vault entry


def test_money_sent_gives_utr_first_drafts_and_never_submits(client) -> None:
    r = client.post("/scam-check/money-sent", json={
        "utr": "412345678901", "amount_inr": 48500, "sent_at": "2026-10-24T16:42",
        "rail": "UPI", "your_bank": "Demo Bank", "your_account_last4": "4821",
        "to_upi": "refund.desk@fakupi", "scammer_phone": "+91 99999 00000",
        "what_happened": "Caller said my KYC expires and asked me to pay a fee.",
    })  # fmt: skip
    assert r.status_code == 200
    body = r.json()
    assert body["submission"] == "MANUAL_ONLY"
    first = body["call_script_1930"].splitlines()[0]
    assert first.startswith("UTR 412345678901") and "₹48,500" in first and "••••4821" in first
    assert "24 Oct 2026 16:42" in first and "refund.desk@fakupi" in first
    assert body["facts"]["sent_at"].endswith("+05:30")
    labels = {f["label"]: f["value"] for f in body["ncrp_draft"]}
    assert labels["Transaction ID / UTR"] == "412345678901"
    assert labels["Sub-category"] == "UPI related fraud"
    assert body["links"]["call_1930"] == "tel:1930"


def test_money_sent_needs_a_utr_and_a_real_amount(client) -> None:
    assert client.post("/scam-check/money-sent", json={"amount_inr": 500}).status_code == 422
    bad = {"utr": "412345678901", "amount_inr": 0}
    assert client.post("/scam-check/money-sent", json=bad).status_code == 422
    r = client.post("/scam-check/money-sent", json={"utr": "AB12-345", "amount_inr": 900,
                                                    "lang": "hi"})  # fmt: skip
    assert r.status_code == 200
    first = r.json()["call_script_1930"].splitlines()[0]
    assert "1930" in r.json()["steps"][0] and "account" not in first  # no empty "account  to"


def test_the_engine_serves_the_consumer_page(client) -> None:
    for path in ("/check", "/scam-check.html"):
        r = client.get(path)
        assert r.status_code == 200 and "Satya Scam Check" in r.text


def test_a_genuine_otp_sms_or_bank_warning_is_not_a_scam(client) -> None:
    """False-positive path: the OTP a bank sends you, with its 'do not share' line, or the
    bank's own warning, must not be called a scam. Asking you for the OTP still is."""
    for text in (
        "Your OTP for transaction of Rs 2,499 at AMAZON is 482913. Valid for 10 mins. Do not "
        "share this OTP with anyone. -Demo Bank",
        "123456 is your OTP to log in. Do not share it with anyone.",
    ):
        body = client.post("/scam-check", json={"text": text}).json()
        assert body["band"] == "PASS" and body["rule_hits"] == [], text
    ask = "Sir I am calling from your bank, please tell me the OTP you just got to stop the block"
    assert client.post("/scam-check", json={"text": ask}).json()["band"] == "HOLD"


def test_an_awareness_message_is_not_a_scam_but_the_scam_script_is() -> None:
    from satyapan.citizen.rules import scam_check

    for advisory in ("Police or CBI never arrest anyone over a video call.",
                     "पुलिस कभी वीडियो कॉल पर गिरफ्तार नहीं करती।"):  # fmt: skip
        assert scam_check(advisory).rule_hits == [], advisory
    scam = "Main CBI se bol raha hoon, aap digital arrest mein ho, video call band mat karna"
    assert scam_check(scam).rule_hits == ["police_video_arrest"]


def test_a_missing_speech_engine_is_named_not_turned_into_an_alarm(client, monkeypatch) -> None:
    """No `make asr` on this laptop: a voice note is not a detector failure (no GREY ->
    VERIFY on every genuine note); the answer says what could not be checked."""
    import io
    import wave

    from satyapan.adapters.transcribe_local import UnavailableTranscriber

    state = client.app.state.satyapan
    monkeypatch.setattr(state, "transcriber_override", UnavailableTranscriber())
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\\x00\\x00" * 16000 * 4)
    r = client.post("/scam-check/file", files={"file": ("note.wav", buf.getvalue(), "audio/wav")})
    body = r.json()
    assert r.status_code == 200 and body["band"] == "PASS"
    assert any("speech engine not installed" in x for x in body["not_checked"])


def test_the_reasons_speak_to_a_person_not_a_finance_team(client) -> None:
    text = "Main CBI se bol raha hoon. Kisi ko mat batana, paise RBI safe account mein bhejo."
    why = " ".join(client.post("/scam-check", json={"text": text}).json()["why"]).lower()
    assert "number you already have" in why or "someone you trust" in why
    for business in ("checker", "vendor", "oob-confirm", "number on file"):
        assert business not in why, business


def test_a_voice_note_is_judged_on_its_voice_and_on_its_words(client, monkeypatch) -> None:
    """The voice model scores the voice; the transcript goes through the same scam-text model
    and asks as a message, so a read-aloud scam is caught even if the voice sounds human."""
    import io
    import wave

    import numpy as np

    from satyapan.adapters.base import FakeTranscriber

    class CalmScorer:
        model_version = "fake"

        def score_windows(self, windows):  # type: ignore[no-untyped-def]
            return [0.05 for _ in windows]

    state = client.app.state.satyapan
    monkeypatch.setattr(state, "voice_scorer_override", CalmScorer())
    monkeypatch.setattr(
        state,
        "transcriber_override",
        FakeTranscriber(
            ["This is your bank. Share the OTP you just received or your account will be blocked."]
        ),
    )
    t = np.arange(16000 * 6) / 16000
    pcm = (0.3 * np.sin(2 * np.pi * 220 * t) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(pcm)
    body = client.post(
        "/scam-check/file", files={"file": ("note.wav", buf.getvalue(), "audio/wav")}
    ).json()
    assert body["band"] == "HOLD"
    assert any("wording" in c for c in body["checked"]) and any(
        "voice" in c for c in body["checked"]
    )
    assert body["heard_or_read"].startswith("This is your bank")


def test_the_share_message_matches_the_answer(client) -> None:
    from urllib.parse import unquote

    def share(text: str) -> str:
        body = client.post("/scam-check", json={"text": text, "lang": "en"}).json()
        return unquote(body["links"]["share"])

    genuine = share("123456 is your OTP for login. Do not share it with anyone.")
    assert "No known scam pattern" in genuine and "suspicious" not in genuine
    scam = share("Share the OTP you received to stop the account block")
    assert "Stop." in scam and "suspicious" in scam
