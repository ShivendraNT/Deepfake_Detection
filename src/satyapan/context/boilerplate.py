"""Context layer: drop text that is ABOUT a request instead of BEING one, before ask extraction.

Leader-owned (ADR-021). The frozen ask lexicon (src/satyapan/asks/, v1.0) is NOT changed; this
layer only decides which sentences the lexicon gets to see. It removes, and labels:

  disclaimer    e-mail confidentiality footers, legal notices, "do not reply" lines
  notification  bank/system notifications quoted in a message ("482913 is your OTP ... ",
                "your password was reset"), incl. the "do not share it" line right after
  warning       protective advice: "never share your OTP", "IT will never ask for your
                password", "share mat karna", "साझा न करें", fraud-awareness notices
  signature     an RFC 3676 signature block ("-- " line) in multi-line mail

Deterministic, sentence level, no ML, no network. Every removed segment is returned with its
rule id so the checker can see exactly what was ignored.

Adversarial guard (a filter that removes text is an evasion surface): a sentence is NEVER
removed if it contains
  - a request directed at the requester ("send me", "read it out", "mujhe", "bata do", "मुझे"),
  - money-movement content (transfer/pay/wire ... account, an account-number-like digit run,
    an IFSC code, "naye account", "नए खाते"),
  - an action verb that is not under a negation ("install the app", "click the link").
Asks hidden inside footer-shaped text can still evade; see docs/THREAT_MODEL.md and the
red-team numbers in results/redteam_deterministic.json.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

CONTEXT_VERSION = "1.0.0"

Kind = Literal["disclaimer", "notification", "warning", "signature"]


@dataclass(frozen=True)
class Removed:
    kind: Kind
    rule: str
    text: str


@dataclass(frozen=True)
class ContextResult:
    original: str
    cleaned: str
    removed: list[Removed] = field(default_factory=list)

    def summary(self) -> dict[str, int | str]:
        out: dict[str, int | str] = {"context_version": CONTEXT_VERSION}
        for r in self.removed:
            out[r.kind] = int(out.get(r.kind, 0)) + 1
        return out


_I = re.IGNORECASE

# ---------------------------------------------------------------- guards (never strip)
_GUARD_ME = [
    re.compile(p, _I)
    for p in (
        r"\b(to|with)\s+(me|us)\b",
        r"\b(send|tell|give|read|text|forward|share|whatsapp|email|mail)\s+(me|us)\b",
        r"\b(call|contact|message|ping)\s+(me|us)\b",
        r"\bread\s+(it|them|the\s+\w+)?\s*out\b",
        r"\b(mujhe|mujhko|humein|hume|hamein|hamko)\b",
        r"\b(bata\s*do|batao|bata\s*dijiye|bataiye|bhej\s*do|bhejo|bhej\s*dijiye|sunao)\b",
        r"(मुझे|हमें|बताइए|बता\s*दीजिए|बता\s*दो|भेज\s*दो|भेजिए|सुनाइए)",
    )
]
_GUARD_MONEY = [
    re.compile(p, _I)
    for p in (
        r"\b(transfer|wire|remit|pay|send|move|shift|deposit)\b.{0,60}\b"
        r"(account|a/c|beneficiary|wallet|upi|ifsc|khat[ae]|khaata)\b",
        r"\b\d{9,18}\b",
        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        r"\bnay[ae]a?\s+(account|khat[ae])\b",
        r"(नए|नया)\s+(खाते|खाता)",
    )
]

# ---------------------------------------------------------------- disclaimers / footers
_DISCLAIMER = [
    (re.compile(p, _I), rid)
    for p, rid in (
        (
            r"\b(this|the)\s+(e-?mail|message|communication|mail)\b[^.]{0,120}"
            r"\b(confidential|privileged|intended)",
            "this_email_confidential",
        ),
        (r"\bcontents?\s+of\s+this\s+(e-?mail|message)", "contents_of_this_email"),
        (r"\bintended\s+(solely|only|recipient|for\s+the)", "intended_recipient"),
        (r"\bnot\s+the\s+intended\b", "intended_recipient"),
        (r"\b(received|receive)\b[^.]{0,30}\bin\s+error\b", "received_in_error"),
        (r"\bunauthori[sz]ed\s+(use|access|disclosure|copying|review)", "unauthorised_use"),
        (
            r"\b(confidentiality(\s+notice)?|disclaimer|privileged\s+and\s+confidential)\s*:",
            "notice",
        ),
        (r"\b(review|retransmission|dissemination)\b[^.]{0,80}\bprohibited\b", "prohibited"),
        (r"\bconsider\s+the\s+environment\s+before\s+printing\b", "print_env"),
        (r"\bscanned\s+for\s+(viruses|malware)\b", "virus_scan"),
        (r"\b(system|auto(matically)?)[\s-]generated\b", "auto_generated"),
        (r"\b(do\s+not|please\s+don'?t)\s+reply\b", "no_reply"),
        (r"\bmailbox\s+is\s+not\s+monitored\b", "no_reply"),
        (r"\bopinions\s+expressed\b", "opinions"),
        (r"\binternal\s+use\s+only\b", "internal_use"),
        (r"\boriginated\s+from\s+outside\b", "external_banner"),
        (r"\bsent\s+from\s+my\s+(mobile|phone|iphone|android)\b", "sent_from"),
        (
            r"\b(share|forward|disclose|distribute)\s+this\s+(e-?mail|message)\s+"
            r"(outside|to\s+any\s+third)",
            "no_forward_outside",
        ),
        (
            r"\b(ye|yeh|is)\s+(e-?mail|mail)\b[^.]{0,40}\b(confidential|gopniya)\b",
            "hinglish_footer",
        ),
        (r"\bgalti\s+se\s+mil", "hinglish_footer"),
        (r"(यह|इस)\s*(ईमेल|मेल|संदेश)[^।]{0,60}(गोपनीय|इच्छित|प्राप्तकर्ता)", "deva_footer"),
        (r"इच्छित\s+प्राप्तकर्ता", "deva_footer"),
        (r"स्वचालित\s+संदेश", "deva_footer"),
        (r"इस\s+(ईमेल|मेल)\s+(को\s+आगे|का\s+उत्तर)", "deva_footer"),
    )
]
_FOOTER_TAIL = re.compile(
    r"^(please\s+|kindly\s+)?(do\s+not|don'?t)\s+(forward|copy|print|disclose|distribute|share)"
    r"\b.{0,80}$",
    _I,
)

# ---------------------------------------------------------------- system notifications
_NOTIFICATION = [
    (re.compile(p, _I), rid)
    for p, rid in (
        (
            r"\b\d{4,8}\s+is\s+(the|your)\s+(otp|one[\s-]time\s+password|verification\s+code)",
            "otp_is",
        ),
        (
            r"\b(otp|one[\s-]time\s+password|verification\s+code)\b.{0,80}?\b(is|:)\s*\d{4,8}\b",
            "otp_value",
        ),
        (r"\botp\s*:?\s*\d{4,8}\s+(for|to)\b", "otp_for"),
        (r"\b(otp|code)\b[^.]{0,20}\bvalid\s+(for|till)\b", "otp_valid"),
        (
            r"\b(password|passcode|pin|upi\s+pin|mpin)\b[^.]{0,25}\b(was|has\s+been|have\s+been)\s+"
            r"(changed|reset|updated)",
            "credential_status",
        ),
        (r"\b(password|pin)\b[^.]{0,25}\bwill\s+expire\b", "credential_expiry"),
        (r"\bpassword\b[^.]{0,25}\b(badal\s+gaya|change\s+ho\s+gaya)\b", "credential_status"),
        (r"(ओटीपी|पासवर्ड)\s*\d{4,8}|ओटीपी\s+\d{4,8}", "deva_otp_value"),
        (r"(पासवर्ड|पिन)[^।]{0,25}(समाप्त\s+हो\s+जाएगा|बदल\s+(गया|दिया))", "deva_credential_status"),
    )
]

# ---------------------------------------------------------------- protective warnings
_TARGET = re.compile(
    r"\b(otps?|one[\s-]time\s+password|pins?|upi\s+pin|mpin|passwords?|passcode|cvv|card\s+number"
    r"|credentials?|token|screen|remote|apps?|software|qr|collect\s+request|gift\s*cards?|crypto\w*"
    r"|bank\s+(details|account))\b|ओटीपी|पिन|पासवर्ड|सीवीवी|ऐप|क्यूआर|यूपीआई",
    _I,
)
_ACTION = re.compile(
    r"\b(share|send|tell|give|read|forward|text|install|download|click|scan|approve|accept|enter"
    r"|type|transfer|pay|wire|move|disclose|reveal|bhej\w*|bata\w*|daal\w*)\b"
    r"|साझा|बता\S*|भेज\S*|इंस्टॉल|स्कैन|डाल\S*",
    _I,
)
_NEG_BEFORE = re.compile(
    r"\b(never|not|don'?t|dont|cannot|can'?t|won'?t|mat|kabhi)\b|(मत|कभी|न)(?=\s|$)", _I
)
_NEG_AFTER = re.compile(r"^\s*(mat|na|nahi|nahin|न|नहीं)(?=\s|$|[,.।])", _I)
_NEVER_ASK = re.compile(
    r"\b(will|would|does|do|shall|should)\s+never\s+(ask|call|request|send|change|message)\b"
    r"|\bnever\s+(asks?|calls?|requests?)\b|कभी[^।]{0,30}(नहीं\s+(माँग|मांग))|नहीं\s+माँगता",
    _I,
)
_ADVISORY = re.compile(
    r"\b(beware|fraud\s+alert|sign\s+of\s+fraud|fraudsters?|caution|safety\s+tip|security\s+tip"
    r"|safe\s+banking|be\s+alert|be\s+careful|advisory)\b|सावधान",
    _I,
)
_CLAUSE = re.compile(r"[,;:]|\s+but\s+|\s+lekin\s+|\s+लेकिन\s+", _I)
_SENTENCE = re.compile(r"(?<=[.!?।])\s+|(?<=[.!?।]['\")\]])\s+|\n+")


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for curly, straight in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(curly, straight)
    return text


def _guarded(sentence: str) -> bool:
    return any(p.search(sentence) for p in (*_GUARD_ME, *_GUARD_MONEY))


def _unnegated_action(sentence: str) -> bool:
    """True if some action verb in the sentence is not under a nearby negation."""
    if _NEVER_ASK.search(sentence):  # "X will never ask you for A, B or to C": rest is in scope
        sentence = sentence[: _NEVER_ASK.search(sentence).start()]  # type: ignore[union-attr]
    for clause in _CLAUSE.split(sentence):
        for m in _ACTION.finditer(clause):
            before = clause[: m.start()].split()[-6:]
            after = clause[m.end() :]
            negated = any(_NEG_BEFORE.fullmatch(w.strip(".,!?'\"")) for w in before) or bool(
                _NEG_AFTER.match(after)
            )
            if not negated:
                return True
    return False


def _is_warning(sentence: str) -> str | None:
    if not _TARGET.search(sentence):
        return None
    protective = _NEVER_ASK.search(sentence) or _ADVISORY.search(sentence)
    if not protective:
        for clause in _CLAUSE.split(sentence):
            for m in _ACTION.finditer(clause):
                before = clause[: m.start()].split()[-6:]
                if any(
                    _NEG_BEFORE.fullmatch(w.strip(".,!?'\"")) for w in before
                ) or _NEG_AFTER.match(clause[m.end() :]):
                    protective = m
                    break
    if not protective or _unnegated_action(sentence):
        return None
    return "never_ask" if _NEVER_ASK.search(sentence) else "negated_or_advisory"


def _classify(sentence: str, prev_kind: Kind | None) -> tuple[Kind, str] | None:
    s = sentence.strip()
    if not s or _guarded(s):
        return None
    for pat, rid in _DISCLAIMER:
        if pat.search(s):
            return "disclaimer", rid
    for pat, rid in _NOTIFICATION:
        if pat.search(s):
            return "notification", rid
    w = _is_warning(s)
    if w:
        return "warning", w
    if prev_kind is not None and _FOOTER_TAIL.match(s) and len(s.split()) <= 16:
        return prev_kind, "follow_on"
    return None


def _signature_split(text: str) -> tuple[str, str]:
    """Split off an RFC 3676 signature block ('-- ' alone on a line) in multi-line text."""
    m = re.search(r"\n-- ?\n", text)
    if not m:
        return text, ""
    return text[: m.start()], text[m.end() :]


def strip_context(text: str) -> ContextResult:
    """Return the text with disclaimers, quoted notifications, protective warnings and
    signature blocks removed (each replaced by a single space), plus what was removed."""
    norm = _normalise(text)
    body, sig = _signature_split(norm)
    removed: list[Removed] = []
    if sig.strip():
        sig_lines = [ln for ln in sig.splitlines() if ln.strip()]
        keep_sig = [ln for ln in sig_lines if _guarded(ln)]
        if not keep_sig:
            removed.append(Removed("signature", "rfc3676", sig.strip()))
        else:
            body = body + "\n" + sig
    kept: list[str] = []
    prev: Kind | None = None
    for sentence in _SENTENCE.split(body):
        hit = _classify(sentence, prev)
        if hit is None:
            kept.append(sentence)
            prev = None
        else:
            removed.append(Removed(hit[0], hit[1], sentence.strip()))
            prev = hit[0]
    cleaned = " ".join(s.strip() for s in kept if s.strip())
    return ContextResult(original=text, cleaned=cleaned, removed=removed)
