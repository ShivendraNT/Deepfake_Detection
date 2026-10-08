"""Verify sealed voice notes / recordings through a real codec (ffmpeg libopus), with gaps."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from satyapan.contracts import SealEpochStatus
from satyapan.seal import tesla
from satyapan.seal import voiceseal as vs
from satyapan.seal.verify_upload import (
    NOT_SEALED_NOTE,
    decode_audio,
    strip_scores,
    verify_samples,
)
from tests.seal.seal_fixtures import speechlike

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

BINDING = "note:VN-1"


def opus_bytes(x: np.ndarray, kbps: int = 16) -> bytes:
    """WhatsApp-style voice note: Opus at 16 kbps, 16 kHz, in an Ogg container."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.wav", Path(d) / "out.ogg"
        wavfile.write(src, vs.SR, np.clip(x * 32767, -32768, 32767).astype(np.int16))
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(src),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "libopus",
                "-b:a",
                f"{kbps}k",
                "-application",
                "voip",
                str(dst),
            ],
            check=True,
        )
        return dst.read_bytes()


@pytest.fixture(scope="module")
def note() -> dict[str, object]:
    x = speechlike(36, seed=21)
    _, keys = tesla.make_chain(b"note-session", 20)
    sealed = vs.embed(x, keys, BINDING)
    return {"x": x, "keys": dict(enumerate(keys)), "sealed": sealed}


def test_sealed_voice_note_through_opus_with_unknown_offset(note: dict[str, object]) -> None:
    lead = np.zeros(int(3.37 * vs.SR))  # recorder started 3.37 s before the seal session
    data = opus_bytes(np.concatenate([lead, note["sealed"]]))  # type: ignore[list-item]
    v = verify_samples(decode_audio(data), keys=note["keys"], binding=BINDING)  # type: ignore[arg-type]
    assert v.sealed and v.gaps == []
    assert v.offset_s == pytest.approx(3.37, abs=0.03)
    assert v.n_epochs_sealed >= 5 and v.n_epochs_sealed == v.n_epochs_speech
    assert v.timing_provable is False


def test_unsealed_and_wrong_binding_are_not_sealed(note: dict[str, object]) -> None:
    for audio, binding in ((note["x"], BINDING), (note["sealed"], "note:VN-2")):
        v = verify_samples(decode_audio(opus_bytes(audio)), keys=note["keys"], binding=binding)  # type: ignore[arg-type]
        assert not v.sealed and v.decided_by == "not_sealed" and v.gaps == []
        assert NOT_SEALED_NOTE in v.notes


def test_spliced_unsealed_speech_shows_as_a_gap(note: dict[str, object]) -> None:
    spliced = np.array(note["sealed"], copy=True)
    a, b = 3 * 80_000, 5 * 80_000  # epochs 3 and 4 replaced by unsealed speech
    spliced[a:b] = speechlike(10, seed=99)
    v = verify_samples(decode_audio(opus_bytes(spliced)), keys=note["keys"], binding=BINDING)  # type: ignore[arg-type]
    assert v.sealed
    assert [(g.first_epoch, g.last_epoch) for g in v.gaps] == [(3, 4)]
    assert {e.epoch for e in v.epochs if e.status == SealEpochStatus.SEALED} >= {0, 1, 2, 5, 6}


def test_maker_view_strips_scores(note: dict[str, object]) -> None:
    v = verify_samples(note["sealed"], keys=note["keys"], binding=BINDING)  # type: ignore[arg-type]
    m = strip_scores(v)
    assert m.acquisition_statistic is None and all(e.z is None for e in m.epochs)
    assert m.sealed == v.sealed and [e.status for e in m.epochs] == [e.status for e in v.epochs]


def test_no_keys_and_bad_audio(note: dict[str, object]) -> None:
    v = verify_samples(note["sealed"], keys={}, binding=BINDING)  # type: ignore[arg-type]
    assert not v.sealed and v.decided_by == "no_keys"
    with pytest.raises(ValueError):
        decode_audio(b"this is not audio")
    with pytest.raises(ValueError):
        decode_audio(b"")
