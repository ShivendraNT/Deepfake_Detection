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
