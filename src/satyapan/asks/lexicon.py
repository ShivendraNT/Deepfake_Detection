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

LEXICON_VERSION = "0.1.0-draft"

LEXICON: list[tuple[str, AskType, str]] = [
    # A1 transfer to a new / "safe" account
    (
        "A1.en.new_account",
        AskType.A1,
        r"\b(new|different|another|escrow|safe)\s+(bank\s+)?account\b",
    ),
    ("A1.hi.naya_khata", AskType.A1, r"\bnay[ae]\s+(account|khate?)\b"),
    # A2 OTP / PIN / password / CVV
    ("A2.en.otp", AskType.A2, r"\b(otp|one[\s-]time\s+password|pin|cvv|password)\b"),
    ("A2.hi.otp_batao", AskType.A2, r"\botp\s+(batao|bata\s+do|bhejo|share\s+karo)\b"),
    ("A2.deva.otp", AskType.A2, r"ओटीपी"),
    # A3 remote-access apps
    ("A3.en.apps", AskType.A3, r"\b(anydesk|teamviewer|quick\s*support|rustdesk|screen\s*share)\b"),
    # A4 secrecy / isolation
    (
        "A4.en.confidential",
        AskType.A4,
        r"\b(keep\s+(this|it)\s+(confidential|secret|between\s+us)|don'?t\s+tell\s+anyone|don'?t\s+loop\s+in)\b",
    ),
    ("A4.hi.mat_batana", AskType.A4, r"\bkisi\s+(ko\s+)?(bhi\s+)?mat\s+batana\b"),
    ("A4.deva.mat_batana", AskType.A4, r"किसी\s+को\s+मत\s+बताना"),
    # A5 bypass a process
    (
        "A5.en.skip",
        AskType.A5,
        r"\b(skip|bypass|no\s+need\s+for)\s+(the\s+)?(approval|po|process|checker|verification)\b",
    ),
    # A6 gift card / crypto / UPI collect
    ("A6.en.giftcard", AskType.A6, r"\b(gift\s*cards?|crypto|bitcoin|usdt|upi\s+collect)\b"),
    # A7 change of payee / bank details
    (
        "A7.en.changed_bank",
        AskType.A7,
        r"\b(changed|updated|new)\s+(our\s+)?bank\s+(details|account)\b",
    ),
]
