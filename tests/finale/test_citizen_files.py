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
