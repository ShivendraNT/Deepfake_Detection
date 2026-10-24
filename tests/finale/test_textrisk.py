"""Scam-text model (docs/TEXT_BENCHMARK.md): de-obfuscation, deterministic features, scoring,
and the raise-only, VERIFY-capped policy effect. No network, no datasets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import (
    Band,
    CaseKind,
    ReasonCode,
    SignalGroup,
    SignalSource,
    TargetRule,
)
from satyapan.contracts.evidence import Signal
from satyapan.contracts.signal_table import SIGNAL_TABLE
from satyapan.policy.engine import decide
from satyapan.textrisk.features import N_FEATURES, hashed_tf, prepare
from satyapan.textrisk.model import TextRiskModel
from satyapan.textrisk.normalize import deobfuscate
from satyapan.textrisk.rules import text_signal


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Your Ꭺссоunt is bl0cked", "Your account is blocked"),
        ("Ve​rify yo​ur p@ssw0rd!", "Verify your password!"),
        ("send O T P now", "send OTP now"),
        ("Pay ₹500 by 9:30, invoice 2026", "Pay ₹500 by 9:30, invoice 2026"),
        ("Hello! See you 1st May", "Hello! See you 1st May"),
        ("नमस्ते, आपका खाता", "नमस्ते, आपका खाता"),
        ("Rs.500 credited to a/c XX1234", "Rs.500 credited to a/c XX1234"),
    ],
)
def test_deobfuscation_undoes_tricks_and_leaves_honest_text_alone(raw: str, clean: str) -> None:
    assert deobfuscate(raw) == clean


def test_features_are_deterministic_and_bounded() -> None:
    a = hashed_tf("Share the OTP to unblock your account")
    b = hashed_tf("Share the OTP to unblock your account")
    assert a == b and all(0 <= k < N_FEATURES for k in a)
    assert hashed_tf("Share the 0TP") == hashed_tf("Share the OTP")
    assert prepare("ＡＢＣ") == "abc"


def _toy_model(tmp_path: Path, tau_hi: float = 0.6) -> TextRiskModel:
    """A tiny model that loves the word 'otp' (one weight), saved in the shipped format."""
    idf = np.ones(N_FEATURES, np.float32)
    coef = np.zeros(N_FEATURES, np.float32)
    for k, v in hashed_tf("otp").items():
        coef[k] = 8.0 * np.sign(v)
    nz = np.flatnonzero(coef)
    np.savez(tmp_path / "m.npz", coef_idx=nz, coef_val=coef[nz], idf_idx=np.arange(N_FEATURES),
             idf_val=idf)  # fmt: skip
    meta = {"intercept": -1.0, "version": "toy", "normalise": True,
            "thresholds": {"tau_hi": tau_hi, "tau_lo": 0.4}}  # fmt: skip
    (tmp_path / "m.json").write_text(json.dumps(meta))
    return TextRiskModel.load(tmp_path / "m.npz", tmp_path / "m.json")


def test_model_scores_and_explains(tmp_path: Path) -> None:
    m = _toy_model(tmp_path)
    scam = "please share the OTP you just received to verify"
    plain = "please share the invoice you just received to verify"
    assert m.score(scam) > m.score(plain)
    assert m.score("please share the 0TP you just received") == pytest.approx(
        m.score("please share the OTP you just received")
    )
    assert "otp" in m.top_ngrams(scam)


def test_signal_is_raise_only_and_skips_short_text(tmp_path: Path) -> None:
    m = _toy_model(tmp_path)
    assert text_signal(m, "OTP", ["ev"]) is None  # too short to judge
    assert text_signal(m, "please send the invoice for last month to accounts", ["ev"]) is None
    sig = text_signal(m, "please share the OTP you just received to verify", ["ev"])
    assert sig is not None and sig.code == ReasonCode.TEXT_SCAM_LIKELY


def test_text_signal_is_capped_style_evidence(master) -> None:
    spec = SIGNAL_TABLE[ReasonCode.TEXT_SCAM_LIKELY]
    assert (spec.group, spec.target, spec.strength) == (SignalGroup.STYLE, TargetRule.VERIFY,
                                                         "weak")  # fmt: skip
    with pytest.raises(ValueError):
        Signal.make(ReasonCode.TEXT_SCAM_LIKELY, source=SignalSource.DETERMINISTIC)
    sig = Signal.make(ReasonCode.TEXT_SCAM_LIKELY, source=SignalSource.ML, evidence_ids=["e"])
    case = Case(
        id="case_t",
        title="t",
        kind=CaseKind.LIVE_CALL,
        created_at=utcnow(),
        created_by="emp_priya",
        signals=[sig, sig.model_copy(update={"id": "sig_x2"})],
    )
    assert decide(case, master).band == Band.VERIFY  # never HOLD on style alone


def test_shipped_text_model_loads_when_present() -> None:
    from satyapan.textrisk.model import META_PATH, MODEL_PATH

    if not MODEL_PATH.exists():
        pytest.skip("text model not trained yet (research/text/bench.py)")
    m = TextRiskModel.load()
    assert 0.0 < m.tau_lo <= m.tau_hi < 1.0
    meta = json.loads(META_PATH.read_text())
    import hashlib

    assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == meta["npz_sha256"]
