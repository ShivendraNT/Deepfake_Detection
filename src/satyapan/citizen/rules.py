"""Deterministic 'impossible claim' rules for the citizen page. TASK T24.

Spec: docs/tasks/T24-citizen-scam-check.md.

Output is COARSE: band + action + rule names. Never scores, never detector breakdowns
(oracle-abuse mitigation, ARCHITECTURE §10).
"""

from __future__ import annotations

import re
from urllib.parse import quote

from satyapan.asks.extractor import extract_asks
from satyapan.contracts.enums import AskType, Band, Lang
from satyapan.contracts.explain import CitizenResult

LINKS: dict[str, str] = {
    "call_1930": "tel:1930",
    "ncrp": "https://cybercrime.gov.in/",
    "chakshu": "https://sancharsaathi.gov.in/sfc/",
}

# (rule_id, regex, EN text, HI text). Extend in T24.
IMPOSSIBLE_CLAIMS: list[tuple[str, str, str, str]] = [
    (
        "police_video_arrest",
        r"(digital\s+arrest|arrest(ed)?\s+(over|on)\s+(video|call)|cbi|police).*(video\s+call|skype|whatsapp)",
        "Police/CBI never arrest anyone over a video call.",
        "पुलिस/सीबीआई कभी वीडियो कॉल पर गिरफ्तार नहीं करती।",
    ),
    (
        "rbi_safe_account",
        r"(rbi|reserve\s+bank).*(safe|secure|suraksh\w*)\s+account",
        "RBI never asks you to move money to a 'safe account'.",
        "आरबीआई कभी भी पैसे 'सुरक्षित खाते' में डालने को नहीं कहता।",
    ),
    (
        "otp_request",
        r"\botp\b|ओटीपी",
        "Nobody legitimate needs your OTP.",
        "किसी भी असली व्यक्ति या संस्था को आपका ओटीपी नहीं चाहिए।",
    ),
    (
        "parcel_customs_fee",
        r"\b(parcel|courier|customs|ship\w*|delivery)\b.*\b(fee|charge|duty|payment|release|clearance)\b",
        "No courier or customs office makes you pay a release fee by UPI or gift card.",
        "कोई कूरियर या कस्टम्स ऑफिस रिलीज़ फ़ीस UPI या गिफ़्ट कार्ड से नहीं माँगता।",
    ),
    (
        "kyc_expiry",
        r"\bkyc\b.*\b(expir\w+|update\w*|suspend\w*|block\w*|verify\w*)\b",
        "Your bank never closes your KYC from a call, SMS or WhatsApp link.",
        "बैंक आपकी केवाईसी कॉल, एसएमएस या व्हाट्सएप लिंक से बंद नहीं करता।",
    ),
    (
        "electricity_disconnect",
        r"\b(electricity|electric\s+board|power\s+dept|bijli)\b.*\b(disconnect\w*|cut\s+off|final\s+notice)\b",
        "The electricity board never disconnects power over a message or a call.",
        "बिजली विभाग संदेश या कॉल पर आपकी बिजली नहीं काटता।",
    ),
    (
        "refund_otp",
        r"\brefund\b.*\botp\b|\botp\b.*\brefund\b",
        "Nobody needs your OTP to send you a refund.",
        "रिफ़ंड भेजने के लिए किसी को आपका ओटीपी नहीं चाहिए।",
    ),
]

HOLD_ASKS = frozenset({AskType.A2, AskType.A3})
VERIFY_ASKS = frozenset({AskType.A1, AskType.A4, AskType.A5, AskType.A6, AskType.A7})

ACTION_TEXT: dict[Lang, dict[Band, str]] = {
    Lang.EN: {
        Band.HOLD: "Stop. Do not pay or share anything. Call 1930 if money has left.",
        Band.VERIFY: "Do not pay yet. Verify by calling the official number yourself.",
        Band.PASS: "No known scam pattern found. Still verify before paying.",
    },
    Lang.HI: {
        Band.HOLD: "रुक जाइए। पैसे या कोई जानकारी मत दीजिए। पैसा निकल चुका हो तो 1930 पर कॉल कीजिए।",
        Band.VERIFY: "अभी पैसे मत भेजिए। आधिकारिक नंबर खुद लगाकर पक्का कीजिए।",
        Band.PASS: "कोई जाना-पहचाना ठगी पैटर्न नहीं मिला। फिर भी पैसे भेजने से पहले जाँच लीजिए।",
    },
}

SHARE_TEXT: dict[Lang, str] = {
    Lang.EN: "Message looks suspicious - do not pay. Call 1930 or report on cybercrime.gov.in.",
    Lang.HI: (
        "संदेश ठगी जैसा लगता है - पैसे मत भेजिए। 1930 पर कॉल कीजिए या cybercrime.gov.in पर शिकायत कीजिए।"
    ),
}


def scam_check(text: str, lang: Lang = Lang.EN) -> CitizenResult:
    """1. hits = IMPOSSIBLE_CLAIMS whose regex matches (re.I | re.S).
    2. spans = extract_asks(text); A2/A3 or any hit -> HOLD; A1/A4/A5/A6/A7 -> VERIFY; else PASS.
    3. action_text (lang): HOLD -> "Stop. Do not pay or share anything. Call 1930 if money
       has left.", VERIFY -> "Do not pay yet. Verify by calling the official number yourself.",
       PASS -> "No known scam pattern found. Still verify before paying."
    4. links = LINKS plus "share" = "https://wa.me/?text=" + urlencoded warning.
    Never include scores."""
    hits = [
        rule_id
        for rule_id, pattern, _en, _hi in IMPOSSIBLE_CLAIMS
        if re.search(pattern, text, re.I | re.S)
    ]
    ask_types = {span.ask_type for span in extract_asks(text)}
    if hits or ask_types & HOLD_ASKS:
        band = Band.HOLD
    elif ask_types & VERIFY_ASKS:
        band = Band.VERIFY
    else:
        band = Band.PASS

    action = ACTION_TEXT[lang][band]
    links = dict(LINKS)
    links["share"] = "https://wa.me/?text=" + quote(f"{action} {SHARE_TEXT[lang]}")
    return CitizenResult(band=band, action_text=action, rule_hits=hits, links=links)
