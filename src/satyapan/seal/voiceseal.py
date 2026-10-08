"""Voice Seal DSP: embed and detect a keyed, zero-bit seal in speech (numpy + scipy only).

What the seal is, in plain words
--------------------------------
Split speech into 12 frequency bands between 300 and 3400 Hz (the range every phone codec
keeps). Every 48 ms ("chip"), nudge each band's level up or down by 2 dB, following a secret
+/-1 pattern. Ears barely notice a 2 dB wobble spread over many bands; a verifier that knows the
pattern can find it. The pattern changes every epoch (5 s) and comes from the TESLA key of that
epoch (see tesla.py), so it is bound to one executive's device, one meeting and one epoch.

How the verifier finds it
-------------------------
1. Measure each band's energy (in dB) for every 8 ms frame of the received audio.
2. Remove what speech itself does: subtract the frame's overall loudness (all bands go up and
   down together when you talk louder), subtract a 3-chip moving average per band (syllables are
   slower than chips), and subtract the average of the two neighbouring bands (vowel formants
   are wider than one band). What is left ("residual" R) is mostly the seal plus noise.
3. Average R inside every (band, chip) cell that contains speech, then correlate with the
   pattern p (+1/-1):   z = sum(p * R) / sqrt(sum(R^2)).

Why the false-alarm rate is set by maths, not by training data
---------------------------------------------------------------
If the audio was NOT sealed with this pattern (any clone, any relay from another meeting, any
replay at a later epoch, any other executive's key), p is independent of R. Then, for the given
audio, z is a sum of +/-R terms with random signs: mean 0, variance exactly 1, and approximately
N(0, 1); rigorously P(z >= t) <= exp(-t^2 / 2) (Hoeffding). This holds for every voice, accent
and language, because nothing in it depends on the voice.

The receiver protocol (v2, unbiased - read this before changing anything)
-------------------------------------------------------------------------
The verifier does not know the exact network/codec delay or where a recording starts. It
searches over candidate offsets ONCE ("acquisition"), with a threshold that pays for every
offset tried (Bonferroni: n_offsets x tail <= ALPHA_ACQ). Afterwards every epoch is scored at
that FIXED offset, so each later z is again N(0, 1) under "not sealed".

Lesson from the lab (v1): re-searching +/-2 frames in every epoch and summing the per-epoch
maxima biases the "not sealed" scores upwards; the sum drifted past the threshold once in 560
attack sessions. Never re-maximise the offset per epoch. If clock drift forces tracking, search
the drift (`rates`) inside the single acquisition and pay for it in the threshold.

Later looks (Stouffer's combined z over post-acquisition epochs) use alpha spending: look k
has threshold isf(ALPHA_STOUFFER / (k (k + 1))), so the total false-seal budget of all later
looks together is ALPHA_STOUFFER, however long the call runs.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from scipy.signal import istft, stft
from scipy.special import ndtri

from satyapan.seal.tesla import epoch_seed

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
Pattern = npt.NDArray[np.int8]

SR = 16_000  # Hz: everything is analysed at 16 kHz mono
NFFT = 512  # 32 ms analysis window
HOP = 128  # 8 ms hop = one "frame"
VERSION = "satyapan-voiceseal/1.0"

# ---- thresholds (documented in docs/SEAL.md and research/seal/README.md) ----
TAU_EPOCH = 4.0  # an epoch counts as "sealed" when z >= 4 (Gaussian tail 3.2e-5)
TAU_GAP = 2.0  # an epoch with speech and z < 2 counts as "unsealed" (a gap)
ALPHA_ACQ = 1e-6  # false-seal budget per acquisition look, shared by all offsets tried
ALPHA_STOUFFER = 1e-6  # false-seal budget of ALL later looks together (alpha spending)
MIN_ACTIVE = 0.6  # a (band, chip) cell is used when >= 60 % of its frames contain speech
MIN_CELLS_FRACTION = 0.25  # an epoch is judged only if >= 25 % of its cells contain speech
LIVE_LOOKS = (1, 2)  # live call: decide after epoch 0, then after epochs 0+1
FILE_LOOKS = (1, 2, 4)  # uploads also try 4 epochs (robust to silence at the start)


@dataclass(frozen=True)
class SealParams:
    """Seal parameter set. All timing is in 8 ms frames so embedder and detector agree exactly.

    An epoch is 625 frames = 5.000 s: 104 chips x 6 frames carry the pattern and the last frame
    is an unmodulated guard, so audio epochs line up with the wall-clock TESLA epochs.
    """

    amp_db: float = 2.0  # +/- level nudge per band per chip (1.5 dB is the quieter fallback)
    n_bands: int = 12
    f_lo: float = 300.0
    f_hi: float = 3400.0
    chip_frames: int = 6  # 48 ms
    chips_per_epoch: int = 104
    epoch_frames: int = 625  # 5 s
    ramp_frames: int = 3  # smooth chip transitions (avoids clicks)
    resid_chips: int = 3  # detector: temporal high-pass window, in chips
    spec_hp: bool = True  # detector: subtract the mean of the two neighbouring bands

    def __post_init__(self) -> None:
        if self.chip_frames * self.chips_per_epoch > self.epoch_frames:
            raise ValueError("pattern longer than the epoch")
        if not 0 < self.f_lo < self.f_hi < SR / 2:
            raise ValueError("bad band edges")
        if self.n_bands < 3 or self.chip_frames < 2:
            raise ValueError("need >= 3 bands and >= 2 frames per chip")

    @property
    def epoch_s(self) -> float:
        return self.epoch_frames * HOP / SR

    @property
    def chip_s(self) -> float:
        return self.chip_frames * HOP / SR

    @property
    def edges(self) -> FloatArray:
        return np.geomspace(self.f_lo, self.f_hi, self.n_bands + 1)

    @property
    def params_id(self) -> str:
        return (
            f"vs1-{self.n_bands}b-{self.f_lo:.0f}-{self.f_hi:.0f}-{self.chip_frames}f-"
            f"{self.chips_per_epoch}c-{self.epoch_frames}f-{self.amp_db:.1f}dB"
        )

    @classmethod
    def from_id(cls, params_id: str) -> SealParams:
        m = re.fullmatch(r"vs1-(\d+)b-(\d+)-(\d+)-(\d+)f-(\d+)c-(\d+)f-([\d.]+)dB", params_id)
        if m is None:
            raise ValueError(f"unknown seal params id {params_id!r}")
        nb, lo, hi, cf, cpe, ef, amp = m.groups()
        return cls(
            amp_db=float(amp),
            n_bands=int(nb),
            f_lo=float(lo),
            f_hi=float(hi),
            chip_frames=int(cf),
            chips_per_epoch=int(cpe),
            epoch_frames=int(ef),
        )


DEFAULT_PARAMS = SealParams()


def isf(alpha: float) -> float:
    """Gaussian inverse survival function: the z with P(N(0,1) >= z) = alpha."""
    return float(-ndtri(alpha))


def tau_acquisition(n_candidates: int, alpha: float = ALPHA_ACQ) -> float:
    """Acquisition threshold when the max is taken over n_candidates offsets (x rates)."""
    return isf(alpha / max(1, n_candidates))


def tau_stouffer(look: int, alpha: float = ALPHA_STOUFFER) -> float:
    """Threshold for the k-th later look (k = 1, 2, ...): sum over k of alpha/(k(k+1)) = alpha."""
    return isf(alpha / (look * (look + 1)))


def hoeffding_tail(t: float) -> float:
    """Distribution-free bound P(z >= t) <= exp(-t^2/2) for a random-sign sum (H0)."""
    return math.exp(-t * t / 2)


# ------------------------------------------------------------------ pattern


def epoch_pattern(key: bytes, binding: str, epoch: int, p: SealParams = DEFAULT_PARAMS) -> Pattern:
    """Keyed +/-1 pattern of shape (n_bands, chips_per_epoch) for one epoch.

    bits = SHAKE256(HMAC-SHA256(K_e, "seal|<binding>|<e>")); +1 for a 1 bit, -1 for a 0 bit.
    """
    n = p.n_bands * p.chips_per_epoch
    raw = hashlib.shake_256(epoch_seed(key, binding, epoch)).digest((n + 7) // 8)
    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:n].astype(np.int8)
    return (2 * bits - 1).astype(np.int8).reshape(p.n_bands, p.chips_per_epoch)


# ------------------------------------------------------------------ STFT helpers


def _stft(x: FloatArray) -> tuple[FloatArray, npt.NDArray[np.complex128]]:
    f, _, z = stft(x, fs=SR, window="hann", nperseg=NFFT, noverlap=NFFT - HOP)
    return np.asarray(f, dtype=np.float64), np.asarray(z, dtype=np.complex128)


def _band_masks(freqs: FloatArray, p: SealParams) -> BoolArray:
    e = p.edges
    return np.stack([(freqs >= e[k]) & (freqs < e[k + 1]) for k in range(p.n_bands)])


def _smooth_rows(a: FloatArray, kernel: FloatArray) -> FloatArray:
    return np.stack([np.convolve(row, kernel, mode="same") for row in a])


# ------------------------------------------------------------------ embed


def embed(
    x: FloatArray,
    key_for_epoch: Callable[[int], bytes] | Sequence[bytes],
    binding: str,
    p: SealParams = DEFAULT_PARAMS,
    start_epoch: int = 0,
) -> FloatArray:
    """Seal mono 16 kHz float audio. Sample 0 is the start of epoch `start_epoch`.

    `key_for_epoch(e)` (or a list indexed by absolute epoch) returns K_e. The output has the
    same length as the input. Only the level of 12 bands is modulated; phase is untouched.
    """
    keys = key_for_epoch if callable(key_for_epoch) else key_for_epoch.__getitem__
    x = np.asarray(x, dtype=np.float64)
    f, z = _stft(x)
    n_frames = z.shape[1]
    ef, cf, cpe = p.epoch_frames, p.chip_frames, p.chips_per_epoch
    n_epochs = math.ceil(n_frames / ef)
    s = np.zeros((p.n_bands, n_epochs * ef))
    for i in range(n_epochs):
        e = start_epoch + i
        pat = epoch_pattern(keys(e), binding, e, p)
        s[:, i * ef : i * ef + cpe * cf] = np.repeat(pat, cf, axis=1)
    s = s[:, :n_frames]
    if p.ramp_frames > 1:
        ramp = np.hanning(p.ramp_frames + 2)[1:-1]
        s = _smooth_rows(s, ramp / ramp.sum())
    w = _smooth_rows(_band_masks(f, p).astype(np.float64), np.ones(3) / 3)  # soft band edges
    gain_db = p.amp_db * (w.T @ s)  # (n_freq, n_frames)
    _, y_raw = istft(
        z * (10 ** (gain_db / 20)), fs=SR, window="hann", nperseg=NFFT, noverlap=NFFT - HOP
    )
    y: FloatArray = np.asarray(y_raw, dtype=np.float64)[: len(x)]
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))
    return y


# ------------------------------------------------------------------ detect


@dataclass
class Features:
    """Per-frame band residuals (n_bands, T) + speech mask (T,), with cumulative sums cached.

    In the product these never leave the verifier's machine; they are not a voiceprint (they
    contain no spectral envelope, only what is left after removing it).
    """

    resid: FloatArray
    active: BoolArray
    _ca: FloatArray = field(init=False, repr=False)
    _cr: FloatArray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        act = self.active.astype(np.float64)
        self._ca = np.concatenate([[0.0], np.cumsum(act)])
        rw = self.resid * act
        self._cr = np.concatenate([np.zeros((rw.shape[0], 1)), np.cumsum(rw, axis=1)], axis=1)

    @property
    def n_frames(self) -> int:
        return int(self.resid.shape[1])

    @property
    def speech_seconds(self) -> float:
        return float(self.active.sum()) * HOP / SR


def features(y: FloatArray, p: SealParams = DEFAULT_PARAMS) -> Features:
    """Band log-energy residuals of received audio (see module docstring, steps 1-2)."""
    f, z = _stft(np.asarray(y, dtype=np.float64))
    power = np.abs(z) ** 2
    masks = _band_masks(f, p)
    energy = np.stack([10 * np.log10(power[m].sum(axis=0) + 1e-10) for m in masks])
    total = 10 * np.log10(power[masks.any(axis=0)].sum(axis=0) + 1e-10)
    active = total > (np.percentile(total, 99) - 35)  # speech = within 35 dB of the loudest
    r = energy - energy.mean(axis=0, keepdims=True)  # remove overall loudness
    win = p.resid_chips * p.chip_frames
    r = r - _smooth_rows(r, np.ones(win) / win)  # remove syllable-rate motion
    if p.spec_hp:
        up = np.vstack([r[1:2], r[:-1]])
        dn = np.vstack([r[1:], r[-2:-1]])
        r = r - 0.5 * (up + dn)  # remove formant-width motion
    return Features(resid=np.asarray(r, dtype=np.float64), active=np.asarray(active))


def score_epoch(
    feat: Features,
    pattern: Pattern,
    start_frame: float,
    p: SealParams = DEFAULT_PARAMS,
    rate: float = 1.0,
) -> tuple[float, int]:
    """Self-normalised correlation z of one epoch starting at `start_frame`.

    `rate` > 1 means the received audio runs slower (stretched). Returns (z, cells_used);
    (0.0, 0) when the epoch has no speech or lies outside the audio.
    """
    cf = p.chip_frames
    g = 1 if cf > 4 else 0  # skip one frame at each chip edge (ramp + STFT smear)
    j = np.arange(pattern.shape[1])
    starts = np.round(start_frame + j * cf * rate).astype(np.int64) + g
    ends = np.round(start_frame + (j + 1) * cf * rate).astype(np.int64) - g
    ok = (starts >= 0) & (ends <= feat.n_frames) & (ends > starts)
    if not ok.any():
        return 0.0, 0
    s, e = starts[ok], ends[ok]
    n_act = feat._ca[e] - feat._ca[s]
    use = n_act / (e - s) >= MIN_ACTIVE
    if not use.any():
        return 0.0, 0
    cell_r = (feat._cr[:, e[use]] - feat._cr[:, s[use]]) / n_act[use]  # (bands, chips)
    pt = pattern[:, ok][:, use]
    den = float((cell_r * cell_r).sum())
    if den <= 0:
        return 0.0, 0
    return float((pt * cell_r).sum() / math.sqrt(den)), int(cell_r.size)


@dataclass(frozen=True)
class EpochResult:
    epoch: int  # absolute epoch index (session epoch)
    start_frame: float
    z: float
    cells: int


@dataclass(frozen=True)
class Detection:
    """Outcome of the receiver protocol for one session and one stream/file."""

    sealed: bool
    decided_by: str  # acquisition_1 | acquisition_2 | acquisition_4 | stouffer | not_sealed
    decided_at_epoch: int | None  # relative epoch index after which the verdict was reached
    offset_frames: int
    rate: float
    acquisition_statistic: float
    acquisition_threshold: float
    n_candidates: int
    stouffer_z: float | None
    epochs: list[EpochResult]

    def time_to_verdict_s(self, p: SealParams = DEFAULT_PARAMS) -> float | None:
        """Seconds of sealed audio needed (from the start of the first epoch)."""
        if self.decided_at_epoch is None:
            return None
        return (self.decided_at_epoch + 1) * p.epoch_s


def detect(
    feat: Features,
    patterns: Sequence[Pattern],
    offsets: Sequence[int],
    p: SealParams = DEFAULT_PARAMS,
    looks: Sequence[int] = LIVE_LOOKS,
    rates: Sequence[float] = (1.0,),
    first_epoch: int = 0,
    alpha_scale: float = 1.0,
) -> Detection:
    """Receiver protocol v2. patterns[i] is the pattern of epoch first_epoch + i.

    1. Acquisition: for each look k in `looks` (k = number of epochs), take the max over all
       candidates (offset x rate) of the combined z of epochs 0..k-1. Sealed if it reaches
       tau_acquisition(n_candidates). The LAST look's argmax fixes the offset and rate.
    2. Every epoch is scored at that fixed offset/rate (no per-epoch re-search).
    3. If no acquisition look fired: Stouffer's z over post-acquisition epochs that contain
       speech, cumulatively, with alpha-spending thresholds tau_stouffer(look).

    `alpha_scale` < 1 tightens every threshold, e.g. 1/S when the same audio is checked
    against S candidate sessions (Bonferroni over sessions).
    """
    if not patterns:
        raise ValueError("no patterns (no disclosed keys)")
    looks = sorted({k for k in looks if 1 <= k <= len(patterns)}) or [1]
    k_max = looks[-1]
    ef = p.epoch_frames
    cands = [(off, r) for r in rates for off in offsets]
    n_cand = len(cands)
    tau_acq = tau_acquisition(n_cand, ALPHA_ACQ * alpha_scale)
    # per-candidate z of the first k_max epochs
    zmat = np.zeros((n_cand, k_max))
    nmat = np.zeros((n_cand, k_max), dtype=np.int64)
    for i, (off, r) in enumerate(cands):
        for e in range(k_max):
            zmat[i, e], nmat[i, e] = score_epoch(feat, patterns[e], off + e * ef * r, p, r)
    best_stat: dict[int, float] = {}
    best_idx = 0
    for k in looks:
        cnt = (nmat[:, :k] > 0).sum(axis=1)
        stat = np.where(cnt > 0, zmat[:, :k].sum(axis=1) / np.sqrt(np.maximum(cnt, 1)), 0.0)
        best_idx = int(np.argmax(stat))
        best_stat[k] = float(stat[best_idx])
    off, rate = cands[best_idx]
    epochs: list[EpochResult] = []
    for i, pat in enumerate(patterns):
        start = off + i * ef * rate
        z, n = score_epoch(feat, pat, start, p, rate)
        if n == 0 and start >= feat.n_frames:
            break
        epochs.append(EpochResult(first_epoch + i, float(start), z, n))
    for k in looks:
        if best_stat[k] >= tau_acq:
            return Detection(
                sealed=True,
                decided_by=f"acquisition_{k}",
                decided_at_epoch=k - 1,
                offset_frames=off,
                rate=rate,
                acquisition_statistic=best_stat[k],
                acquisition_threshold=tau_acq,
                n_candidates=n_cand,
                stouffer_z=None,
                epochs=epochs,
            )
    post = [(i, er) for i, er in enumerate(epochs) if i >= k_max and er.cells > 0]
    total, stouffer = 0.0, None
    for look, (i, er) in enumerate(post, start=1):
        total += er.z
        stouffer = total / math.sqrt(look)
        if stouffer >= tau_stouffer(look, ALPHA_STOUFFER * alpha_scale):
            return Detection(
                sealed=True,
                decided_by="stouffer",
                decided_at_epoch=i,
                offset_frames=off,
                rate=rate,
                acquisition_statistic=best_stat[k_max],
                acquisition_threshold=tau_acq,
                n_candidates=n_cand,
                stouffer_z=stouffer,
                epochs=epochs,
            )
    return Detection(
        sealed=False,
        decided_by="not_sealed",
        decided_at_epoch=None,
        offset_frames=off,
        rate=rate,
        acquisition_statistic=best_stat[k_max],
        acquisition_threshold=tau_acq,
        n_candidates=n_cand,
        stouffer_z=stouffer,
        epochs=epochs,
    )


def snr_db(x: FloatArray, y: FloatArray) -> float:
    """Waveform SNR of the seal (y - x). Meaningless for a level pattern; reported for scale."""
    return float(10 * np.log10(np.sum(x**2) / max(np.sum((y - x) ** 2), 1e-20)))
