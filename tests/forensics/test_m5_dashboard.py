"""M5 tests: Explainable forensic dashboard UI (`/forensics`) and REST API (`/api/forensics/*`)."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from satyapan.api.app import create_app


def test_forensics_dashboard_page_is_offline_and_complete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SATYAPAN_FORENSIC_CASES_DIR", str(tmp_path / "fcases"))
    client = TestClient(create_app())

    resp = client.get("/forensics")
    assert resp.status_code == 200
    html = resp.text
    assert "Multimedia Evidence Authentication, Deepfake & Provenance Lab" in html
    assert "Limits of This Analysis" in html
    assert "Signed Custody, Merkle Proof & Tamper Lab" in html
    # Zero external CDN or cloud script/font links (strictly offline)
    assert "https://cdn." not in html
    assert "https://fonts." not in html
    assert "https://unpkg." not in html


def test_forensics_demo_case_intake_artifacts_and_tamper_simulation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SATYAPAN_FORENSIC_CASES_DIR", str(tmp_path / "fcases"))
    client = TestClient(create_app())

    # 1. Seed the multi-modal demo case
    r_seed = client.post("/api/forensics/demo-case")
    assert r_seed.status_code == 200
    case_data = r_seed.json()
    assert case_data["case_id"] == "case_forensic_demo_01"
    assert case_data["integrity"]["ok"] is True
    assert len(case_data["items"]) == 4
    assert len(case_data["timeline"]) >= 6
    assert len(case_data["custody_log"]) >= 8
    assert len(case_data["limitations_of_analysis"]) >= 4

    # Check that EV0001 (tampered image) and EV0002 (C2PA authentic image) have expected findings
    ev1 = case_data["items"][0]
    ev2 = case_data["items"][1]
    assert ev1["evidence_id"] == "EV0001"
    assert ev1["overall_finding"] == "consistent_with_manipulation"
    assert ev2["evidence_id"] == "EV0002"
    assert ev2["provenance"]["c2pa"]["status"] == "valid_c2pa_manifest"

    # 2. Fetch heatmap PNG artifact for EV0001
    r_art = client.get(
        "/api/forensics/cases/case_forensic_demo_01/artifacts/EV0001/tamper_composite.png"
    )
    assert r_art.status_code == 200
    assert r_art.headers["content-type"] == "image/png"
    assert r_art.content.startswith(b"\x89PNG")

    # 3. Simulate 1-bit tamper on EV0001 -> integrity must turn FALSE
    r_tamp = client.post("/api/forensics/cases/case_forensic_demo_01/tamper-sim/EV0001")
    assert r_tamp.status_code == 200
    tamp_data = r_tamp.json()
    assert tamp_data["integrity"]["ok"] is False
    assert "EV0001" in tamp_data["integrity"]["file_mismatches"]
    assert tamp_data["merkle_proofs"]["EV0001"]["verified"] is False

    # 4. Restore sealed byte on EV0001 -> integrity must return to TRUE
    r_rest = client.post("/api/forensics/cases/case_forensic_demo_01/tamper-restore/EV0001")
    assert r_rest.status_code == 200
    rest_data = r_rest.json()
    assert rest_data["integrity"]["ok"] is True
    assert rest_data["merkle_proofs"]["EV0001"]["verified"] is True

    # 5. Create a new case and upload an image via multipart intake
    r_new = client.post(
        "/api/forensics/cases",
        json={
            "case_id": "case_custom_02",
            "title": "Lab Custom Upload Case",
            "agency": "State FSL",
            "examiner": "examiner_meera",
        },
    )
    assert r_new.status_code == 200

    rgb = np.full((128, 128, 3), 120, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=85)
    r_up = client.post(
        "/api/forensics/cases/case_custom_02/intake",
        files={"file": ("evidence_photo.jpg", buf.getvalue(), "image/jpeg")},
        data={"device": "seized-phone-9", "make": "Samsung", "model": "S24"},
    )
    assert r_up.status_code == 200
    up_data = r_up.json()
    assert len(up_data["items"]) == 1
    assert up_data["items"][0]["evidence_id"] == "EV0001"
    assert up_data["integrity"]["ok"] is True
