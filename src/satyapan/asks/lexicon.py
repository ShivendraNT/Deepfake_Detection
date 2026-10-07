"""Ask lexicon v1 (A1-A7) for English, romanised Hinglish and Devanagari. TASK T05.

FROZEN FOR RESEARCH once T05 is done: bump LEXICON_VERSION to "1.0.0", git tag
`lexicon-v1.0`, and never change it after the research test set is touched
(docs/RESEARCH_PROTOCOL.md §Pre-registration). Build it from your own knowledge and the
ICFD *train* split only. NEVER look at ICFD test while writing patterns.

Format: each entry is (entry_id, AskType, regex_pattern). Patterns are matched with
re.IGNORECASE on text normalised by satyapan.asks.extractor.normalise().
The seed entries below are examples; T05 extends them (target >= 8 per ask type).
"""

from __future__ import annotations

from satyapan.contracts.enums import AskType

LEXICON_VERSION = "1.0.0"

LEXICON: list[tuple[str, AskType, str]] = [
    # A1 transfer to a new / "safe" account
    (
        "A1.en.new_account",
        AskType.A1,
        r"\b(new|different|another|escrow|safe|alternate)\s+(bank\s+)?account\b",
    ),
    ("A1.hi.naya_khata", AskType.A1, r"\bnay[ae]\s+(account|khate?|bank)\b"),
    ("A1.hi.doosra_khata", AskType.A1, r"\bdoosre\s+account\b"),
    ("A1.deva.naya_khata", AskType.A1, r"(नए|नया)\s+(खाते|खाता|बैंक|अकाउंट)"),
    ("A1.deva.doosra_khata", AskType.A1, r"दूसरे\s+अकाउंट"),
    # A2 OTP / PIN / password / CVV
    ("A2.en.otp", AskType.A2, r"\b(otp|one[\s-]time\s+password|pin(?!\s+code)|cvv|password)\b"),
    ("A2.hi.otp_batao", AskType.A2, r"\botp\s+(batao|bata\s+do|bhejo|share\s+karo)\b"),
    ("A2.hi.pin_share", AskType.A2, r"\bpin\s+share\b"),
    ("A2.deva.otp", AskType.A2, r"ओटीपी"),
    ("A2.deva.pin", AskType.A2, r"पिन\s+नंबर"),
    ("A2.deva.password", AskType.A2, r"पासवर्ड"),
    # A3 remote-access apps
    (
        "A3.en.apps",
        AskType.A3,
        r"\b(anydesk|teamviewer|quick\s*support|rust\s*desk|screen\s*share)\b",
    ),
    ("A3.deva.anydesk", AskType.A3, r"एनीडेस्क"),
    ("A3.deva.teamviewer", AskType.A3, r"टीमव्यूअर"),
    ("A3.deva.remote", AskType.A3, r"रिमोट\s+एक्सेस"),
    # A4 secrecy / isolation
    (
        "A4.en.confidential",
        AskType.A4,
        r"\b(keep\s+(this|it)\s+(confidential|secret|between\s+us)|don'?t\s+tell\s+(anyone|the\s+checker)|don'?t\s+loop\s+(in|anyone))\b",
    ),
    ("A4.hi.mat_batana", AskType.A4, r"\bkisi\s+(aur\s+)?(ko\s+)?(bhi\s+)?mat\s+batana\b"),
    ("A4.hi.gupt", AskType.A4, r"\bgupt\s+rakhna\b"),
    ("A4.deva.mat_batana", AskType.A4, r"किसी\s+(को|से)\s+(मत\s+बताना|शेयर\s+मत\s+करना)"),
    ("A4.deva.gupt", AskType.A4, r"गुप्त\s+रखना"),
    ("A4.deva.between_us", AskType.A4, r"हमारे\s+बीच\s+ही\s+रहनी\s+चाहिए"),
    # A5 bypass a process
    (
        "A5.en.skip",
        AskType.A5,
        r"\b(skip|bypass|no\s+need\s+for)\s+(the\s+)?(approval|po|process|checker|verification|usual\s+po\s+process)\b",
    ),
    ("A5.hi.no_approval", AskType.A5, r"\bapproval\s+ki\s+zaroorat\s+nahi\b"),
    ("A5.hi.skip_process", AskType.A5, r"\bprocess\s+ko\s+skip\s+karo\b"),
    ("A5.deva.no_approval", AskType.A5, r"अप्रूवल\s+की\s+जरूरत\s+नहीं"),
    ("A5.deva.bypass", AskType.A5, r"बायपास\s+करें"),
    ("A5.deva.skip", AskType.A5, r"प्रोसेस\s+को\s+छोड़\s+दें"),
    # A6 gift card / crypto / UPI collect
    ("A6.en.giftcard", AskType.A6, r"\b(gift\s*cards?|crypto|bitcoin|usdt|upi\s+collect)\b"),
    ("A6.deva.giftcard", AskType.A6, r"गिफ्ट\s+कार्ड"),
    ("A6.deva.upi_collect", AskType.A6, r"यूपीआई\s+कलेक्ट"),
    ("A6.deva.crypto", AskType.A6, r"क्रिप्टो"),
    # A7 change of payee / bank details
    (
        "A7.en.changed_bank",
        AskType.A7,
        r"\b(changed|updated|new)\s+(our\s+)?(bank\s+(details|account)|account|payee)\b",
    ),
    ("A7.en.payee_change", AskType.A7, r"\bpayee\s+has\s+been\s+changed\b"),
    ("A7.hi.changed_bank", AskType.A7, r"\bbank\s+details\s+change\b"),
    ("A7.hi.update_account", AskType.A7, r"\bnaya\s+account\s+update\b"),
    ("A7.deva.changed_bank", AskType.A7, r"बैंक\s+की\s+जानकारी\s+बदल\s+गई"),
    ("A7.deva.update_bank", AskType.A7, r"नए\s+बैंक\s+खाते\s+को\s+अपडेट\s+करें"),
    ("A7.deva.changed_account", AskType.A7, r"खाता\s+नंबर\s+बदल\s+गया"),
]
