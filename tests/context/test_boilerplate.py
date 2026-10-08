"""Context layer (ADR-021): strips text ABOUT requests, never the requests themselves."""

from __future__ import annotations

import pytest

from satyapan.asks.extractor import extract_asks
from satyapan.context import strip_context


def asks(text: str) -> set[str]:
    return {s.ask_type.value for s in extract_asks(strip_context(text).cleaned)}


@pytest.mark.parametrize(
    "text",
    [
        "Invoice KDP/1187 attached. This e-mail and any attachments are confidential and intended "
        "solely for the addressee. If you have received it in error, please delete it.",
        "Payment received, thanks. The contents of this email are confidential.",
        "Bill attached. यह ईमेल और इसके संलग्नक गोपनीय हैं।",
        "Invoice attach kar diya. Ye mail confidential hai, forward na karein.",
        "482913 is the OTP for your login. Valid for 5 minutes. Do not share this OTP with anyone.",
        "FYI: Your OTP for login is 118204. Do not share it with anyone.",
        "Your OTP for transaction of INR 2,84,000.00 to DEMO LOGISTICS is 309152. "
        "Do NOT share OTP.",
        "आपका ओटीपी 552910 है। बैंक कभी ओटीपी नहीं माँगता।",
        "Your UPI PIN was reset successfully. Never share your UPI PIN with anyone.",
        "IT will never ask for your password over email or phone.",
        "IT Helpdesk will never ask you for your password, OTP or to install remote access "
        "software.",
        "Apna purana password hi use karein, kisi ke saath share na karein.",
        "Bank ki advisory: koi bhi aapse OTP ya PIN maange toh share mat karna.",
        "Notice: gift card payments are a common sign of fraud. Our bank will never ask you to pay "
        "in gift cards or crypto.",
    ],
)
def test_benign_boilerplate_no_longer_fires(text: str) -> None:
    assert asks(text) == set(), strip_context(text)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Priya, confidential acquisition hai, kisi ko mat batana.", {"A4"}),  # T11 line
        ("This is strictly confidential, do not discuss it with your manager.", {"A4"}),
        ("Aapke phone pe OTP aaya hoga, OTP batao jaldi.", {"A2"}),
        ("Never mind the bank, share your OTP with me now.", {"A2"}),
        ("The bank will never ask for your OTP, but read it out to me now.", {"A2"}),
        ("Do not worry, transfer to the new account 99991234567890 today.", {"A1"}),
        ("Fraud alert: install the screen share app from the link right now.", {"A3"}),
        ("Don't worry, just screen share karo.", {"A3"}),
    ],
)
def test_asks_survive_the_filter(text: str, want: set[str]) -> None:
    assert want <= asks(text)


def test_ask_with_appended_footer_is_kept() -> None:
    text = (
        "Our bank account is under audit, please pay the invoice to the new account below. "
        "This email is confidential and intended only for the addressee."
    )
    res = strip_context(text)
    assert "A1" in asks(text)
    assert [r.kind for r in res.removed] == ["disclaimer"]


def test_removed_segments_are_labelled() -> None:
    res = strip_context("Thanks. 771204 is your OTP. Never share your OTP.")
    assert [(r.kind, r.rule) for r in res.removed] == [
        ("notification", "otp_is"),
        ("warning", "negated_or_advisory"),
    ]
    assert res.cleaned == "Thanks."
    assert res.summary()["notification"] == 1


def test_signature_block_removed_only_without_payment_details() -> None:
    sig = "Hi, invoice attached.\n-- \nSuresh K\nDispatch\n+91-00000-30011"
    assert [r.kind for r in strip_context(sig).removed] == ["signature"]
    sneaky = "Hi, invoice attached.\n-- \nNew a/c for payment: 99991234567890 IFSC FAKZ0000001"
    assert strip_context(sneaky).removed == []


def test_pipeline_records_what_was_ignored(master) -> None:  # type: ignore[no-untyped-def]
    import hashlib

    from satyapan.contracts import Channel, Evidence
    from satyapan.pipeline import PipelineContext, analyze_evidence
    from satyapan.settings import Settings
    from satyapan.voice.rules import VoiceThresholds
    from tests.helpers import DEMO_DAY, make_case

    data = b"Invoice attached. This email is confidential and intended only for the addressee."
    ev = Evidence(
        id="ev_ctx",
        case_id="case_test",
        channel=Channel.MANUAL,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        captured_at=DEMO_DAY,
        submitted_by="emp_priya",
        storage_uri="mem://x",
    )
    th = VoiceThresholds(tau_hi=0.9, tau_lo=0.6, model_version="t")
    on = PipelineContext(master=master, settings=Settings(), thresholds=th)
    off = PipelineContext(master=master, settings=Settings(), thresholds=th, context_filter=False)
    out_on = analyze_evidence(data, ev, make_case(), on)
    out_off = analyze_evidence(data, ev, make_case(), off)
    assert out_on.signals == [] and out_on.artifacts["context"]["disclaimer"] == 1
    assert [s.code.value for s in out_off.signals] == ["ASK_SECRECY"]
