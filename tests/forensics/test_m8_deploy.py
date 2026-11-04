"""M8 tests: offline packaging contract (compose + Dockerfile) and the one-command demo.

Docker itself is not required: the daemon is unavailable in this environment (see BLOCKERS.md),
so these tests assert the contract the image must satisfy and that the non-Docker path works.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_is_offline_and_binds_loopback_only() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "forensic-lab" in services
    lab = services["forensic-lab"]
    # Port published to the host loopback only.
    assert lab["ports"] == ["127.0.0.1:8000:8000"]
    # No outbound dependency is declared: no extra_hosts, no network_mode host, no cloud env.
    assert "extra_hosts" not in lab
    assert lab.get("network_mode") != "host"
    joined = " ".join(f"{k}={v}" for k, v in lab.get("environment", {}).items())
    assert "SATYAPAN_AWS_MODE=off" in joined
    assert "SATYAPAN_FORENSIC_CASES_DIR=/data/cases" in joined
    # A demo profile exists for `docker compose run --rm demo`.
    assert "profiles" in services["demo"]
    assert "forensic_demo.py" in " ".join(services["demo"]["entrypoint"])


def test_dockerfile_runs_offline_and_does_not_bake_models() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12-slim" in text
    assert "ffmpeg" in text  # audio decoding
    assert "HEALTHCHECK" in text and "/health" in text
    assert "satyapan.api.app:app" in text
    # The 1.2 GB GenD / 1.3 GB voice models must not be in the image. Only real instructions
    # count (comments and the compose volume may mention models/ as optional).
    instructions = [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert not any(".onnx" in ln for ln in instructions), "Dockerfile must not bake model files"
    assert not any(re.match(r"\s*COPY\s+.*models", ln) for ln in instructions)
    # Runtime must not reach the network: no pip install at CMD, no curl-to-cloud.
    assert "SATYAPAN_FORENSIC_CASES_DIR=/data/cases" in text


def test_demo_kit_is_committed_and_matches_its_manifest() -> None:
    import hashlib
    import json

    manifest = json.loads((ROOT / "demo_kit" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["items"]) == 6
    for item in manifest["items"]:
        path = ROOT / "demo_kit" / item["filename"]
        assert path.exists(), f"missing committed exhibit {path}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == item["sha256"], f"{path.name} does not match the manifest hash"
        assert path.stat().st_size < 2_000_000, f"{path.name} is too large for the repo"


def test_make_demo_target_is_documented_in_help() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\ndemo:\n" in makefile
    assert "\ndocker-demo:\n" in makefile
    assert "make demo " in makefile
