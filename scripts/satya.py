"""Cross-platform task runner: the Makefile's targets for Windows (no `make`), macOS and Linux.

    uv run python scripts/satya.py <task>        # e.g. sync, asr, video, check, run, live

Every task is a list of plain commands (no shell syntax), so it behaves the same in PowerShell,
cmd, bash and zsh, on x64 and arm64. `make <task>` keeps working where make exists.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UV = shutil.which("uv")


def run(*cmd: str, env: dict[str, str] | None = None, cwd: Path = ROOT) -> None:
    print("$", " ".join(cmd), flush=True)
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.run(list(cmd), cwd=cwd, env=full_env, check=False)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def py(*args: str, env: dict[str, str] | None = None) -> None:
    """Run inside the project environment (uv if present, else the current interpreter)."""
    if UV:
        run(UV, "run", *args, env=env)
    elif args[0] == "python":
        run(sys.executable, *args[1:], env=env)
    else:
        run(sys.executable, "-m", *args, env=env)


def machine() -> str:
    return platform.machine().lower()


def asr_extras() -> list[str]:
    extras = ["--extra", "asr"]
    if sys.platform == "darwin" and machine() in ("arm64", "aarch64"):
        extras += ["--extra", "asr-mac"]
    return extras


def windows_on_arm_python() -> bool:
    return sys.platform == "win32" and machine() == "arm64"


def warn_platform() -> None:
    if windows_on_arm_python():
        print(
            "note: native ARM64 Python on Windows: Whisper and the face check have no ARM64\n"
            "      wheels.\n"
            "      Use x64 Python (runs under Windows' emulation):\n"
            "      uv python install cpython-3.12-windows-x86_64 && "
            "uv venv --python cpython-3.12-windows-x86_64"
        )
    if sys.platform == "darwin" and machine() == "x86_64" and sys.version_info >= (3, 13):
        print(
            "note: Intel Mac: the face check needs Python 3.11 or 3.12 (last mediapipe build "
            "for Intel Macs). uv venv --python 3.12"
        )


def need_uv() -> None:
    if not UV:
        sys.exit("uv is not installed: https://docs.astral.sh/uv/getting-started/installation/")


def sync() -> None:
    need_uv()
    run(UV, "sync", "--inexact")  # type: ignore[arg-type]


def asr() -> None:
    need_uv()
    warn_platform()
    run(UV, "sync", "--inexact", *asr_extras())  # type: ignore[arg-type]
    py("python", "scripts/asr_check.py")


def video() -> None:
    need_uv()
    warn_platform()
    run(UV, "sync", "--inexact", "--extra", "video")  # type: ignore[arg-type]
    py("python", "scripts/video_models.py")


def voice() -> None:
    need_uv()
    run(UV, "sync", "--inexact", "--extra", "audio", "--extra", "voice-build")  # type: ignore[arg-type]
    py("python", "-m", "research.voice.export", "--install")


def check() -> None:
    py("ruff", "check", ".")
    py("ruff", "format", "--check", ".")
    py("mypy")
    py("pytest")
    print("satya check: ALL GREEN")


def serve(live: bool, profile: str | None = None) -> None:
    args = [
        "uvicorn",
        "--app-dir",
        "src",
        "satyapan.api.app:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    if not live:
        args.append("--reload")
    env = {"SATYAPAN_ASR_WARMUP": "1"} if live else {}
    if profile:
        env["SATYAPAN_PROFILE"] = profile
    py(*args, env=env or None)


def desktop() -> None:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        sys.exit("Node.js (npm) is not installed: https://nodejs.org")
    cwd = ROOT / "desktop"
    if not (cwd / "node_modules").exists():
        run(npm, "ci", cwd=cwd)
    run(npm, "run", "dev", cwd=cwd)


TASKS: dict[str, tuple[str, Callable[[], None]]] = {
    "sync": ("install core + dev dependencies", sync),
    "asr": ("install the local speech engine for this OS/CPU and check it", asr),
    "video": ("install the face check (video deepfakes) and verify its models", video),
    "voice": ("build + install the voice-clone model (needs torch once)", voice),
    "doctor": (
        "check the speech engine on this laptop",
        lambda: py("python", "scripts/asr_check.py"),
    ),
    "check": ("lint + format check + typecheck + tests", check),
    "test": ("all tests", lambda: py("pytest")),
    "judge": (
        "score the detector stack and check a judge's own input",
        lambda: py("python", "scripts/judge_kit.py"),
    ),
    "dry-run": (
        "automated end-to-end rehearsal (real app, fake speech)",
        lambda: py("python", "scripts/dry_run.py"),
    ),
    "fmt": ("auto-format", lambda: (py("ruff", "format", "."), py("ruff", "check", "--fix", "."))),
    "schemas": ("regenerate JSON schemas", lambda: py("python", "scripts/export_schemas.py")),
    "run": ("API with auto-reload on http://127.0.0.1:8000", lambda: serve(False)),
    "live": ("API for a live demo (no reload, speech engine warmed up)", lambda: serve(True)),
    "live-personal": (
        "the same, alerts for a person on their own call (1930, call back, no approver)",
        lambda: serve(True, "personal"),
    ),
    "desktop": ("the Electron app (installs node modules on first run)", desktop),
    "scan": ("scan FILES/FOLDERS: verdict for each file, offline, nothing kept", lambda: None),
}


def scan() -> None:
    """`satya.py scan FILES_OR_FOLDERS...`: check any files offline (the judges' kit)."""
    run("uv", "run", "python", "-m", "satyapan.check_cli", *sys.argv[2:])


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "scan":
        scan()
        return
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        print(__doc__)
        for name, (doc, _) in TASKS.items():
            print(f"  {name:<8} {doc}")
        sys.exit(2)
    TASKS[sys.argv[1]][1]()


if __name__ == "__main__":
    main()
