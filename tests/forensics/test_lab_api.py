"""The Forensic Lab API end to end with stub models: intake, integrity, analysis, custody,
links, reports, SSE, and hostile inputs."""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import create_app
from satyapan.forensics.service import LabService, set_service
from satyapan.forensics.store import LabStore
from tests.forensics.conftest import StubModels, jpeg, textured, tone_speechlike, wav


@pytest.fixture
def lab(tmp_path: Path):
    svc = LabService(store=LabStore(tmp_path / "lab"), models=StubModels(), workers=2)
    set_service(svc)
    client = TestClient(create_app())
    yield client, svc
    set_service(None)
    svc.pool.shutdown(wait=True)


def wait_done(client: TestClient, case_id: str, timeout: float = 120) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = client.get(f"/lab/api/cases/{case_id}").json()
        if v["evidence"] and all(e["status"] in ("done", "error") for e in v["evidence"]):
            return v
        time.sleep(0.2)
    raise AssertionError("analysis did not finish")


def new_case(client: TestClient, **kw) -> str:
    body = {"title": "Test case", "fir_number": "FIR 1/2026", **kw}
    r = client.post("/lab/api/cases", json=body)
    assert r.status_code == 201
    return r.json()["id"]


def upload(client: TestClient, case_id: str, name: str, data: bytes, role: str = "questioned"):
    return client.post(f"/lab/api/cases/{case_id}/evidence", files=[("files", (name, data))],
                       data={"role": role, "received_from": "test"})  # fmt: skip


def test_health_and_techniques(lab) -> None:
    client, _ = lab
    h = client.get("/lab/api/health").json()
    assert h["status"] == "ok" and h["techniques"] >= 20
    t = client.get("/lab/api/techniques").json()
    ids = {x["id"] for x in t}
    assert {"image.ela", "audio.enf", "video.deepfake", "provenance.c2pa"} <= ids
    assert all(x["method"] for x in t)


def test_intake_hashes_first_and_stores_read_only(lab) -> None:
    client, svc = lab
    cid = new_case(client)
    data = jpeg(textured(320, 240))
    r = upload(client, cid, "photo.jpg", data)
    assert r.status_code == 201
    ev = r.json()[0]
    import hashlib

    assert ev["sha256"] == hashlib.sha256(data).hexdigest()
    assert ev["md5"] == hashlib.md5(data).hexdigest()  # noqa: S324 - recorded, not trusted
    assert ev["exhibit"] == "Q1" and ev["kind"] == "image"
    p = svc.store.evidence_path(cid, ev["sha256"])
    assert p.read_bytes() == data
    assert not (os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    v = wait_done(client, cid)
    assert v["evidence"][0]["verdict"] in ("NO_INDICATORS", "INCONCLUSIVE", "SUSPICIOUS")
    a = client.get(f"/lab/api/evidence/{ev['id']}").json()
    assert a["analysis"]["integrity_verified"] is True
    assert a["analysis"]["hashes"]["sha256"] == ev["sha256"]
    stages = [e["stage"] for e in a["events"]]
    assert stages[0] == "intake" and "integrity" in stages and stages[-1] == "done"


def test_duplicate_upload_is_detected(lab) -> None:
    client, _ = lab
    cid = new_case(client)
    data = jpeg(textured(200, 150))
    first = upload(client, cid, "a.jpg", data).json()[0]
    again = upload(client, cid, "renamed.jpg", data).json()[0]
    assert again["duplicate"] is True and again["id"] == first["id"]
    wait_done(client, cid)


def test_exhibit_numbering_by_role(lab) -> None:
    client, _ = lab
    cid = new_case(client)
    q = upload(client, cid, "q.jpg", jpeg(textured(100, 100, 1))).json()[0]
    r = upload(client, cid, "r.jpg", jpeg(textured(100, 100, 2)), role="reference").json()[0]
    q2 = upload(client, cid, "q2.wav", wav(tone_speechlike(4.0))).json()[0]
    assert (q["exhibit"], r["exhibit"], q2["exhibit"]) == ("Q1", "R1", "Q2")
    bad = upload(client, cid, "x.jpg", jpeg(textured(100, 100, 3)), role="suspect")
    assert bad.status_code == 422
    wait_done(client, cid)


def test_custody_chain_records_everything_and_detects_tampering(lab) -> None:
    client, svc = lab
    cid = new_case(client)
    upload(client, cid, "a.jpg", jpeg(textured(200, 150)))
    wait_done(client, cid)
    cu = client.get(f"/lab/api/cases/{cid}/custody").json()
    events = [r["event"] for r in cu["rows"]]
    assert events[:3] == ["STATUS_CHANGE", "INTAKE", "ANALYSIS"]
    assert cu["chain"]["ok"] is True
    svc.store.custody._tamper_for_tests(2, "someone-else")
    assert client.get(f"/lab/api/cases/{cid}/custody").json()["chain"]["ok"] is False


def test_integrity_failure_stops_analysis(lab) -> None:
    client, svc = lab
    cid = new_case(client)
    ev = upload(client, cid, "a.jpg", jpeg(textured(200, 150))).json()[0]
    wait_done(client, cid)
    p = svc.store.evidence_path(cid, ev["sha256"])
    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR)
    p.write_bytes(b"tampered")
    assert client.post(f"/lab/api/evidence/{ev['id']}/reanalyze").status_code == 202
    v = wait_done(client, cid)
    assert v["evidence"][0]["status"] == "error"
    assert "INTEGRITY" in v["evidence"][0]["headline"]
    rows = client.get(f"/lab/api/cases/{cid}/custody").json()["rows"]
    assert any(r["payload"].get("action") == "INTEGRITY_FAILURE" for r in rows)


def test_hostile_inputs_never_crash(lab) -> None:
    client, _ = lab
    cid = new_case(client)
    cases = {
        "../../etc/passwd": b"root:x:0:0", "empty.jpg": b"",
        "truncated.jpg": jpeg(textured(300, 200))[:900], "random.mp4": os.urandom(4096),
        "text_as_video.mp4": b"just text " * 100, "evil.exe.jpg": b"MZ" + os.urandom(2000),
        "ünïcødé फ़ाइल.wav": wav(tone_speechlike(3.0)), "tiny.png": jpeg(textured(8, 8)),
        "silence.wav": wav(tone_speechlike(0.2) * 0),
    }  # fmt: skip
    for name, data in cases.items():
        r = upload(client, cid, name, data)
        if not data:
            assert r.status_code == 422
            continue
        assert r.status_code == 201, (name, r.text)
        assert "/" not in r.json()[0]["filename"]
    v = wait_done(client, cid)
    for e in v["evidence"]:
        assert e["status"] == "done", (e["filename"], e["headline"])
        assert e["verdict"] in ("NO_INDICATORS", "INCONCLUSIVE", "SUSPICIOUS", "MANIPULATED")


def test_artifact_path_traversal_is_refused(lab) -> None:
    client, _ = lab
    cid = new_case(client)
    ev = upload(client, cid, "a.jpg", jpeg(textured(320, 240))).json()[0]
    wait_done(client, cid)
    for name in ("../../lab.db", "..%2F..%2Flab.db", ".hidden", "nonexistent.png"):
        assert client.get(f"/lab/api/evidence/{ev['id']}/artifacts/{name}").status_code == 404
    ok = client.get(f"/lab/api/evidence/{ev['id']}").json()["analysis"]["techniques"]
    names = [a["name"] for t in ok for a in t["artifacts"]]
    assert (
        names
        and client.get(f"/lab/api/evidence/{ev['id']}/artifacts/{names[0]}").status_code == 200
    )


def test_links_between_related_exhibits(lab) -> None:
    client, _ = lab
    cid = new_case(client)
    base = textured(640, 480, seed=11)
    edited = base.copy()
    edited[200:300, 300:420] = 30
    upload(client, cid, "original.jpg", jpeg(base, 95), role="reference")
    wait_done(client, cid)
    upload(client, cid, "edited.jpg", jpeg(edited, 80))
    v = wait_done(client, cid)
    kinds = {ln["kind"] for ln in v["links"]}
    assert "shares_content" in kinds or "near_duplicate" in kinds
    sc = [ln for ln in v["links"] if ln["kind"] == "shares_content"]
    if sc:
        assert "differ" in sc[0]["detail"]
        name = sc[0]["artifacts"][0]
        assert (
            client.get(f"/lab/api/evidence/{sc[0]['source']}/artifacts/{name}").status_code == 200
        )


def test_report_pdf_and_custody_export(lab) -> None:
    client, _ = lab
    cid = new_case(client, police_station="Cyber PS", offence_sections="IT Act 66D")
    upload(client, cid, "a.jpg", jpeg(textured(320, 240)))
    upload(client, cid, "b.wav", wav(tone_speechlike(6.0)))
    wait_done(client, cid)
    r = client.post(
        f"/lab/api/cases/{cid}/reports", json={"examiner": "Dr. Test", "designation": "SO"}
    )
    assert r.status_code == 201
    rec = r.json()
    pdf = client.get(rec["url"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    import hashlib

    assert hashlib.sha256(pdf.content).hexdigest() == rec["sha256"]
    rows = client.get(f"/lab/api/cases/{cid}/custody").json()["rows"]
    assert rows[-1]["event"] == "EXPORT" and rows[-1]["payload"]["pdf_sha256"] == rec["sha256"]
    exp = client.get(f"/lab/api/cases/{cid}/export.json").json()
    assert exp["custody"]["chain"]["ok"] and len(exp["analyses"]) == 2
    assert client.post("/lab/api/cases/case_nope/reports", json={}).status_code == 404


def test_sse_stream_ends_with_done(lab) -> None:
    client, _ = lab
    cid = new_case(client)
    ev = upload(client, cid, "a.jpg", jpeg(textured(160, 120))).json()[0]
    with client.stream("GET", f"/lab/api/evidence/{ev['id']}/events") as s:
        lines = [ln for ln in s.iter_lines() if ln.startswith("data:")]
    assert lines and '"stage":"done"' in lines[-1].replace(" ", "")


def test_unknown_ids_are_404(lab) -> None:
    client, _ = lab
    assert client.get("/lab/api/cases/case_missing").status_code == 404
    assert client.get("/lab/api/evidence/ev_missing").status_code == 404
    assert client.get("/lab/api/evidence/ev_missing/file").status_code == 404
    assert client.get("/lab/api/reports/SFL-x.pdf").status_code == 404
    assert client.post("/lab/api/evidence/ev_missing/reanalyze").status_code == 404


def test_root_redirects_to_lab(lab) -> None:
    client, _ = lab
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/lab"


def test_lab_api_refuses_foreign_origins(lab) -> None:
    client, _ = lab
    evil = client.get("/lab/api/cases", headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    pre = client.options("/lab/api/cases", headers={"Origin": "https://evil.example",
                                                    "Access-Control-Request-Method": "GET"})  # fmt: skip
    assert pre.status_code == 403
    own = client.get("/lab/api/cases", headers={"Origin": "http://testserver"})
    assert own.status_code == 200
    assert client.get("/lab/api/cases").status_code == 200  # same-origin fetches send no Origin
    dev = client.get("/lab/api/cases", headers={"Origin": "http://127.0.0.1:5175"})
    assert dev.status_code == 200


def test_artifact_route_cannot_escape_the_exhibit_folder(lab) -> None:
    client, svc = lab
    cid = new_case(client)
    ev = upload(client, cid, "a.jpg", jpeg(textured(160, 120))).json()[0]
    wait_done(client, cid)
    for url in ("/lab/api/evidence/../artifacts/lab.db", "/lab/api/evidence/%2E%2E/artifacts/lab.db",
                "/lab/api/evidence/%2E%2E/artifacts/custody.db", f"/lab/api/evidence/{ev['id']}/artifacts/..%2Flab.db",
                "/lab/api/evidence/ev_unknown/artifacts/ela.jpg"):  # fmt: skip
        r = client.get(url)
        assert r.status_code == 404 and not r.content.startswith(b"SQLite"), url


def test_lab_api_refuses_unknown_hosts(lab) -> None:
    client, _ = lab
    assert client.get("/lab/api/cases", headers={"Host": "attacker.example"}).status_code == 403
    assert client.get("/lab/api/cases", headers={"Host": "127.0.0.1:8000"}).status_code == 200


def test_parallel_analyses_keep_the_custody_chain_consistent(lab) -> None:
    client, svc = lab
    cid = new_case(client)
    for i in range(6):
        upload(client, cid, f"img{i}.jpg", jpeg(textured(200, 150, seed=30 + i)))
    v = wait_done(client, cid)
    assert all(e["status"] == "done" for e in v["evidence"])
    rows = client.get(f"/lab/api/cases/{cid}/custody").json()
    assert rows["chain"]["ok"] and len([r for r in rows["rows"] if r["event"] == "ANALYSIS"]) == 6
