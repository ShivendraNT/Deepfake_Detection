"""Replay a real audio/video file through the real live-call path, in-process.

    uv run python scripts/replay_live_media.py audio .cache/testkit/audio/fake_cfo_clone_en.wav
    uv run python scripts/replay_live_media.py video <path_to_video.mp4>
    uv run python scripts/replay_live_media.py both  ...  # video frames + audio together

This is the same FastAPI app, live service, voice-clone model, speech engine, video endpoint
and policy engine the desktop uses. It is the closest thing to a Meet call without Meet: the
audio is cut into the product's 5 s windows and scored on this laptop; the video is sampled at
15 fps and posted to `/live/{call_id}/video`, exactly like the capture window.

No network, no real data, nothing stored: a temp file is used for the video frames and deleted.
If the video CNN is not installed, the live service reports `video_unavailable` and listening
continues (an abstention, never a fake "safe").
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WINDOW_S = 5.0  # the product's voice window
FPS = 15.0  # the capture window's video rate
MAX_SECONDS = 30.0


def _wav_bytes(samples: Any, sample_rate: int = 16_000) -> bytes:
    import io

    raw = (samples * 32767.0).clip(-32768, 32767).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(raw)
    return out.getvalue()


def _start(client: Any) -> tuple[str, str]:
    session = client.post(
        "/companion/session/start",
        json={"version": "1", "consent": True, "source": "user_selected_loopback"},
    ).json()
    call = client.post(
        "/companion/calls/start",
        json={
            "version": "1",
            "source": "loopback",
            "consent_id": session["state"]["consent_id"],
        },
    ).json()
    return call["call_id"], call["case_id"]


def _show(events: list[dict[str, Any]], label: str) -> None:
    for event in events:
        kind = event.get("type", "?")
        if kind == "transcript":
            print(f"  [{label}] transcript: {event.get('text', '')[:120]}")
        elif kind == "ask":
            print(f"  [{label}] ask {event.get('ask_type')}: {event.get('span_text', '')[:100]}")
        elif kind == "voice":
            print(
                f"  [{label}] voice window {event.get('window_index')}: "
                f"{event.get('label')} (consecutive={event.get('consecutive_over_hi')})"
            )
        elif kind == "band":
            print(
                f"  [{label}] BAND {event.get('band')} "
                f"reasons={','.join(event.get('reason_codes', []))}"
            )
        elif kind == "video":
            print(
                f"  [{label}] video window {event.get('window_index')}: "
                f"{event.get('label')} usable={event.get('usable_windows')}"
            )
        elif kind == "status":
            print(f"  [{label}] status {event.get('code')}: {event.get('message')}")


def _audio_chunks(client: Any, call_id: str, path: Path, max_s: float) -> None:
    from satyapan.voice.audio_io import decode_to_16k_mono

    samples = decode_to_16k_mono(path.read_bytes(), "audio/wav")
    step = int(WINDOW_S * 16_000)
    for index, start in enumerate(range(0, min(len(samples), int(max_s * 16_000)), step)):
        chunk = samples[start : start + step]
        if len(chunk) < 16_000:
            break
        t0, t1 = start / 16_000, (start + len(chunk)) / 16_000
        events = client.post(
            f"/live/{call_id}/chunk",
            files={"audio": (f"chunk{index}.wav", _wav_bytes(chunk), "audio/wav")},
            data={
                "chunk_index": str(index),
                "t_start_s": f"{t0:.3f}",
                "t_end_s": f"{t1:.3f}",
            },
        ).json()
        _show(events, f"audio {t0:.0f}-{t1:.0f}s")


def _video_frames(client: Any, call_id: str, path: Path, max_s: float) -> None:
    with tempfile.TemporaryDirectory(prefix="satya_replay_") as tmp:
        out = Path(tmp) / "f%05d.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-t",
                f"{max_s:.3f}",
                "-vf",
                f"fps={FPS}",
                "-q:v",
                "2",
                str(out),
            ],
            check=True,
        )
        frames = sorted(Path(tmp).glob("f*.jpg"))
        if not frames:
            print("  ! no frames decoded")
            return
        for start in range(0, len(frames), int(FPS)):
            batch = frames[start : start + int(FPS)]
            times = [round((start + i) / FPS, 3) for i in range(len(batch))]
            files = [("frames", (f.name, f.read_bytes(), "image/jpeg")) for f in batch]
            events = client.post(
                f"/live/{call_id}/video",
                files=files,
                data={"times": json.dumps(times)},
            ).json()
            _show(events, f"video {times[0]:.0f}-{times[-1]:.0f}s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["audio", "video", "both"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--max-seconds", type=float, default=MAX_SECONDS)
    parser.add_argument(
        "--audio-file",
        type=Path,
        help="for `both`: the call audio to play alongside the video (default: the video's own)",
    )
    args = parser.parse_args(argv)
    if not args.file.is_file():
        print(f"file not found: {args.file}")
        return 2

    from fastapi.testclient import TestClient

    from satyapan.api.app import create_app
    from satyapan.settings import Settings

    client = TestClient(create_app(Settings()))
    state = client.app.state.satyapan
    print(f"voice model : {'ready' if state.voice_scorer() else state.voice_status()}")
    print(f"video model : {'ready' if state.video() else state.video_status()}")
    print(f"speech      : {state.asr_status().get('engine')}")

    call_id, case_id = _start(client)
    print(f"call {call_id} / case {case_id}\n")

    if args.mode in ("video", "both"):
        _video_frames(client, call_id, args.file, args.max_seconds)
    if args.mode == "audio":
        _audio_chunks(client, call_id, args.file, args.max_seconds)
    elif args.mode == "both":
        audio = args.audio_file or args.file
        _audio_chunks(client, call_id, audio, args.max_seconds)

    case = client.get(f"/cases/{case_id}").json()
    decision = case.get("decision") or {}
    print("\nFinal policy band:", decision.get("band"))
    print("Reasons:", ", ".join(decision.get("reason_codes", [])) or "(none)")
    print("Nothing was stored; the call is stopped.")
    consent_id = getattr(state.companion().snapshot(), "consent_id", "")
    client.post(
        "/companion/session/stop",
        json={"version": "1", "consent_id": consent_id},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
