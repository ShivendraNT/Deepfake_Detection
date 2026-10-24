"""Hashed TF-IDF features: the same function in training (research/text/) and in Satya.

Word unigrams and bigrams plus character 2-5-grams inside word boundaries, after
`deobfuscate` and casefolding. Each feature string is hashed with CRC-32: the low 20 bits pick
one of 2**20 buckets, bit 31 picks a sign (signed hashing cancels collisions on average).
Term frequency is sublinear (1 + log tf); the IDF weights and the classifier are learned.
Pure Python + numpy; no model files are needed to compute features.
"""

from __future__ import annotations

import math
import re
import zlib
from collections import Counter

from satyapan.textrisk.normalize import deobfuscate

N_BITS = 20
N_FEATURES = 1 << N_BITS
MASK = N_FEATURES - 1
MAX_CHARS = 2000  # subject + opening of a message; long tails add little and cost time
MAX_WORD = 30
_WORD = re.compile(r"\w+", re.UNICODE)


def prepare(text: str) -> str:
    return deobfuscate(text[: MAX_CHARS * 2])[:MAX_CHARS].casefold()


def raw_counts(text: str, normalise: bool = True) -> Counter[str]:
    t = prepare(text) if normalise else text[:MAX_CHARS].casefold()
    words = [w[:MAX_WORD] for w in _WORD.findall(t)]
    feats: Counter[str] = Counter()
    for w in words:
        feats["w" + w] += 1
    for a, b in zip(words, words[1:], strict=False):
        feats["b" + a + " " + b] += 1
    for w in words:
        padded = f" {w} "
        for n in (2, 3, 4, 5):
            for i in range(len(padded) - n + 1):
                feats["c" + padded[i : i + n]] += 1
    return feats


def hashed_tf(text: str, normalise: bool = True) -> dict[int, float]:
    """{bucket: signed sublinear tf} for one text (before IDF and L2 normalisation)."""
    out: dict[int, float] = {}
    for key, count in raw_counts(text, normalise).items():
        h = zlib.crc32(key.encode("utf-8"))
        idx = h & MASK
        sign = -1.0 if h & 0x80000000 else 1.0
        out[idx] = out.get(idx, 0.0) + sign * (1.0 + math.log(count))
    return out
