"""Band ordering helpers. PRE-IMPLEMENTED (T02)."""

from __future__ import annotations

from satyapan.contracts.enums import BAND_ORDER, Band

_BY_RANK: dict[int, Band] = {v: k for k, v in BAND_ORDER.items()}


def rank(band: Band) -> int:
    return BAND_ORDER[band]


def bmax(*bands: Band) -> Band:
    """Highest band. bmax() with no args is PASS."""
    if not bands:
        return Band.PASS
    return max(bands, key=rank)


def bmin(*bands: Band) -> Band:
    return min(bands, key=rank)


def plus_one(band: Band) -> Band:
    """PASS->VERIFY, VERIFY->HOLD, HOLD->HOLD."""
    return _BY_RANK[min(rank(band) + 1, rank(Band.HOLD))]


def cap(band: Band, ceiling: Band) -> Band:
    return bmin(band, ceiling)
