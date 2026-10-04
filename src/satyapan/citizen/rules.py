"""Deterministic 'impossible claim' rules for the citizen page. TASK T24.

Spec: docs/tasks/T24-citizen-scam-check.md.

Output is COARSE: band + action + rule names. Never scores, never detector breakdowns
(oracle-abuse mitigation, ARCHITECTURE §10).
"""

from __future__ import annotations

from satyapan.contracts.enums import Lang
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
]


def scam_check(text: str, lang: Lang = Lang.EN) -> CitizenResult:
    """1. hits = IMPOSSIBLE_CLAIMS whose regex matches (re.I | re.S).
    2. spans = extract_asks(text); A2/A3 or any hit -> HOLD; A1/A4/A5/A6/A7 -> VERIFY; else PASS.
    3. action_text (lang): HOLD -> "Stop. Do not pay or share anything. Call 1930 if money
       has left.", VERIFY -> "Do not pay yet. Verify by calling the official number yourself.",
       PASS -> "No known scam pattern found. Still verify before paying."
    4. links = LINKS plus "share" = "https://wa.me/?text=" + urlencoded warning.
    Never include scores."""
    raise NotImplementedError("T24: see docs/tasks/T24-citizen-scam-check.md")
