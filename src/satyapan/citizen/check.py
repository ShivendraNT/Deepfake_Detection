"""Citizen Scam Check for anything a person forwards: text, screenshot, voice note, photo,
video, e-mail or PDF (finale, consumer journey).

The file goes through the quick check (every detector on this device, band from the policy
engine, nothing kept); any text it contains (the message, what the voice note said, what the
screenshot reads) also goes through the T24 "impossible claim" rules, and the band is the
higher of the two (raise-only). The answer is coarse on purpose: band, what to do, why, and
what could not be checked here. Never a score.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from satyapan.citizen.rules import ACTION_TEXT, IMPOSSIBLE_CLAIMS, LINKS, SHARE_TEXT, scam_check
from satyapan.contracts.enums import Band, Channel, Lang
from satyapan.contracts.explain import CitizenFileResult
from satyapan.policy.bands import rank

CHECKED = {
    "voice": {Lang.EN: "the voice (cloned or real)", Lang.HI: "आवाज़ (नकली/क्लोन या असली)"},
    "face": {Lang.EN: "the face (swapped or real)", Lang.HI: "चेहरा (बदला हुआ या असली)"},
    "text": {Lang.EN: "the wording (known scam patterns)", Lang.HI: "शब्द (जाने-पहचाने ठगी पैटर्न)"},
    "asks": {Lang.EN: "what it asks you to do", Lang.HI: "यह आपसे क्या करवाना चाहता है"},
}
MAX_BYTES = 40 * 1024 * 1024


def citizen_check(
    state: Any, data: bytes, filename: str | None, media_type: str, lang: Lang = Lang.EN
) -> CitizenFileResult:
    from satyapan.quickcheck import quick_check

    if len(data) > MAX_BYTES:
        raise ValueError("file too large for a quick check (40 MB max)")
    r = quick_check(state, data, filename, media_type, lang)
    words = r.transcript or (
        data.decode("utf-8", errors="replace") if r.channel == Channel.MANUAL else ""
    )
    band, why, hits = r.band, [], []
    if words.strip():
        rules = scam_check(words, lang)
        hits = rules.rule_hits
        if rank(rules.band) > rank(band):
            band = rules.band
        why += [
            (en if lang == Lang.EN else hi)
            for rule_id, _pat, en, hi in IMPOSSIBLE_CLAIMS
            if rule_id in hits
        ]
    why += r.why
    action = ACTION_TEXT[lang][band]
    links = dict(LINKS)
    links["share"] = "https://wa.me/?text=" + quote(f"{action} {SHARE_TEXT[lang]}")
    checked = [CHECKED[k][lang] for k in ("voice", "face", "text", "asks") if k in r.findings]
    return CitizenFileResult(
        band=band,
        action_text=action,
        rule_hits=hits,
        links=links,
        why=list(dict.fromkeys(why))[:6],
        checked=checked,
        not_checked=r.not_checked,
        heard_or_read=_tidy(words) if r.channel != Channel.MANUAL and words else None,
        seconds=r.seconds,
    )


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:600]


__all__ = ["Band", "citizen_check"]
