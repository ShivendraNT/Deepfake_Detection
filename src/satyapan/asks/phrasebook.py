"""Live phrasebook: extra ask patterns for product surfaces, plus informational context cues.

WHY THIS EXISTS. The research lexicon (`lexicon.py`, v1.0.0) is FROZEN so the numbers in
`results/EVIDENCE_LEDGER.md` stay reproducible. Its measured recall on paraphrases is modest
(0.33). Real calls use phrasings like "skip the usual approval" or "I'll send the account
details on WhatsApp" that v1.0 misses. This module adds deterministic patterns for those, used
ONLY by product surfaces that opt in (live calls, files handed to Satya, screen text).
Research scripts keep calling `extract_asks` and never see these patterns. See ADR-024.

Written from the team's own knowledge of CEO-fraud / vishing scripts. No ICFD text was used.

Two outputs:
- extra ASK spans (A1-A7) — they become ordinary deterministic ask signals via
  `ask_signals`, so the policy engine and the signal table decide what they mean;
- CUES (rush, boss claim, can't-talk excuse, money amount) — shown to the user as grey,
  educational chips. Cues are NEVER signals: they cannot raise or lower any band.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from satyapan.asks.extractor import extract_asks, normalise
from satyapan.contracts.enums import AskType
from satyapan.contracts.evidence import AskSpan

PHRASEBOOK_VERSION = "live-1.1.0"

_A = r"(?:a|an|the|this|that|my|our|your)\s+"

EXTRA_ASKS: list[tuple[str, AskType, str]] = [
    # A1 money to a new / separate account
    (
        "A1.live.pay_into_new",
        AskType.A1,
        r"\b(?:transfer|send|wire|pay|move|remit|park|deposit)\b[^.?!]{0,60}?\b(?:to|into|in)\s+"
        rf"(?:{_A})?(?:new|fresh|separate|other|personal|different|temporary|holding|"
        r"special|backup)\s+(?:bank\s+)?(?:account|a/?c)\b",
    ),
    (
        "A1.live.details_on_chat",
        AskType.A1,
        r"\b(?:account|bank|beneficiary)\s+(?:details|number|info)\b[^.?!]{0,30}?\b(?:on|over|via|by|"
        r"through|in)\s+(?:the\s+)?(?:chat|whatsapp|sms|text|telegram|signal|personal\s+(?:e-?)?mail)\b",
    ),
    (
        "A1.live.holding",
        AskType.A1,
        r"\b(?:holding|suspense|nodal|clearing|settlement)\s+account\b",
    ),
    (
        "A1.live.add_payee",
        AskType.A1,
        r"\badd\s+(?:a\s+)?(?:new\s+)?payee\b",
    ),
    (
        "A1.live.account_mentioned",
        AskType.A1,
        r"\b(?:transfer|send|wire|pay|move|remit)\b[^.?!]{0,60}?\b(?:to|into|in)\s+"
        r"(?:the\s+|that\s+|this\s+|an?\s+)?account\s+"
        r"(?:mentioned|given|shared|sent|below|in\s+(?:my|this|the)\s+"
        r"(?:next\s+|previous\s+)?(?:message|chat|sms|text))\b",
    ),
    (
        "A1.live.escrow",
        AskType.A1,
        r"\b(?:transfer|send|wire|pay|move|remit|park|deposit)\b[^.?!]{0,60}?\b"
        r"(?:escrow|neutral|client|lawyer'?s?|seller'?s?\s+agent)\s+account\b",
    ),
    (
        "A1.hi.seedha_account",
        AskType.A1,
        r"\b(?:seedha|directly)\s+(?:is|us|in)\s+account\s+(?:mein|me|mai)\b",
    ),
    (
        "A1.hi.naye_account_mein",
        AskType.A1,
        r"\b(?:naye|nayi|naya|dusre|doosre|alag)\s+(?:bank\s+)?(?:account|khate|khaate)\s+"
        r"(?:me|mein|mai|par|pe)\b",
    ),
    # A2 one-time codes and credentials
    (
        "A2.live.read_code",
        AskType.A2,
        r"\b(?:read|tell|give|send|share|forward)\s+(?:me\s+)?(?:out\s+)?(?:the\s+|that\s+|your\s+)?"
        r"(?:(?:\d|four|six|eight)[\s-]?digit\s+)?(?:code|verification\s+code|security\s+code)\b",
    ),
    (
        "A2.live.code_received",
        AskType.A2,
        r"\bcode\s+(?:you|that)\s+(?:just\s+)?(?:got|received|get)\b",
    ),
    (
        "A2.live.login",
        AskType.A2,
        r"\b(?:netbanking|net\s+banking|internet\s+banking|banking)\s+(?:login|password|credentials)\b",
    ),
    (
        "A2.live.digits_from_sms",
        AskType.A2,
        r"\b(?:read|tell|give|send|share|forward|whatsapp)\b[^.?!]{0,50}?\b"
        r"(?:digits?|numbers?|code)\b[^.?!]{0,50}?\b(?:sms|phone|message|card)\b",
    ),
    (
        "A2.live.number_that_came",
        AskType.A2,
        r"\b(?:number|digits?|code)\b[^.?!]{0,30}?\b(?:came|received|aaya|aayi|aaye)\b"
        r"[^.?!]{0,30}?\b(?:sms|phone|message)\b",
    ),
    (
        "A2.live.card_back",
        AskType.A2,
        r"\bcard\s+(?:ke\s+)?(?:peeche|piche|back)\b[^.?!]{0,30}\b"
        r"(?:number|digits|3|three|cvv)\b",
    ),
    (
        "A2.hi.pin_kya",
        AskType.A2,
        r"\b(?:pin|password)\s+(?:kya|bata|bol|share|de)\b",
    ),
    (
        "A2.hi.code_padho",
        AskType.A2,
        r"\b(?:code|कोड)\b[^.?!]{0,30}\b(?:padh|padhke|padh\s*kar|sunao|batao|bata\s*do)\b",
    ),
    # A3 remote access / screen sharing
    (
        "A3.live.install_app",
        AskType.A3,
        rf"\b(?:install|download)\s+(?:{_A})?(?:small\s+|quick\s+|support\s+|remote\s+)?"
        r"(?:app|application|software|tool)\b",
    ),
    ("A3.live.share_screen", AskType.A3, r"\bshare\s+(?:your|the)\s+(?:screen|desktop)\b"),
    ("A3.live.remote_session", AskType.A3, r"\b(?:remote|support)\s+(?:session|access|control)\b"),
    (
        "A3.live.desktop_access",
        AskType.A3,
        r"\b(?:give|grant|allow|get|take)\b[^.?!]{0,30}?\baccess\b[^.?!]{0,20}?\b"
        r"(?:desktop|computer|laptop|screen|system)\b",
    ),
    (
        "A3.live.install_apk",
        AskType.A3,
        r"\b(?:install|download)\b[^.?!]{0,30}\b(?:apk|attachment|remote\s+support\s+app)\b",
    ),
    (
        "A3.live.start_screen_sharing",
        AskType.A3,
        r"\b(?:start|open|enable|turn\s+on|accept)\b[^.?!]{0,20}?\bscreen\s*sharing\b",
    ),
    (
        "A3.hi.laptop_control",
        AskType.A3,
        r"\b(?:laptop|computer|system)\s+(?:ka|par|pe)\s+(?:control|access)\b",
    ),
    (
        "A3.hi.screen_sharing_on",
        AskType.A3,
        r"\bscreen\s*sharing\s+(?:on|chalu|start)\b",
    ),
    (
        "A3.hi.support_app",
        AskType.A3,
        r"\b(?:support|remote)\s+(?:app|software)\b[^.?!]{0,20}\b"
        r"(?:install|download|karo|kar\s*lo)\b",
    ),
    # A4 secrecy / isolation
    (
        "A4.live.nobody_knows",
        AskType.A4,
        r"\b(?:nobody|no\s*one|no\s+body)\s+(?:else\s+)?(?:should|must|can|needs\s+to|has\s+to)\s+know\b",
    ),
    (
        "A4.live.between",
        AskType.A4,
        r"\bbetween\s+(?:you\s+and\s+me|us|the\s+two\s+of\s+us)\b",
    ),
    (
        "A4.live.dont_involve",
        AskType.A4,
        # Case-sensitive on purpose: a capitalised word after "don't tell" is a person's name.
        r"(?i:\b(?:don'?t|do\s+not|no\s+need\s+to)\s+(?:involve|cc|copy|loop\s+in|inform|tell|"
        r"update|discuss\s+(?:this\s+|it\s+)?with|mention\s+(?:this\s+|it\s+)?to)\s+)"
        r"(?:(?i:anyone|anybody|him|her|them|finance|accounts|the\s+team|your\s+(?:team|manager|boss))"
        r"|[A-Z][a-z]+)\b",
    ),
    (
        "A4.live.under_wraps",
        AskType.A4,
        r"\b(?:under\s+wraps|off\s+the\s+record|hush[\s-]hush|top\s+secret)\b",
    ),
    (
        "A4.hi.kisi_se",
        AskType.A4,
        r"\bkisi\s+(?:se|ko)\s+(?:bhi\s+)?(?:baat|zikr|mention|share)?\s*(?:mat|nahi|na)\s+"
        r"(?:karna|karo|batana|bolna)\b",
    ),
    # A5 bypass the normal process / prevent verification
    (
        "A5.live.skip_usual",
        AskType.A5,
        r"\b(?:skip|bypass|ignore|avoid|forget|override|jump)\s+(?:the\s+|all\s+the\s+)?"
        r"(?:usual|normal|regular|standard|whole|entire|formal|internal)?\s*(?:approval|approvals|"
        r"process|procedure|checks?|verification|po|paperwork|protocol|sign[\s-]?off|checker|queue)\b",
    ),
    (
        "A5.live.sign_later",
        AskType.A5,
        r"\b(?:i'?ll|i\s+will|we'?ll|we\s+will|i\s+can)\s+(?:sign|approve|authori[sz]e|regulari[sz]e|"
        r"do\s+the\s+paperwork)\b[^.?!]{0,20}?\b(?:later|afterwards|after|tomorrow|when\s+i'?m\s+back)\b",
    ),
    (
        "A5.live.no_callback",
        AskType.A5,
        r"\b(?:don'?t|do\s+not|no\s+need\s+to)\s+(?:call|ring|phone)\s+(?:me\s+)?(?:back|anyone|him|her|"
        r"the\s+(?:bank|vendor|cfo|ceo))\b",
    ),
    (
        "A5.live.no_time",
        AskType.A5,
        r"\b(?:no\s+time\s+(?:for|to\s+wait\s+for)|can'?t\s+wait\s+for|don'?t\s+wait\s+for)\s+"
        r"(?:the\s+)?(?:approval|process|checks?|sign[\s-]?off|verification|checker)\b",
    ),
    (
        "A5.live.authorise_directly",
        AskType.A5,
        r"\b(?:i\s+am|i'?m)\s+(?:authori[sz]ing|approving)\s+(?:it|this)\s+(?:directly|myself|personally)\b",
    ),
    (
        "A5.hi.baad_mein",
        AskType.A5,
        r"\b(?:approval|sign\s*off|paperwork)\s+(?:baad\s+(?:me|mein)|later)\b",
    ),
    # A6 gift cards / crypto / vouchers
    (
        "A6.live.cards",
        AskType.A6,
        r"\b(?:google\s+play|amazon|apple|itunes|steam|flipkart)\s+(?:gift\s+)?(?:cards?|vouchers?)\b",
    ),
    (
        "A6.live.vouchers",
        AskType.A6,
        r"\b(?:buy|purchase|get)\s+(?:some\s+|a\s+few\s+)?(?:vouchers|prepaid\s+cards|gift\s+vouchers)\b",
    ),
    # A7 change of payee / bank details
    (
        "A7.live.details_changed",
        AskType.A7,
        r"\b(?:bank|account|banking|payment)\s+(?:details|account|number|info)\s+(?:have|has)\s+"
        r"(?:been\s+|now\s+)?(?:changed|updated|moved|switched)\b",
    ),
    (
        "A7.live.use_new_details",
        AskType.A7,
        r"\b(?:use|pay\s+(?:to|into)|send\s+(?:it\s+)?to|update\s+(?:to|with))\s+(?:the\s+|our\s+)?"
        r"(?:new|updated|revised|latest)\s+(?:bank\s+)?(?:details|account|ifsc|a/?c)\b",
    ),
    (
        "A7.live.old_blocked",
        AskType.A7,
        r"\b(?:old|previous|usual|registered|existing)\s+(?:bank\s+)?account\s+(?:is\s+)?"
        r"(?:blocked|frozen|closed|under\s+audit|not\s+working|on\s+hold|suspended)\b",
    ),
    (
        "A7.live.switched_bank",
        AskType.A7,
        r"\b(?:changed|switched|moved)\s+(?:our\s+|to\s+a\s+new\s+)?banks?\b",
    ),
]

# Patterns with scoped "(?i:" flags manage their own case; the rest ignore case.
_COMPILED_ASKS = [
    (eid, at, re.compile(p) if "(?i:" in p else re.compile(p, re.IGNORECASE))
    for eid, at, p in EXTRA_ASKS
]
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@dataclass(frozen=True)
class Cue:
    """An informational context cue. Never a Signal; never changes a band."""

    code: str  # "RUSH" | "AUTHORITY" | "UNREACHABLE" | "AMOUNT"
    text: str
    start: int
    end: int


_NUM_WORDS = (
    r"(?:\d[\d,]*(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
    r"(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[\s-](?:one|two|three|four|five|"
    r"six|seven|eight|nine))"
)

CUES: list[tuple[str, str]] = [
    (
        "RUSH",
        r"\b(?:urgent(?:ly)?|immediately|right\s+(?:now|away)|asap|as\s+soon\s+as\s+possible|"
        r"within\s+(?:the\s+)?(?:next\s+)?(?:\d+|an?|one|two|ten|fifteen|thirty)\s+(?:minutes?|mins?|hours?)|"
        r"before\s+(?:\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm|o'?clock)?|end\s+of\s+(?:the\s+)?day|eod|"
        r"the\s+bank\s+closes|(?:the\s+)?cut[\s-]?off|lunch)|today\s+itself|by\s+today|"
        r"jaldi|abhi\s+ke\s+abhi|turant|fauran)\b",
    ),
    (
        "AUTHORITY",
        r"\b(?:this\s+is\s+(?:your\s+)?(?:ceo|cfo|md|director|boss|chairman|managing\s+director)|"
        r"i\s+am\s+(?:the\s+|your\s+)?(?:ceo|cfo|md|director|chairman)|on\s+behalf\s+of\s+(?:the\s+)?"
        r"(?:ceo|cfo|md|director|board|chairman)|(?:ceo|cfo|md|board)\s+(?:has\s+)?(?:asked|wants|approved))\b",
    ),
    (
        "UNREACHABLE",
        r"\b(?:(?:i'?m|i\s+am)\s+(?:in|stuck\s+in|inside)\s+(?:a\s+|the\s+)?(?:board\s+|client\s+)?meeting|"
        r"can'?t\s+(?:talk|speak)\s+(?:long|now|much|right\s+now)|(?:i'?m|i\s+am)\s+(?:on|boarding)\s+"
        r"(?:a\s+)?flight|bad\s+(?:network|line|connection|signal)|(?:my\s+)?(?:camera|video|webcam)\s+"
        r"(?:is\s+)?(?:not\s+working|broken|off|down)|(?:can'?t|cannot)\s+(?:turn\s+on|switch\s+on)\s+"
        r"(?:my\s+|the\s+)?(?:camera|video))\b",
    ),
    (
        "AMOUNT",
        rf"(?:₹\s?{_NUM_WORDS}(?:\s*(?:lakhs?|lacs?|crores?|cr|k|thousand))?|\b{_NUM_WORDS}\s*"
        r"(?:lakhs?|lacs?|crores?|cr)\b(?:\s+(?:rupees|rs\.?|inr))?|\b(?:rs\.?|inr)\s?\d[\d,]*)",
    ),
]

_COMPILED_CUES = [(code, re.compile(p, re.IGNORECASE)) for code, p in CUES]


def _script(text: str) -> str:
    return "devanagari" if _DEVANAGARI.search(text) else "latin"


def extra_ask_spans(text: str) -> list[AskSpan]:
    """Phrasebook matches only (positions refer to `normalise(text)`)."""
    norm = normalise(text)
    out: list[AskSpan] = []
    for entry_id, ask_type, rx in _COMPILED_ASKS:
        for m in rx.finditer(norm):
            if m.end() <= m.start():
                continue
            out.append(
                AskSpan(
                    ask_type=ask_type,
                    start=m.start(),
                    end=m.end(),
                    text=norm[m.start() : m.end()],
                    lexicon_id=entry_id,
                    script=_script(m.group(0)),
                )
            )
    return out


def extract_live_asks(text: str) -> list[AskSpan]:
    """Frozen lexicon v1.0 + phrasebook, merged per ask type exactly like `extract_asks`."""
    norm = normalise(text)
    spans = [*extract_asks(text), *extra_ask_spans(text)]
    by_type: dict[AskType, list[AskSpan]] = {}
    for s in spans:
        by_type.setdefault(s.ask_type, []).append(s)
    merged: list[AskSpan] = []
    for group in by_type.values():
        group.sort(key=lambda s: (s.start, -s.end))
        cur = group[0]
        for s in group[1:]:
            if s.start < cur.end:
                start, end = cur.start, max(cur.end, s.end)
                cur = AskSpan(
                    ask_type=cur.ask_type,
                    start=start,
                    end=end,
                    text=norm[start:end],
                    lexicon_id=cur.lexicon_id,
                    script=_script(norm[start:end]),
                )
            else:
                merged.append(cur)
                cur = s
        merged.append(cur)
    merged.sort(key=lambda s: (s.start, s.ask_type))
    return merged


def extract_cues(text: str) -> list[Cue]:
    """Informational context cues on `normalise(text)`. One entry per match, sorted."""
    norm = normalise(text)
    cues = [
        Cue(code=code, text=norm[m.start() : m.end()], start=m.start(), end=m.end())
        for code, rx in _COMPILED_CUES
        for m in rx.finditer(norm)
        if m.end() > m.start()
    ]
    cues.sort(key=lambda c: (c.start, c.code))
    return cues
