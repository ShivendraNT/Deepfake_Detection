"""Capture the Satyapan Seal demo screenshots (PNG, 1600 px wide) into docs/pitch/round1/screens/.

Everything shown is produced live by the real code paths:
* starts the API (uvicorn) on :8000, serves console/public on :5173 and extension/ on :5174;
* seals a synthetic Kokoro voice through the API with scripts/seal_cli.py api-seal (software
  passkey standing in for Touch ID), makes a WhatsApp-style Opus 16k note of it, an unsealed
  copy, and a spliced copy; uploads each on seal-demo.html;
* intent-approve.html uses a Chrome VIRTUAL authenticator (CDP WebAuthn domain) for the passkey.

Run with a Python that has Playwright (the API and CLI are started through `uv run`):
  python3 scripts/seal_screenshots.py [--voice am_michael]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "pitch" / "round1" / "screens"
DATA = Path(os.environ.get("SATYAPAN_SEAL_DATA", str(Path.home() / ".cache/satyapan/seal")))
W = 1600


def wait_http(url: str, timeout: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)  # noqa: S310 - localhost only
            return
        except Exception:
            time.sleep(0.3)
    raise SystemExit(f"timeout waiting for {url}")


def opus_note(src: Path, dst: Path) -> None:
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
            "16k",
            str(dst),
        ],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="am_michael")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "SATYAPAN_WEBAUTHN_ORIGINS": "http://localhost:5173"}
    procs = [
        subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "satyapan.api.app:app",
                "--port",
                "8000",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
        ),
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                "5173",
                "--bind",
                "127.0.0.1",
                "-d",
                str(ROOT / "console" / "public"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                "5174",
                "--bind",
                "127.0.0.1",
                "-d",
                str(ROOT / "extension"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    ]
    shots: list[str] = []
    try:
        wait_http("http://127.0.0.1:8000/health")
        wait_http("http://127.0.0.1:5173/seal-demo.html")
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            src = DATA / "voices" / f"{a.voice}.wav"
            sealed_wav = tmp / "sealed.wav"
            r = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    str(ROOT / "scripts" / "seal_cli.py"),
                    "api-seal",
                    "--note",
                    "VN-2026-10-07-0042",
                    str(src),
                    str(sealed_wav),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=ROOT,
            )
            print(r.stdout.strip())
            notes = {
                "sealed": tmp / "rajesh_note.ogg",
                "unsealed": tmp / "forwarded_note.ogg",
                "spliced": tmp / "spliced_note.ogg",
            }
            opus_note(sealed_wav, notes["sealed"])
            opus_note(src, notes["unsealed"])
            sr, xs = wavfile.read(sealed_wav)
            _, xu = wavfile.read(src)
            spl = xs.copy()
            spl[4 * 5 * sr : 7 * 5 * sr] = xu[4 * 5 * sr : 7 * 5 * sr]  # epochs 4-6 unsealed
            wavfile.write(tmp / "spliced.wav", sr, spl.astype(np.int16))
            opus_note(tmp / "spliced.wav", notes["spliced"])
            shots += capture(notes)
    finally:
        for p in procs:
            p.terminate()
    print(json.dumps(shots, indent=1))


def capture(notes: dict[str, Path]) -> list[str]:
    from playwright.sync_api import sync_playwright

    shots = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": 980}, device_scale_factor=1)
        page = ctx.new_page()
        # 1-3. voice note seal check
        for name, role in (
            ("sealed", "emp_priya|maker"),
            ("unsealed", "emp_priya|maker"),
            ("spliced", "emp_arjun|checker"),
        ):
            page.goto("http://localhost:5173/seal-demo.html")
            page.wait_for_timeout(400)
            page.select_option("#role", role)
            page.set_input_files("#file", str(notes[name]))
            page.click("#go")
            page.wait_for_selector(".verdict", timeout=60_000)
            f = OUT / f"seal_voice_note_{name}.png"
            page.screenshot(path=str(f), full_page=True)
            shots.append(str(f.relative_to(ROOT)))
        # 4-5. Intent Seal with a virtual authenticator
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("WebAuthn.enable")
        cdp.send(
            "WebAuthn.addVirtualAuthenticator",
            {
                "options": {
                    "protocol": "ctap2",
                    "transport": "internal",
                    "hasResidentKey": True,
                    "hasUserVerification": True,
                    "isUserVerified": True,
                    "automaticPresenceSimulation": True,
                }
            },
        )
        page.goto("http://localhost:5173/intent-approve.html")
        page.click("#enrol")
        page.wait_for_selector("#pk.on", timeout=20_000)
        page.wait_for_function("document.getElementById('amount').textContent.includes('₹')")
        f = OUT / "intent_seal_request.png"
        page.screenshot(path=str(f), full_page=True)
        shots.append(str(f.relative_to(ROOT)))
        page.check("#tamper")
        page.click("#approve")
        page.wait_for_selector(".result.bad", timeout=20_000)
        f = OUT / "intent_seal_tampered_amount_rejected.png"
        page.screenshot(path=str(f), full_page=True)
        shots.append(str(f.relative_to(ROOT)))
        page.reload()
        page.wait_for_function("document.getElementById('amount').textContent.includes('₹')")
        page.click("#approve")
        page.wait_for_selector(".result.ok", timeout=20_000)
        f = OUT / "intent_seal_genuine_accepted.png"
        page.screenshot(path=str(f), full_page=True)
        shots.append(str(f.relative_to(ROOT)))
        # 6. seal chip states, 7. existing side panel in replay mode
        page = ctx.new_page()
        page.goto("http://localhost:5174/seal_chip_demo.html")
        page.wait_for_selector(".seal-chip")
        f = OUT / "seal_chip_states.png"
        page.screenshot(path=str(f), full_page=True)
        shots.append(str(f.relative_to(ROOT)))
        page = ctx.new_page()
        page.goto("http://localhost:5174/sidepanel.html?replay=1")
        page.wait_for_timeout(300 * 16 + 1500)  # replay feeds one event every 300 ms
        f = OUT / "sidepanel_replay.png"
        page.screenshot(path=str(f), full_page=True)
        shots.append(str(f.relative_to(ROOT)))
        b.close()
    return shots


if __name__ == "__main__":
    main()
