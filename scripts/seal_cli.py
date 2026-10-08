"""Voice Seal CLI. Synthetic or consented voices only.

Offline TEST mode (keys derived from a shared test seed; for the two-laptop Meet test):
  python scripts/seal_cli.py seal   --seed demo --meeting abc-defg-hij in.wav sealed.wav
  python scripts/seal_cli.py verify --seed demo --meeting abc-defg-hij rec.(webm|m4a|ogg|wav)

End-to-end against a running API (`make run`), with a SOFTWARE passkey standing in for Touch ID:
  python scripts/seal_cli.py api-seal --api http://127.0.0.1:8000 --note VN-0042 in.wav note.wav
      enrols emp_rajesh's demo passkey, starts a voice-note session through POST /seal/sessions
      (passkey-signed SEAL-START), seals the audio, and discloses the keys. t0 is set to "now
      minus the note length", i.e. it simulates a note recorded over the last N seconds.
  python scripts/seal_cli.py api-verify --api http://127.0.0.1:8000 --claimed emp_rajesh note.ogg

In the product the executive's browser does the sealing (AudioWorklet) and the verifier only
ever fetches disclosed keys from the registry; the seed never leaves the executive's device.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.seal import tesla  # noqa: E402
from satyapan.seal import voiceseal as vs  # noqa: E402
from satyapan.seal.verify_upload import decode_path  # noqa: E402

N_EPOCHS = 2000


def _write(path: str, y: np.ndarray) -> None:
    y = 0.98 * y / max(1.0, float(np.max(np.abs(y))) / 0.98)
    wavfile.write(path, vs.SR, np.round(np.clip(y, -1, 1) * 32767).astype(np.int16))


def cmd_seal(a: argparse.Namespace) -> None:
    p = vs.SealParams(amp_db=a.amp)
    x = decode_path(Path(a.inp))
    _, keys = tesla.make_chain(a.seed.encode(), N_EPOCHS)
    binding = tesla.canonical_binding(a.meeting)
    _write(a.out, vs.embed(x, keys, binding, p, start_epoch=a.first_epoch))
    print(f"sealed {len(x) / vs.SR:.1f} s -> {a.out} (amp {a.amp} dB, binding {binding})")


def cmd_verify(a: argparse.Namespace) -> None:
    from satyapan.seal.verify_upload import verify_samples

    y = decode_path(Path(a.inp))
    _, keys = tesla.make_chain(a.seed.encode(), N_EPOCHS)
    binding = tesla.canonical_binding(a.meeting)
    t = time.perf_counter()
    v = verify_samples(
        y,
        keys=dict(enumerate(keys)),
        binding=binding,
        first_epoch=a.first_epoch,
        max_offset_s=a.max_offset,
        rates=tuple(a.rates),
    )
    dt = time.perf_counter() - t
    print(f"binding {binding}; {v.audio_seconds:.1f} s audio, {v.speech_seconds:.1f} s speech")
    print(
        f"offset {v.offset_s} s; acquisition A={v.acquisition_statistic} "
        f"(threshold {v.acquisition_threshold})"
    )
    for e in v.epochs:
        print(
            f"  epoch {e.epoch:4d} @ {e.start_s:7.2f} s  z={e.z:6.2f}  cells={e.cells:5d}  "
            f"{e.status.value}"
        )
    verdict = "SEALED" if v.sealed else "NOT SEALED"
    print(
        f"{verdict} ({v.decided_by}); sealed epochs {v.n_epochs_sealed}/{v.n_epochs_speech} "
        f"with speech; gaps {[(g.first_epoch, g.last_epoch) for g in v.gaps]}; {dt:.1f} s"
    )
    if a.json:
        Path(a.json).write_text(v.model_dump_json(indent=1))


# ------------------------------------------------------------------ API mode


def _http(
    api: str,
    method: str,
    path: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    raw: bytes | None = None,
    ctype: str = "application/json",
) -> Any:
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(api.rstrip("/") + path, data=data, method=method)
    req.add_header("Content-Type", ctype)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:400]}") from e


def _demo_passkey(api: str, employee: str) -> Any:
    from satyapan.seal.softauth import SoftAuthenticator

    auth = SoftAuthenticator(
        rp_id="localhost", origin=os.environ.get("SEAL_ORIGIN", "http://localhost:5173")
    )
    hdr = {"X-Demo-User": employee, "X-Demo-Role": "requester"}
    opts = _http(api, "POST", f"/passkeys/{employee}/register/options", {}, hdr)
    _http(api, "POST", f"/passkeys/{employee}/register", {"credential": auth.create(opts)}, hdr)
    return auth, hdr


def cmd_api_seal(a: argparse.Namespace) -> None:
    from satyapan.contracts.enums import SealSessionKind
    from satyapan.seal.registry import binding_for, seal_start_challenge, seal_start_statement

    x = decode_path(Path(a.inp))
    auth, hdr = _demo_passkey(a.api, a.employee)
    p = vs.DEFAULT_PARAMS
    n_ep = int(np.ceil(len(x) / vs.SR / p.epoch_s))
    seed = os.urandom(32)  # secret, stays in this process (the exec's device in the product)
    commitment, keys = tesla.make_chain(seed, max(n_ep + 2, 10))
    t0_ms = int((time.time() - n_ep * p.epoch_s - 2) * 1000)  # simulates a note just recorded
    kind = SealSessionKind.VOICE_NOTE
    stmt = seal_start_statement(
        employee_id=a.employee,
        kind=kind,
        binding=binding_for(kind, a.note),
        commitment_hex=commitment.hex(),
        t0_ms=t0_ms,
        epoch_ms=round(p.epoch_s * 1000),
        n_epochs=len(keys),
        params_id=p.params_id,
    )
    body = {
        "meeting": a.note,
        "kind": kind.value,
        "commitment": commitment.hex(),
        "t0_ms": t0_ms,
        "epoch_ms": round(p.epoch_s * 1000),
        "n_epochs": len(keys),
        "params_id": p.params_id,
        "assertion": auth.get(seal_start_challenge(stmt)),
    }
    s = _http(a.api, "POST", "/seal/sessions", body, hdr)
    _write(a.out, vs.embed(x, keys, s["binding"], p))
    s = _http(
        a.api,
        "POST",
        f"/seal/sessions/{s['id']}/keys",
        {"epoch": n_ep - 1, "key": keys[n_ep - 1].hex()},
    )
    print(
        json.dumps(
            {
                "session_id": s["id"],
                "binding": s["binding"],
                "employee": a.employee,
                "epochs": n_ep,
                "sealed_file": a.out,
            }
        )
    )


def cmd_api_verify(a: argparse.Namespace) -> None:
    boundary = uuid.uuid4().hex
    fields = {"claimed_employee_id": a.claimed} if a.claimed else {"session_id": a.session}
    parts = b""
    for k, v in fields.items():
        parts += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
        ).encode()
    data = Path(a.inp).read_bytes()
    parts += (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{Path(a.inp).name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    hdr = {"X-Demo-User": a.user, "X-Demo-Role": a.role}
    out = _http(
        a.api,
        "POST",
        "/seal/verify-upload",
        headers=hdr,
        raw=parts,
        ctype=f"multipart/form-data; boundary={boundary}",
    )
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description="Voice Seal CLI (synthetic/consented voices only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("seal", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--seed", required=True, help="TEST seed shared by sealer and verifier")
        s.add_argument("--meeting", required=True)
        s.add_argument("--first-epoch", type=int, default=0)
        s.add_argument("inp")
        if name == "seal":
            s.add_argument("--amp", type=float, default=2.0)
            s.add_argument("out")
        else:
            s.add_argument("--max-offset", type=float, default=30.0)
            s.add_argument("--rates", type=float, nargs="+", default=[1.0])
            s.add_argument("--json", default="")
    s = sub.add_parser("api-seal")
    s.add_argument("--api", default="http://127.0.0.1:8000")
    s.add_argument("--employee", default="emp_rajesh")
    s.add_argument("--note", required=True)
    s.add_argument("inp")
    s.add_argument("out")
    s = sub.add_parser("api-verify")
    s.add_argument("--api", default="http://127.0.0.1:8000")
    s.add_argument("--claimed", default="")
    s.add_argument("--session", default="")
    s.add_argument("--user", default="emp_priya")
    s.add_argument("--role", default="maker")
    s.add_argument("inp")
    a = ap.parse_args()
    {
        "seal": cmd_seal,
        "verify": cmd_verify,
        "api-seal": cmd_api_seal,
        "api-verify": cmd_api_verify,
    }[a.cmd](a)


if __name__ == "__main__":
    main()
