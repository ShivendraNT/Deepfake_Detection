"""Verify an uploaded voice note or call recording against one seal session.

Input: any ffmpeg-decodable audio (WhatsApp .opus/.ogg, .m4a, .webm, .wav, .mp3 ...). Output: a
`SealVerification`: sealed / not sealed, the per-epoch status strip, and "gaps" (runs of epochs
that contain speech but no seal inside an otherwise sealed recording, e.g. a spliced-in fake
sentence).

The file's start time relative to the session is unknown, so the verifier searches the offset of
epoch `first_epoch` over [0, max_offset_s] once, with a Bonferroni threshold for the number of
offsets tried (voiceseal.detect, FILE_LOOKS), then scores every epoch at that fixed offset.

What an upload can and cannot prove: it can show the speech carries the seal of the enrolled
executive's device for this session (binding + epochs). It cannot prove WHEN it was produced:
the TESLA timing guarantee (key still secret while the epoch is spoken) only holds for live
calls. That is why voice-note keys never leave the server (registry.py) and why the result says
`timing_provable = False`.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.contracts.enums import SealEpochStatus
from satyapan.contracts.seal import SealEpoch, SealGap, SealSession, SealVerification
from satyapan.seal import voiceseal as vs

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_OFFSET_S = 30.0
NOT_SEALED_NOTE = (
    "Not sealed does not mean fake: the speaker may be on a phone or a guest device. "
    "Confirm through OOB-Confirm or a callback on the number on file."
)
UPLOAD_TIMING_NOTE = (
    "Offline check: shows whose enrolled device sealed this audio for this session, "
    "not when it was recorded."
)


def decode_audio(data: bytes, timeout_s: float = 120.0) -> vs.FloatArray:
    """Decode any ffmpeg-readable audio to 16 kHz mono float64. Raises ValueError on failure.

    Written to a temp file first (MP4/M4A need seeking, which a pipe cannot do).
    """
    if not data:
        raise ValueError("empty audio")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("audio file too large")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "upload.bin"
        src.write_bytes(data)
        return decode_path(src, timeout_s)


def decode_path(path: Path, timeout_s: float = 120.0) -> vs.FloatArray:
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-vn"]
    cmd += ["-ac", "1", "-ar", str(vs.SR), "-f", "f32le", "pipe:1"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout_s, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValueError(f"ffmpeg failed: {type(e).__name__}") from e
    if r.returncode != 0 or not r.stdout:
        raise ValueError("could not decode audio: " + r.stderr.decode(errors="replace")[-200:])
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float64)


def epoch_status(er: vs.EpochResult, p: vs.SealParams) -> SealEpochStatus:
    if er.cells < vs.MIN_CELLS_FRACTION * p.n_bands * p.chips_per_epoch:
        return SealEpochStatus.NO_SPEECH
    if er.z >= vs.TAU_EPOCH:
        return SealEpochStatus.SEALED
    if er.z < vs.TAU_GAP:
        return SealEpochStatus.UNSEALED
    return SealEpochStatus.WEAK


def find_gaps(epochs: list[SealEpoch], epoch_s: float) -> list[SealGap]:
    """Maximal runs of UNSEALED epochs (speech without seal)."""
    gaps: list[SealGap] = []
    run: list[SealEpoch] = []
    for ep in [*epochs, None]:
        if ep is not None and ep.status == SealEpochStatus.UNSEALED:
            run.append(ep)
            continue
        if run:
            gaps.append(
                SealGap(
                    first_epoch=run[0].epoch,
                    last_epoch=run[-1].epoch,
                    start_s=round(run[0].start_s, 3),
                    end_s=round(run[-1].start_s + epoch_s, 3),
                )
            )
            run = []
    return gaps


def verify_samples(
    samples: vs.FloatArray,
    *,
    keys: Mapping[int, bytes],
    binding: str,
    params: vs.SealParams = vs.DEFAULT_PARAMS,
    first_epoch: int = 0,
    max_offset_s: float = DEFAULT_MAX_OFFSET_S,
    rates: tuple[float, ...] = (1.0,),
    session: SealSession | None = None,
    alpha_scale: float = 1.0,
) -> SealVerification:
    """Verify 16 kHz mono samples. `keys` are the disclosed keys K_e of the session.

    `alpha_scale` = 1/S when the same file is checked against S candidate sessions.
    """
    p = params
    feat = vs.features(samples, p)
    n_frames = feat.n_frames
    max_off = max(0, min(int(max_offset_s * vs.SR / vs.HOP), n_frames - p.epoch_frames))
    n_avail = max(1, math.ceil(n_frames / p.epoch_frames))
    patterns = []
    for i in range(n_avail):
        e = first_epoch + i
        if e not in keys:
            break
        patterns.append(vs.epoch_pattern(keys[e], binding, e, p))

    def result(**kw: Any) -> SealVerification:
        return SealVerification(
            session_id=session.id if session else None,
            employee_id=session.employee_id if session else None,
            binding=binding,
            first_epoch=first_epoch,
            speech_seconds=round(feat.speech_seconds, 2),
            audio_seconds=round(len(samples) / vs.SR, 2),
            params_id=p.params_id,
            verifier_version=vs.VERSION,
            **kw,
        )

    if not patterns:
        return result(
            sealed=False,
            decided_by="no_keys",
            acquisition_threshold=vs.tau_acquisition(max_off + 1, vs.ALPHA_ACQ * alpha_scale),
            notes=["No disclosed keys for these epochs yet.", NOT_SEALED_NOTE],
        )
    det = vs.detect(
        feat,
        patterns,
        range(0, max_off + 1),
        p,
        vs.FILE_LOOKS,
        rates,
        first_epoch=first_epoch,
        alpha_scale=alpha_scale,
    )
    epochs = [
        SealEpoch(
            epoch=er.epoch,
            start_s=round(er.start_frame * vs.HOP / vs.SR, 3),
            cells=er.cells,
            status=epoch_status(er, p),
            z=round(er.z, 3),
        )
        for er in det.epochs
    ]
    gaps = find_gaps(epochs, p.epoch_s) if det.sealed else []
    notes = [UPLOAD_TIMING_NOTE] if det.sealed else [NOT_SEALED_NOTE]
    if gaps:
        notes.append("Some speech in this recording carries no seal (see gaps).")
    if det.rate != 1.0:
        notes.append(f"Playback-rate search used: best rate {det.rate:.3f}.")
    return result(
        sealed=det.sealed,
        decided_by=det.decided_by,
        decided_at_epoch=det.decided_at_epoch,
        offset_s=round(det.offset_frames * vs.HOP / vs.SR, 3),
        acquisition_threshold=round(det.acquisition_threshold, 3),
        acquisition_statistic=round(det.acquisition_statistic, 3),
        stouffer_z=None if det.stouffer_z is None else round(det.stouffer_z, 3),
        epochs=epochs,
        n_epochs_speech=sum(e.status != SealEpochStatus.NO_SPEECH for e in epochs),
        n_epochs_sealed=sum(e.status == SealEpochStatus.SEALED for e in epochs),
        gaps=gaps,
        notes=notes,
    )


def strip_scores(v: SealVerification) -> SealVerification:
    """Maker view: statuses only, no raw z (oracle-abuse mitigation, AGENTS.md rule 9)."""
    return v.model_copy(
        update={
            "acquisition_statistic": None,
            "stouffer_z": None,
            "epochs": [e.model_copy(update={"z": None}) for e in v.epochs],
        }
    )
