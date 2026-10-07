"""Ask lexicon v1 (A1-A7) for English, romanised Hinglish and Devanagari. TASK T05.

FROZEN FOR RESEARCH once T05 is done: bump LEXICON_VERSION to "1.0.0", git tag
`lexicon-v1.0`, and never change it after the research test set is touched
(docs/RESEARCH_PROTOCOL.md §Pre-registration). Build it from your own knowledge and the
ICFD *train* split only. NEVER look at ICFD test while writing patterns.

Format: each entry is (entry_id, AskType, regex_pattern). Patterns are matched with
re.IGNORECASE on text normalised by satyapan.asks.extractor.normalise().
"""

from __future__ import annotations

from satyapan.contracts.enums import AskType

LEXICON_VERSION = "1.0.0"

LEXICON: list[tuple[str, AskType, str]] = [
    # A1 transfer to a new / "safe" account
    (
        "A1.en.new_account",
        AskType.A1,
        r"\b(new|different|another|escrow|safe)\s+(bank\s+)?account\b",
    ),
    (
        "A1.en.wire_to",
        AskType.A1,
        r"\b(wire|transfer|send)\b[^.]{0,40}?\bto\s+(the\s+)?(new|safe|escrow|different)"
        r"\s+(account|wallet)\b",
    ),
    ("A1.en.switch", AskType.A1, r"\b(move|shift)\s+(our\s+)?(payment|fund|transfer)s?\s+to\b"),
    ("A1.en.safe_wallet", AskType.A1, r"\b(safe|secure|protected)\s+(wallet|a/?c|account)\b"),
    ("A1.hi.naya_khata", AskType.A1, r"\bnay[ae]a?\s+(account|khate?|khaata)\b"),
    ("A1.hi.nayi_account", AskType.A1, r"\bnayi\s+account\b"),
    ("A1.hi.escrow_mein", AskType.A1, r"\bescrow\s+(account\s+)?me[mN]\b"),
    ("A1.deva.naya_khaata", AskType.A1, r"नया\s+(खाता|अकाउंट|खाते)"),
    # A2 OTP / PIN / password / CVV
    ("A2.en.otp", AskType.A2, r"\b(otp|one[\s-]time\s+password)\b"),
    ("A2.en.pin", AskType.A2, r"\bpin\b(?!\s*code)"),
    ("A2.en.creds", AskType.A2, r"\b(cvv|card\s+number|password|passcode|mpin)\b"),
    (
        "A2.en.share_code",
        AskType.A2,
        r"\b(share|send|text|forward)\s+(me\s+)?(your\s+|the\s+)?(otp|pin|cvv|password|code)\b",
    ),
    (
        "A2.hi.otp_batao",
        AskType.A2,
        r"\b(otp|pin|password|cvv)\s+(batao|bata\s+do|bhejo|share\s+karo|bataiye)\b",
    ),
    ("A2.hi.bata_dijiye", AskType.A2, r"\b(otp|pin|password|cvv)\s+bata\s*dijiye\b"),
    ("A2.deva.otp", AskType.A2, r"ओटीपी"),
    ("A2.deva.pin_do", AskType.A2, r"(पिन|पासवर्ड|सीवीवी)\s*(बताइए|बताओ|भेजिए|दो)"),
    # A3 remote-access apps
    ("A3.en.anydesk", AskType.A3, r"\bany\s*desk\b"),
    ("A3.en.teamviewer", AskType.A3, r"\bteam\s*viewer\b"),
    (
        "A3.en.other_apps",
        AskType.A3,
        r"\b(quick\s*support|rustdesk|ammyy|supremo|getscreen|screen\s*share)\b",
    ),
    (
        "A3.en.install_remote",
        AskType.A3,
        r"\b(install|download|open)\s+(the\s+)?(anydesk|team\s*viewer|rustdesk|quick\s*support)\b",
    ),
    (
        "A3.hi.download_karo",
        AskType.A3,
        r"\b(anydesk|teamviewer|rustdesk|quick\s*support)\s+(download|install)\s+kar\s*(lijiye|lo|do)\b",
    ),
    ("A3.hi.screen_dekh", AskType.A3, r"\bscreen\s+(dekh\w*|share\s+kar\w*)\b"),
    ("A3.hi.remote_app", AskType.A3, r"\bremote\s+(access\s+)?app\b"),
    ("A3.deva.anydesk", AskType.A3, r"एनीडेस्क"),
    # A4 secrecy / isolation
    (
        "A4.en.confidential",
        AskType.A4,
        r"\b(keep\s+(this|it)\s+(confidential|secret|between\s+us)|confidential|secret\s+(deal|matter))\b",
    ),
    (
        "A4.en.dont_tell",
        AskType.A4,
        r"\b(don'?t|do\s+not)\s+(tell|inform|mention|share(\s+this)?)\s+(anyone|anybody|the\s+\w+)?\b",
    ),
    ("A4.en.dont_loop", AskType.A4, r"\b(don'?t|do\s+not)\s+loop\s+in\b"),
    ("A4.en.keep_quiet", AskType.A4, r"\bkeep\s+(this\s+)?(quiet|low[\s-]key)\b"),
    ("A4.hi.mat_batana", AskType.A4, r"\bkisi\s+(ko\s+)?(bhi\s+)?mat\s+batana\b"),
    ("A4.hi.batana_nahi", AskType.A4, r"\b(mat|nahi)\s+batana\b"),
    ("A4.hi.chup", AskType.A4, r"\b(gope\s*niy|gopeeniya|kisi\s+ko\s+nahi\s+batana)\b"),
    ("A4.deva.mat_batana", AskType.A4, r"(किसी\s+को\s+मत\s+बताना|गोपनीय)"),
    # A5 bypass a process
    (
        "A5.en.skip",
        AskType.A5,
        r"\b(skip|bypass)\s+(the\s+)?(approval|po|process|checker|verification|cheque)\b",
    ),
    (
        "A5.en.no_need",
        AskType.A5,
        r"\bno\s+need\s+(for\s+)?(the\s+)?(approval|po|process|checker|verification|otp|call)\b",
    ),
    (
        "A5.en.without",
        AskType.A5,
        r"\bwithout\s+(the\s+)?(approval|po|process|verification|rm|manager)\b",
    ),
    ("A5.en.fast_track", AskType.A5, r"\b(fast[\s-]?track|shortcut|cut\s*corners?)\b"),
    ("A5.hi.skip_karo", AskType.A5, r"\b(approval|process|verification|po)?\s*skip\s+kar\w*\b"),
    ("A5.hi.bypass_karo", AskType.A5, r"\b(bypass\s+kar\w*|approval\s+tod\w*|process\s+tod\w*)\b"),
    ("A5.hi.bina", AskType.A5, r"\bbina\s+(approval|po|process|verification)\b"),
    (
        "A5.deva.skip",
        AskType.A5,
        r"(स्वीकृति\s+छोड़|अप्रूवल\s+छोड़|वेरिफिकेशन\s+छोड़|बिना\s+अप्रूवल)",
    ),
    # A6 gift card / crypto / UPI collect
    ("A6.en.giftcard", AskType.A6, r"\bgift\s*cards?\b"),
    ("A6.en.crypto", AskType.A6, r"\b(crypto|bitcoin|ethereum|usdt|cryptocurrency)\b"),
    ("A6.en.upi_collect", AskType.A6, r"\bupi\s+collect\b"),
    (
        "A6.en.wallet",
        AskType.A6,
        r"\b(wallet\s+address|pay\s+in\s+(crypto|usdt|bitcoin)|send\s+(crypto|bitcoin|usdt))\b",
    ),
    ("A6.hi.gift_lao", AskType.A6, r"\bgift\s*card\s+(khareed\w*|lao|bhejo|le\s+ke)\b"),
    (
        "A6.hi.crypto_bhejo",
        AskType.A6,
        r"\b(crypto|usdt|bitcoin)\s+(bhejo|bhej\s+do|me[mN]\s+daal\w*)\b",
    ),
    ("A6.hi.upi_collect", AskType.A6, r"\bupi\s+collect\s+kar\w*\b"),
    ("A6.deva.gift", AskType.A6, r"(गिफ्ट\s*कार्ड|क्रिप्टो|बिटकॉइन)"),
    # A7 change of payee / bank details
    (
        "A7.en.changed_bank",
        AskType.A7,
        r"\b(changed|updated|change)\s+(our\s+)?bank\s+(details|account)\b",
    ),
    ("A7.en.new_bank", AskType.A7, r"\bnew\s+(bank\s+)?(details|ifsc|account\s+number)\b"),
    (
        "A7.en.ifsc",
        AskType.A7,
        r"\bifsc\s+(has\s+)?(changed|updated)\b|\b(changed|updated)\s+ifsc\b",
    ),
    (
        "A7.en.payee",
        AskType.A7,
        r"\b(change|update|switch)\s+(the\s+)?(payee|beneficiary|vendor)\s+(name|details|account)?\b",
    ),
    (
        "A7.hi.bank_badal",
        AskType.A7,
        r"\bbank\s+(details|account)\s+(badal\w*|change|update)\s*(gay?e|gaye|lijiye|kariye)?\b",
    ),
    ("A7.hi.naya_ifsc", AskType.A7, r"\bnaya\s+(ifsc|account\s+number)\b"),
    (
        "A7.hi.khata_update",
        AskType.A7,
        r"\b(khata|khate?|account)\s+(update|badal)\s*(kariye|karo|dena)\b",
    ),
    ("A7.deva.bank", AskType.A7, r"बैंक\s+(विवरण|खाता)\s*(बदल|अपडेट)"),
]
