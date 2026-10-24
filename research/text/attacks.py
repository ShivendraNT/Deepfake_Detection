"""Code-generated evasion attacks on scam texts (the test kit's "synthetic data" for text).

Real scam SMS and phishing mails dodge filters with cheap character tricks. We apply each to
the FRAUD texts of every test split (seeded, so the attacked set is reproducible from this
file alone) and measure how many are still caught at the frozen threshold:

  homoglyph   swap ~30% of Latin letters for Cyrillic/Greek look-alikes (а, е, о, р, с ...)
  leet        a->4/@, e->3, i->1, o->0, s->$/5 in ~40% of eligible letters
  zero_width  insert U+200B inside ~50% of the words
  spacing     spell the 3 longest words letter by letter ("O T P")
  combined    all four at once

The attacks never touch legitimate texts (attackers obfuscate scams, not invoices), so the
false-alarm side is measured on the clean legitimate test texts.
"""

from __future__ import annotations

import random  # provenance: seeded-resampling-ok

HOMOGLYPH = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у", "i": "і",
             "A": "А", "E": "Е", "O": "О", "P": "Р", "C": "С", "B": "В", "H": "Н", "K": "К",
             "M": "М", "T": "Т", "X": "Х"}  # fmt: skip
LEET = {"a": "4@", "e": "3", "i": "1", "o": "0", "s": "$5", "t": "7"}
ZW = "​"
ATTACKS = ("homoglyph", "leet", "zero_width", "spacing", "combined")


def homoglyph(text: str, rng: random.Random, p: float = 0.3) -> str:
    return "".join(HOMOGLYPH[ch] if ch in HOMOGLYPH and rng.random() < p else ch for ch in text)


def leet(text: str, rng: random.Random, p: float = 0.4) -> str:
    out = []
    for ch in text:
        low = ch.lower()
        if low in LEET and rng.random() < p:
            out.append(rng.choice(LEET[low]))
        else:
            out.append(ch)
    return "".join(out)


def zero_width(text: str, rng: random.Random, p: float = 0.5) -> str:
    words = text.split(" ")
    out = []
    for w in words:
        if len(w) > 3 and rng.random() < p:
            k = rng.randrange(1, len(w))
            w = w[:k] + ZW + w[k:]
        out.append(w)
    return " ".join(out)


def spacing(text: str, rng: random.Random, n: int = 3) -> str:
    words = text.split(" ")
    longest = sorted(range(len(words)), key=lambda i: -len(words[i]))[:n]
    for i in longest:
        if words[i].isalpha():
            words[i] = " ".join(words[i])
    return " ".join(words)


def attack(text: str, kind: str, seed: str) -> str:
    rng = random.Random(seed)
    if kind == "homoglyph":
        return homoglyph(text, rng)
    if kind == "leet":
        return leet(text, rng)
    if kind == "zero_width":
        return zero_width(text, rng)
    if kind == "spacing":
        return spacing(text, rng)
    if kind == "combined":
        return zero_width(homoglyph(leet(spacing(text, rng), rng), rng), rng)
    raise ValueError(kind)
