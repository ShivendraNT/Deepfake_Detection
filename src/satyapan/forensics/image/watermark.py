"""Invisible-watermark check for Stable Diffusion outputs (DWT-DCT, `invisible-watermark`).

Stability AI's reference pipelines and Hugging Face diffusers (SDXL) embed a fixed message in
every image with the `invisible-watermark` library's dwtDct method. The decoder below is a
NumPy re-implementation of that library's `EmbedMaxDct.decode` (MIT licence, see
THIRD_PARTY.md), vectorised and without its PyTorch dependency; tests check it bit-for-bit
against the library when it is installed.

Messages checked (bit accuracy against the known message; chance level is 50 %):
  * SDXL (diffusers / sgm): 48-bit 0b101100111110110010010000011110111011000110011110
  * Stable Diffusion 1.x reference scripts: bytes "StableDiffusionV1" (136 bits)
  * Stable Diffusion 2.x reference scripts: bytes "SDV2" (32 bits)
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

import numpy as np

SDXL_BITS = [int(b) for b in bin(0b101100111110110010010000011110111011000110011110)[2:]]


def _bytes_bits(s: bytes) -> list[int]:
    return [int(b) for byte in s for b in f"{byte:08b}"]


MESSAGES = {
    "Stable Diffusion XL (diffusers / Stability AI)": SDXL_BITS,
    "Stable Diffusion 1.x (reference scripts)": _bytes_bits(b"StableDiffusionV1"),
    "Stable Diffusion 2.x (reference scripts)": _bytes_bits(b"SDV2"),
}
SCALE = 36.0  # the library's default scale for the U channel
BLOCK = 4


def block_bits(rgb: np.ndarray) -> np.ndarray:
    """Per-block bit votes in raster order, exactly as EmbedMaxDct.decode computes them."""
    import cv2

    bgr = np.ascontiguousarray(rgb[..., ::-1])
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
    row, col = yuv.shape[:2]
    u = yuv[: row // 4 * 4, : col // 4 * 4, 1].astype(np.float64)
    ca = (u[0::2, 0::2] + u[0::2, 1::2] + u[1::2, 0::2] + u[1::2, 1::2]) / 2.0  # Haar cA
    r, c = ca.shape[0] // BLOCK, ca.shape[1] // BLOCK
    blocks = (
        ca[: r * BLOCK, : c * BLOCK]
        .reshape(r, BLOCK, c, BLOCK)
        .transpose(0, 2, 1, 3)
        .reshape(r * c, BLOCK * BLOCK)
    )
    pos = np.argmax(np.abs(blocks[:, 1:]), axis=1) + 1
    val = np.abs(blocks[np.arange(len(blocks)), pos])
    return ((val % SCALE) > 0.5 * SCALE).astype(np.float64)


def decode(rgb: np.ndarray, length: int, votes: np.ndarray | None = None) -> list[int]:
    v = block_bits(rgb) if votes is None else votes
    idx = np.arange(len(v)) % length
    sums = np.bincount(idx, weights=v, minlength=length)
    counts = np.bincount(idx, minlength=length)
    avg = sums / np.maximum(counts, 1)
    return [int(x) for x in (avg * 255 > 127)]


@dataclass(frozen=True)
class WatermarkMatch:
    name: str
    bits: int
    matching: int
    p_chance: float  # probability of at least this many matches on an unmarked image

    @property
    def accuracy(self) -> float:
        return self.matching / self.bits


def p_at_least(k: int, n: int) -> float:
    return sum(comb(n, i) for i in range(k, n + 1)) / 2.0**n


def check(rgb: np.ndarray) -> list[WatermarkMatch]:
    if min(rgb.shape[:2]) < 256:
        return []
    votes = block_bits(rgb)
    out = []
    for name, msg in MESSAGES.items():
        got = decode(rgb, len(msg), votes)
        k = sum(int(a == b) for a, b in zip(got, msg, strict=True))
        out.append(WatermarkMatch(name, len(msg), k, p_at_least(k, len(msg))))
    return out
