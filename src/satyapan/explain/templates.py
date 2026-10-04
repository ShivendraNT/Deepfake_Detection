"""Reason-code explanation templates in English and Hindi. TASK T14.

See docs/tasks/T14-explanation-templates.md. Templates are AUTHORITATIVE: the LLM summary is
optional prose on top and falls back to these. Every ReasonCode needs EN and HI text.
Hindi text must be in Devanagari. Keep each text to one or two plain sentences that tell
the maker WHAT HAPPENED and WHAT TO DO. Never say "safe", "verified", "genuine".
"""

from __future__ import annotations

from satyapan.contracts.case import Decision
from satyapan.contracts.enums import Lang, ReasonCode
from satyapan.contracts.explain import Explanation

# Fill this for EVERY ReasonCode. Two examples are given.
REASON_TEXT: dict[ReasonCode, dict[Lang, str]] = {
    ReasonCode.FLOOR_C1_BANK_CHANGED: {
        Lang.EN: "The bank account differs from the vendor master. Call the vendor back on the "
        "number already on file (not the one in the message) before paying.",
        Lang.HI: "बैंक खाता वेंडर मास्टर से अलग है। भुगतान से पहले वेंडर को पहले से दर्ज नंबर पर "
        "वापस कॉल करें (संदेश वाले नंबर पर नहीं)।",
    },
    ReasonCode.VOICE_LIKELY_SYNTHETIC: {
        Lang.EN: "The caller's voice shows signs of being AI-generated in two windows in a row. "
        "Do not act on this call; confirm through OOB-Confirm or a callback.",
        Lang.HI: "कॉल करने वाले की आवाज़ लगातार दो हिस्सों में AI से बनी हुई लगती है। इस कॉल पर "
        "कार्रवाई न करें; OOB-Confirm या कॉल-बैक से पुष्टि करें।",
    },
}

# Suggested line for the maker to say during a live call when the band rises.
SUGGESTED_LINES: dict[Lang, str] = {
    Lang.EN: "I'll process it once it's raised in the system with your login.",
    Lang.HI: "जैसे ही आप अपने लॉगिन से सिस्टम में अनुरोध डालेंगे, मैं इसे प्रोसेस कर दूँगी।",
}


def reason_text(code: ReasonCode, lang: Lang) -> str:
    """Return REASON_TEXT[code][lang]. Raise KeyError if missing (tests catch this)."""
    raise NotImplementedError("T14: see docs/tasks/T14-explanation-templates.md")


def explain_template(decision: Decision, lang: Lang) -> Explanation:
    """Band headline + one line per reason code (in decision.reason_codes order).

    Headline EN: "Band: VERIFY" / HI: "स्तर: VERIFY" (band names stay in English).
    Return Explanation(lang=..., band=decision.band, text=..., source="template",
                       reason_codes=decision.reason_codes).
    """
    raise NotImplementedError("T14: see docs/tasks/T14-explanation-templates.md")
