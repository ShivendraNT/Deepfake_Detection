"""Undo the cheap obfuscations scam messages use to slip past filters.

Scammers write "Ꭺссоunt", "p@ssw0rd", "O T P", or hide zero-width characters inside words so
that keyword filters and n-gram models miss them. Before any model looks at a text we:

1. apply NFKC (full-width letters, ligatures, compatibility forms -> plain letters);
2. drop zero-width and other invisible format characters;
3. fold Cyrillic / Greek / Cherokee look-alike letters to Latin, but only inside words that
   are mostly Latin (a real Hindi, Russian or Greek word is left alone);
4. fold leetspeak digits/symbols to letters, only inside tokens that also contain letters
   ("acc0unt" -> "account"; "2026", "₹500" and "9:30" stay as they are);
5. join letters spaced out one by one ("O T P" -> "OTP").

Pure Python, deterministic. The original text is never changed for display or evidence.
"""

from __future__ import annotations

import re
import unicodedata

# Latin look-alikes (lower-case targets; casefolding happens later).
_CONFUSABLE = {
    # Cyrillic
    "а": "a", "в": "b", "с": "c", "е": "e", "һ": "h", "і": "i", "ј": "j", "к": "k", "м": "m",
    "н": "h", "о": "o", "р": "p", "ԛ": "q", "ѕ": "s", "т": "t", "у": "y", "х": "x", "ԁ": "d",
    "ԝ": "w", "ӏ": "l", "А": "a", "В": "b", "С": "c", "Е": "e", "Н": "h", "І": "i", "Ј": "j",
    "К": "k", "М": "m", "О": "o", "Р": "p", "Ѕ": "s", "Т": "t", "Х": "x", "У": "y",
    # Greek
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "ι": "i", "κ": "k", "τ": "t", "υ": "u", "χ": "x",
    "Α": "a", "Β": "b", "Ε": "e", "Η": "h", "Ι": "i", "Κ": "k", "Μ": "m", "Ν": "n", "Ο": "o",
    "Ρ": "p", "Τ": "t", "Υ": "y", "Χ": "x", "Ζ": "z",
    # Cherokee / Latin extended look-alikes seen in phishing
    "Ꭺ": "a", "Ᏼ": "b", "Ꮯ": "c", "Ꭼ": "e", "Ꮋ": "h", "Ꮶ": "k", "Ꮇ": "m", "Ꮲ": "p", "Ꭲ": "t",
    "ı": "i", "ɑ": "a", "ɡ": "g", "ⅼ": "l",
}  # fmt: skip
_LEET = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s",
         "!": "i", "|": "l"}  # fmt: skip
_INVISIBLE_CATEGORIES = {"Cf"}  # zero-width space/joiners, BOM, bidi controls
_TOKEN = re.compile(r"\S+")
_SPACED = re.compile(r"(?<!\S)(?:[^\W\d_](?:[ .\-_]|$)){3,}", re.UNICODE)


def _is_latin_letter(ch: str) -> bool:
    return ch.isalpha() and ("LATIN" in unicodedata.name(ch, "") or ch.isascii())


def _fold_confusables(token: str) -> str:
    if not any(ch in _CONFUSABLE for ch in token):
        return token
    letters = [ch for ch in token if ch.isalpha()]
    latin = sum(1 for ch in letters if _is_latin_letter(ch))
    mapped = sum(1 for ch in letters if ch in _CONFUSABLE)
    # Fold only when the word is a Latin word with look-alikes mixed in (or entirely
    # look-alikes that spell a Latin word); leave genuine non-Latin words alone.
    if latin == 0 and mapped < len(letters):
        return token
    return "".join(_CONFUSABLE.get(ch, ch) for ch in token)


_EDGE = re.compile(r"^([\W_]*)(.*?)([\W_]*)$", re.UNICODE | re.S)
_ORDINAL = re.compile(r"^\d+(st|nd|rd|th)$", re.I)


def _fold_leet(token: str) -> str:
    lead, core, trail = _EDGE.match(token).groups()  # type: ignore[union-attr]
    if len(core) < 3 or _ORDINAL.match(core):
        return token
    letters = sum(1 for ch in core if ch.isalpha())
    leet = sum(1 for ch in core if ch in _LEET)
    if letters < 2 or leet == 0 or leet > letters:
        return token
    return lead + "".join(_LEET.get(ch, ch) for ch in core) + trail


def _join_spaced(match: re.Match[str]) -> str:
    return re.sub(r"[ .\-_]", "", match.group(0)) + " "


def deobfuscate(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in _INVISIBLE_CATEGORIES)
    text = _TOKEN.sub(lambda m: _fold_leet(_fold_confusables(m.group(0))), text)
    text = _SPACED.sub(_join_spaced, text)
    return re.sub(r"\s+", " ", text).strip()
