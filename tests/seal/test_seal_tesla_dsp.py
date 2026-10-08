"""Voice Seal core: TESLA chain, binding, pattern, embed/detect, and the unbiased protocol."""

from __future__ import annotations

import os

import numpy as np
import pytest

from satyapan.seal import tesla
from satyapan.seal import voiceseal as vs
from tests.seal.seal_fixtures import NOW, speechlike

BINDING = "meet:abc-defg-hij"


def test_chain_links_and_commitment() -> None:
    c, keys = tesla.make_chain(b"seed", 20)
    assert len(keys) == 20 and c == tesla.h(keys[0])
    for e in range(1, 20):
        assert tesla.h(keys[e]) == keys[e - 1]
    assert tesla.key_matches_commitment(c, keys[19], 19)
    assert not tesla.key_matches_commitment(c, keys[19], 18)
    assert not tesla.key_matches_commitment(c, os.urandom(32), 19)
    assert tesla.key_follows(keys[3], 3, keys[7], 7)
    assert not tesla.key_follows(keys[7], 7, keys[3], 3)  # backwards is never valid
    assert tesla.earlier_keys(keys[5], 5) == {e: keys[e] for e in range(6)}


def test_epoch_timing() -> None:
    assert not tesla.epoch_has_ended(NOW, 5.0, 0, NOW)
    assert tesla.epoch_has_ended(NOW, 5.0, 0, tesla.epoch_end(NOW, 5.0, 0))
    assert tesla.epoch_end(NOW, 5.0, 9).timestamp() - NOW.timestamp() == 50


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("https://meet.google.com/abc-defg-hij?authuser=0", "meet:abc-defg-hij"),
        ("ABC-DEFG-HIJ", "meet:abc-defg-hij"),
        ("meet.google.com/abc-defg-hij/", "meet:abc-defg-hij"),
        ("note:VN-0042", "note:VN-0042"),
        ("https://teams.example/l/meetup-join/xyz#a", "url:teams.example/l/meetup-join/xyz"),
    ],
)
def test_canonical_binding(raw: str, want: str) -> None:
    assert tesla.canonical_binding(raw) == want


def test_pattern_is_keyed_bound_and_balanced() -> None:
    _, keys = tesla.make_chain(b"seed", 10)
    p = vs.epoch_pattern(keys[3], BINDING, 3)
    assert p.shape == (12, 104) and set(np.unique(p)) == {-1, 1}
    assert abs(int(p.sum())) < 100  # roughly balanced
    assert np.array_equal(p, vs.epoch_pattern(keys[3], BINDING, 3))  # deterministic
    for other in (
        vs.epoch_pattern(keys[3], "meet:xyz-uvwq-rst", 3),  # other meeting
        vs.epoch_pattern(keys[3], BINDING, 4),  # other epoch
        vs.epoch_pattern(keys[4], BINDING, 3),  # other key
    ):
        agree = float((p == other).mean())
        assert 0.4 < agree < 0.6


def test_params_id_round_trip_and_epoch_is_5s() -> None:
    p = vs.DEFAULT_PARAMS
    assert p.epoch_s == 5.0 and p.chip_s == 0.048
    assert vs.SealParams.from_id(p.params_id) == p
    with pytest.raises(ValueError):
        vs.SealParams.from_id("vs9-bogus")


def test_thresholds() -> None:
    assert vs.tau_acquisition(51) == pytest.approx(5.49, abs=0.01)
    assert vs.tau_stouffer(1) < vs.tau_stouffer(10) < vs.tau_stouffer(100)
    # alpha spending: the looks' budgets sum to ALPHA_STOUFFER
    assert sum(vs.ALPHA_STOUFFER / (k * (k + 1)) for k in range(1, 10_000)) < vs.ALPHA_STOUFFER
    assert vs.hoeffding_tail(5.0) == pytest.approx(np.exp(-12.5))


def test_embed_is_deterministic_and_length_preserving() -> None:
    x = speechlike(12, seed=3)
    _, keys = tesla.make_chain(b"seed", 10)
    y1, y2 = vs.embed(x, keys, BINDING), vs.embed(x, keys, BINDING)
    assert y1.shape == x.shape and np.array_equal(y1, y2)
    assert 12 < vs.snr_db(x, y1) < 30


@pytest.fixture(scope="module")
def streams() -> dict[str, np.ndarray]:
    x = speechlike(31, seed=11)
    _, k_raj = tesla.make_chain(b"rajesh", 20)
    _, k_mee = tesla.make_chain(b"meera", 20)
    pad = np.zeros(int(0.07 * vs.SR))  # unknown network delay
    return {
        "sealed": np.concatenate([pad, vs.embed(x, k_raj, BINDING)]),
        "clone": np.concatenate([pad, x]),
        "relay": np.concatenate([pad, vs.embed(x, k_raj, "meet:xyz-uvwq-rst")]),
        "other_exec": np.concatenate([pad, vs.embed(x, k_mee, BINDING)]),
        "keys": np.frombuffer(b"".join(k_raj), dtype=np.uint8),
    }


def _keys(streams: dict[str, np.ndarray]) -> list[bytes]:
    raw = streams["keys"].tobytes()
    return [raw[i : i + 32] for i in range(0, len(raw), 32)]


def test_sealed_stream_is_detected_at_the_right_lag(streams: dict[str, np.ndarray]) -> None:
    keys = _keys(streams)
    pats = [vs.epoch_pattern(keys[e], BINDING, e) for e in range(6)]
    d = vs.detect(vs.features(streams["sealed"]), pats, range(-25, 26))
    assert d.sealed and d.decided_by.startswith("acquisition")
    assert abs(d.offset_frames - 0.07 * vs.SR / vs.HOP) <= 1
    assert d.time_to_verdict_s() in (5.0, 10.0)
    assert sum(e.z >= vs.TAU_EPOCH for e in d.epochs) >= 5


@pytest.mark.parametrize("case", ["clone", "relay", "other_exec", "replay"])
def test_attacks_are_not_sealed(streams: dict[str, np.ndarray], case: str) -> None:
    keys = _keys(streams)
    shift = 3 if case == "replay" else 0  # epoch e's audio played at epoch e+3
    pats = [vs.epoch_pattern(keys[e + shift], BINDING, e + shift) for e in range(6)]
    audio = streams["sealed" if case == "replay" else case]
    d = vs.detect(vs.features(audio), pats, range(-25, 26))
    assert not d.sealed
    assert max(e.z for e in d.epochs[2:]) < vs.TAU_EPOCH


def test_fixed_lag_after_acquisition_is_unbiased() -> None:
    """Protocol v2: post-acquisition epochs of unsealed audio are ~N(0,1) (no max bias)."""
    zs = []
    for seed in range(6):
        x = speechlike(41, seed=100 + seed)
        _, keys = tesla.make_chain(bytes([seed]), 10)
        pats = [vs.epoch_pattern(keys[e], BINDING, e) for e in range(8)]
        d = vs.detect(vs.features(x), pats, range(-25, 26))
        zs += [e.z for e in d.epochs[2:] if e.cells]
    zs_arr = np.array(zs)
    assert len(zs_arr) >= 30
    assert abs(zs_arr.mean()) < 0.6  # a per-epoch max over 51 lags would sit near +2
    assert 0.5 < zs_arr.std() < 1.6


def test_rate_search_recovers_time_stretch() -> None:
    from scipy.signal import resample

    x = speechlike(21, seed=5)
    _, keys = tesla.make_chain(b"stretch", 10)
    y = vs.embed(x, keys, BINDING)
    stretched = resample(y, int(len(y) * 1.02))  # plays 2 % slower
    pats = [vs.epoch_pattern(keys[e], BINDING, e) for e in range(4)]
    feat = vs.features(stretched)
    plain = vs.detect(feat, pats, range(0, 26))
    searched = vs.detect(feat, pats, range(0, 26), rates=(0.99, 1.0, 1.01, 1.02, 1.03))
    assert searched.sealed and searched.rate == pytest.approx(1.02)
    # the plain search may or may not catch epoch 0, but loses later epochs
    assert searched.epochs[-1].z > plain.epochs[-1].z
