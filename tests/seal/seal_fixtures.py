"""Generated test audio + a ready-made enrolled executive for the Satyapan Seal tests.

No audio files: `speechlike()` synthesises a voiced, formant-filtered, syllable-gated signal in
memory (deterministic per seed). It is not speech, but it has what the seal detector relies on:
band energies that move from frame to frame, pauses, and a voice-like spectrum.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from scipy.signal import lfilter

from satyapan.seal import voiceseal as vs
from satyapan.seal.passkey import PasskeyStore, RelyingParty
from satyapan.seal.softauth import SoftAuthenticator

NOW = datetime(2026, 10, 7, 10, 0, 0, tzinfo=UTC)
RP = RelyingParty(rp_id="localhost", origins=("http://localhost:5173",))
ORIGIN = "http://localhost:5173"
MEETING = "https://meet.google.com/abc-defg-hij"


def speechlike(seconds: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    sr = vs.SR
    n = int(seconds * sr)
    t = np.arange(n) / sr
    f0 = 120 + 30 * np.sin(2 * np.pi * 0.3 * t) + 10 * rng.standard_normal()
    phase = np.cumsum(f0 / sr)
    src = (np.diff(np.floor(phase), prepend=0) > 0).astype(float) + 0.05 * rng.standard_normal(n)
    env = np.clip(np.sin(2 * np.pi * 4 * t + rng.uniform(0, 6)), 0, None) ** 0.5
    gate = np.repeat(rng.random(int(seconds * 2) + 1) > 0.15, sr // 2)[:n]
    y = np.zeros(n)
    blk = 320  # 20 ms blocks with new formants
    for i in range(0, n, blk):
        out = src[i : i + blk]
        for fc, bw in ((rng.uniform(300, 900), 120), (rng.uniform(900, 2500), 200), (3000, 300)):
            r = np.exp(-np.pi * bw / sr)
            th = 2 * np.pi * fc / sr
            out = lfilter([1 - r], [1, -2 * r * np.cos(th), r * r], out)
        y[i : i + blk] = out
    y = y * env * gate
    return 0.3 * y / np.max(np.abs(y))


def enrolled(employee_id: str = "emp_rajesh") -> tuple[PasskeyStore, SoftAuthenticator]:
    store = PasskeyStore(rp=RP)
    auth = SoftAuthenticator(rp_id=RP.rp_id, origin=ORIGIN)
    opts = store.registration_options(employee_id, employee_id, NOW)
    store.register(employee_id, auth.create(opts), NOW)
    return store, auth


def enrol_more(store: PasskeyStore, employee_id: str) -> SoftAuthenticator:
    auth = SoftAuthenticator(rp_id=RP.rp_id, origin=ORIGIN)
    store.register(
        employee_id, auth.create(store.registration_options(employee_id, employee_id, NOW)), NOW
    )
    return auth
