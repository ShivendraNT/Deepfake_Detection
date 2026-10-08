"""HTTP: passkey enrolment, seal sessions + key disclosure, upload verification, Intent Seal."""

from __future__ import annotations

import io
from datetime import timedelta
from typing import Any

import numpy as np
import pytest
from scipy.io import wavfile

from satyapan.contracts import ReasonCode, SealSessionKind
from satyapan.contracts.common import utcnow
from satyapan.seal import tesla
from satyapan.seal import voiceseal as vs
from satyapan.seal.registry import binding_for, seal_start_challenge, seal_start_statement
from satyapan.seal.softauth import SoftAuthenticator
from tests.seal.seal_fixtures import speechlike

RAJESH = {"X-Demo-User": "emp_rajesh", "X-Demo-Role": "requester"}
PRIYA = {"X-Demo-User": "emp_priya", "X-Demo-Role": "maker"}
ARJUN = {"X-Demo-User": "emp_arjun", "X-Demo-Role": "checker"}


def _enrol(client: Any) -> SoftAuthenticator:
    auth = SoftAuthenticator(rp_id="localhost", origin="http://localhost:5173")
    opts = client.post("/passkeys/emp_rajesh/register/options", headers=RAJESH).json()
    r = client.post(
        "/passkeys/emp_rajesh/register", headers=RAJESH, json={"credential": auth.create(opts)}
    )
    assert r.status_code == 200 and r.json()["enrolled"] is True
    return auth


def _start(client: Any, auth: SoftAuthenticator, kind: SealSessionKind, meeting: str, seed: bytes):  # type: ignore[no-untyped-def]
    commitment, keys = tesla.make_chain(seed, 50)
    t0 = utcnow() - timedelta(seconds=60)
    t0_ms = int(t0.timestamp() * 1000)
    stmt = seal_start_statement(
        employee_id="emp_rajesh",
        kind=kind,
        binding=binding_for(kind, meeting),
        commitment_hex=commitment.hex(),
        t0_ms=t0_ms,
        epoch_ms=5000,
        n_epochs=50,
        params_id=vs.DEFAULT_PARAMS.params_id,
    )
    body = {
        "meeting": meeting,
        "kind": kind.value,
        "commitment": commitment.hex(),
        "t0_ms": t0_ms,
        "epoch_ms": 5000,
        "n_epochs": 50,
        "params_id": vs.DEFAULT_PARAMS.params_id,
        "assertion": auth.get(seal_start_challenge(stmt)),
    }
    r = client.post("/seal/sessions", headers=RAJESH, json=body)
    assert r.status_code == 200, r.text
    return r.json(), keys


def _wav(x: np.ndarray) -> bytes:
    buf = io.BytesIO()
    wavfile.write(buf, vs.SR, np.clip(x * 32767, -32768, 32767).astype(np.int16))
    return buf.getvalue()


def test_enrol_only_yourself(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/passkeys/emp_rajesh/register/options", headers=PRIYA)
    assert r.status_code == 403


def test_meeting_session_and_key_disclosure(client) -> None:  # type: ignore[no-untyped-def]
    auth = _enrol(client)
    s, keys = _start(
        client, auth, SealSessionKind.MEETING, "https://meet.google.com/abc-defg-hij", b"m"
    )
    assert s["binding"] == "meet:abc-defg-hij"
    r = client.post(f"/seal/sessions/{s['id']}/keys", json={"epoch": 10, "key": keys[10].hex()})
    assert r.status_code == 200 and r.json()["last_disclosed_epoch"] == 10
    r = client.post(f"/seal/sessions/{s['id']}/keys", json={"epoch": 30, "key": keys[30].hex()})
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "epoch_not_ended"
    r = client.post(f"/seal/sessions/{s['id']}/keys", json={"epoch": 11, "key": "00" * 32})
    assert r.json()["detail"]["reason"] == "key_mismatch"
    views = client.get("/seal/meetings/abc-defg-hij").json()
    assert len(views) == 1 and [k["epoch"] for k in views[0]["keys"]] == list(range(11))
    bad = dict(s)  # replaying the same start fails (fresh commitment required)
    assert bad["id"].startswith("seal_")


def test_verify_upload_sealed_and_unsealed(client) -> None:  # type: ignore[no-untyped-def]
    auth = _enrol(client)
    s, keys = _start(client, auth, SealSessionKind.VOICE_NOTE, "VN-API-1", b"note")
    client.post(f"/seal/sessions/{s['id']}/keys", json={"epoch": 8, "key": keys[8].hex()})
    assert client.get("/seal/meetings/note:VN-API-1").json() == []  # note keys stay private
    x = speechlike(26, seed=7)
    sealed = vs.embed(x, keys, "note:VN-API-1")
    files = {"file": ("note.wav", _wav(sealed), "audio/wav")}
    r = client.post(
        "/seal/verify-upload",
        headers=PRIYA,
        files=files,
        data={"claimed_employee_id": "emp_rajesh"},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    v = out["verification"]
    assert v["sealed"] and v["employee_id"] == "emp_rajesh" and v["n_epochs_sealed"] >= 4
    assert v["acquisition_statistic"] is None and all(e["z"] is None for e in v["epochs"])
    assert [sg["code"] for sg in out["signals"]] == [ReasonCode.VOICE_SEALED]
    r = client.post("/seal/verify-upload", headers=ARJUN, files=files, data={"session_id": s["id"]})
    assert all(e["z"] is not None for e in r.json()["verification"]["epochs"])  # checker sees z
    unsealed = {"file": ("note.wav", _wav(speechlike(45, seed=8)), "audio/wav")}
    r = client.post(
        "/seal/verify-upload",
        headers=PRIYA,
        files=unsealed,
        data={"claimed_employee_id": "emp_rajesh"},
    )
    out = r.json()
    assert out["verification"]["sealed"] is False
    assert out["verification"]["speech_seconds"] >= 15
    assert [sg["code"] for sg in out["signals"]] == [ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC]
    r = client.post(
        "/seal/verify-upload",
        headers=PRIYA,
        files={"file": ("x.wav", b"not audio", "audio/wav")},
        data={"session_id": s["id"]},
    )
    assert r.status_code == 422


def test_intent_seal_end_to_end(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/intent/challenge", headers=PRIYA, json={"case_id": "case_s06"})
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "not_enrolled"
    auth = _enrol(client)
    issued = client.post("/intent/challenge", headers=PRIYA, json={"case_id": "case_s06"}).json()
    assert (
        issued["display_text"] == "Approve ₹48,50,000 to A/c ••••4821 (FAKM0000482) for case_s06?"
    )
    intent = issued["intent"]
    assertion = auth.get(bytes.fromhex(issued["challenge_sha256_hex"]))
    tampered = {**intent, "amount_inr": 48_500_000}
    r = client.post(
        "/intent/verify", headers=RAJESH, json={"intent": tampered, "assertion": assertion}
    )
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "signature_rejected"
    r = client.post(
        "/intent/verify", headers=RAJESH, json={"intent": intent, "assertion": assertion}
    )
    assert r.status_code == 200 and r.json()["accepted"] is True
    r = client.post(
        "/intent/verify", headers=RAJESH, json={"intent": intent, "assertion": assertion}
    )
    assert r.json()["detail"]["reason"] == "replay"
    rows = client.get("/cases/case_s06/custody", headers=ARJUN).json()["rows"]
    seals = [row["payload"].get("intent_seal") for row in rows if "intent_seal" in row["payload"]]
    assert seals == ["refused", "approved", "refused"]


@pytest.mark.parametrize("case_id", ["case_s01"])
def test_intent_needs_a_requester(client, case_id: str) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/intent/challenge", headers=PRIYA, json={"case_id": case_id})
    assert r.status_code in (409, 422)
