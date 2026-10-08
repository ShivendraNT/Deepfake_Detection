"""Chrome WebRTC realism probe for the Voice Seal (approximates Google Meet's client pipeline).

What it does, for each synthetic voice:
1. Seal the voice (test chain, meeting "meet:abc-defg-hij"), prefix 3 s of silence, write a
   48 kHz WAV, and start headless Chromium with
   --use-fake-device-for-media-stream --use-file-for-fake-audio-capture=<wav>%noloop
   so getUserMedia() returns that file as the "microphone".
2. In the page: getUserMedia with echoCancellation / noiseSuppression / autoGainControl all
   TRUE (Chrome's WebRTC audio processing module, APM) or all FALSE; send the track through a
   real loopback RTCPeerConnection pair (Opus, Chrome defaults; NetEQ jitter buffer on the
   receive side); record the REMOTE track with MediaRecorder (Opus/WebM, 128 kbps).
3. Verify the seal on the recording with the in-repo verifier (unknown start offset, file mode).
   Controls: the same recording checked for another meeting (relay) and for epoch+3 (replay),
   and the UNSEALED voice through the same path.
4. Offline stress on the APM-on recording: sox `tempo` 0.97 / 1.03 (a constant 3 % time-scale,
   far harsher than NetEQ's short accelerate/expand bursts), verified with and without the
   playback-rate search; and an RNNoise ML denoiser (ffmpeg arnndn) if a model file is given.

NOT covered (must be tested on two laptops, see research/seal/README.md): Google Meet's own
server-side processing and its ML noise cancellation, real network jitter/loss, Bluetooth
headsets, the speaker->mic acoustic path, and mixing with other participants.

Run: python research/seal/webrtc_probe.py [--voices am_michael,hf_alpha] [--rnnoise model.rnnn]
Output: results/seal_webrtc_probe.json
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

try:
    from research.seal.common import RESULTS, VOICES_DIR, git_commit, sha256_file, tool_versions
except ImportError:  # run as a plain script
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.seal.common import RESULTS, VOICES_DIR, git_commit, sha256_file, tool_versions

from satyapan.seal import tesla  # noqa: E402
from satyapan.seal import voiceseal as vs  # noqa: E402
from satyapan.seal.verify_upload import decode_path, verify_samples  # noqa: E402

MEET, OTHER = "meet:abc-defg-hij", "meet:xyz-uvwq-rst"
CHAIN_SEED = b"webrtc-probe-session"
LEAD_S = 3.0
RATES = tuple(round(0.96 + 0.005 * i, 3) for i in range(17))  # 0.960 .. 1.040

PAGE = """<!doctype html><html><body><audio id=a autoplay muted></audio><script>
async function run(apm, seconds) {
  const log = {};
  const stream = await navigator.mediaDevices.getUserMedia({audio: {
    echoCancellation: apm, noiseSuppression: apm, autoGainControl: apm, channelCount: 1}});
  const track = stream.getAudioTracks()[0];
  log.local_settings = track.getSettings();
  const pc1 = new RTCPeerConnection(), pc2 = new RTCPeerConnection();
  pc1.onicecandidate = e => e.candidate && pc2.addIceCandidate(e.candidate);
  pc2.onicecandidate = e => e.candidate && pc1.addIceCandidate(e.candidate);
  const remote = new Promise(
    r => pc2.ontrack = e => r(e.streams[0] || new MediaStream([e.track])));
  pc1.addTrack(track, stream);
  const offer = await pc1.createOffer(); await pc1.setLocalDescription(offer);
  await pc2.setRemoteDescription(offer);
  const answer = await pc2.createAnswer(); await pc2.setLocalDescription(answer);
  await pc1.setRemoteDescription(answer);
  const rs = await remote;
  document.getElementById('a').srcObject = rs;  // Chrome needs a sink to pull remote audio
  const rec = new MediaRecorder(rs,
    {mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000});
  const chunks = [];
  rec.ondataavailable = e => e.data.size && chunks.push(e.data);
  rec.start(1000);
  await new Promise(r => setTimeout(r, seconds * 1000));
  rec.stop(); await new Promise(r => rec.onstop = r);
  const stats = await pc1.getStats(); const rstats = await pc2.getStats();
  stats.forEach(s => { if (s.type === 'codec') log.codec = {mimeType: s.mimeType,
    clockRate: s.clockRate, channels: s.channels, sdpFmtpLine: s.sdpFmtpLine};
    if (s.type === 'outbound-rtp') log.outbound = {bytesSent: s.bytesSent,
    packetsSent: s.packetsSent, targetBitrate: s.targetBitrate}; });
  rstats.forEach(s => { if (s.type === 'inbound-rtp') log.inbound = {
    packetsLost: s.packetsLost, jitter: s.jitter, concealedSamples: s.concealedSamples,
    insertedSamplesForDeceleration: s.insertedSamplesForDeceleration,
    removedSamplesForAcceleration: s.removedSamplesForAcceleration,
    totalSamplesReceived: s.totalSamplesReceived,
    jitterBufferDelay: s.jitterBufferDelay,
    jitterBufferEmittedCount: s.jitterBufferEmittedCount}; });
  const blob = new Blob(chunks, {type: 'audio/webm'});
  const buf = new Uint8Array(await blob.arrayBuffer());
  let bin = ''; for (let i = 0; i < buf.length; i += 0x8000)
    bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  log.webm_b64 = btoa(bin);
  pc1.close(); pc2.close(); track.stop();
  return log;
}
</script></body></html>"""


def load16(path: Path) -> np.ndarray:
    sr, x = wavfile.read(path)
    assert sr == vs.SR
    return x.astype(np.float64) / 32768.0


def write48k(path: Path, x16: np.ndarray) -> None:
    y = resample_poly(x16, 3, 1)
    wavfile.write(path, 48_000, np.round(np.clip(y, -1, 1) * 32767).astype(np.int16))


def chrome_loopback(wav48: Path, apm: bool, seconds: float, out_webm: Path) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    args = [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-audio-capture={wav48}%noloop",
        "--autoplay-policy=no-user-gesture-required",
    ]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=args)
        page = browser.new_page()
        page.route(
            "http://localhost/probe", lambda r: r.fulfill(body=PAGE, content_type="text/html")
        )
        page.goto("http://localhost/probe")  # secure context without a server
        log: dict[str, Any] = page.evaluate(f"run({str(apm).lower()}, {seconds})")
        log["browser_version"] = browser.version
        browser.close()
    out_webm.write_bytes(base64.b64decode(log.pop("webm_b64")))
    return log


def verify(
    y: np.ndarray,
    keys: list[bytes],
    binding: str,
    first_epoch: int = 0,
    rates: tuple[float, ...] = (1.0,),
) -> dict[str, Any]:
    v = verify_samples(
        y,
        keys=dict(enumerate(keys)),
        binding=binding,
        first_epoch=first_epoch,
        max_offset_s=LEAD_S + 4,
        rates=rates,
    )
    speech = [e for e in v.epochs if e.status.value != "no_speech"]
    return {
        "sealed": v.sealed,
        "decided_by": v.decided_by,
        "time_to_verdict_s": None
        if v.decided_at_epoch is None
        else (v.decided_at_epoch + 1) * vs.DEFAULT_PARAMS.epoch_s,
        "offset_s": v.offset_s,
        "acquisition_statistic": v.acquisition_statistic,
        "acquisition_threshold": v.acquisition_threshold,
        "epochs_sealed": v.n_epochs_sealed,
        "epochs_with_speech": v.n_epochs_speech,
        "z_mean_speech_epochs": round(float(np.mean([e.z for e in speech])), 3) if speech else None,
        "z_per_epoch": [e.z for e in v.epochs],
        "best_rate": None
        if len(rates) == 1
        else next((n.split()[-1].rstrip(".") for n in v.notes if "rate" in n), "1.000"),
    }


def sox_tempo(src: Path, dst: Path, factor: float) -> None:
    subprocess.run(["sox", str(src), str(dst), "tempo", "-s", str(factor)], check=True)


def ffmpeg_filter(src: Path, dst: Path, filt: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src),
            "-af",
            filt,
            "-ar",
            "48000",
            str(dst),
        ],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voices", default="am_michael,hf_alpha")
    ap.add_argument("--rnnoise", default="", help="ffmpeg arnndn model file (.rnnn)")
    a = ap.parse_args()
    _, keys = tesla.make_chain(CHAIN_SEED, 200)
    out: dict[str, Any] = {
        "what": "Sealed synthetic speech through Chrome getUserMedia (+/- WebRTC APM) -> loopback "
        "RTCPeerConnection (Opus, NetEQ) -> MediaRecorder; seal verified on the recording",
        "approximates": "Google Meet's CLIENT pipeline (Chrome WebRTC APM + Opus + NetEQ)",
        "not_covered": [
            "Google Meet server-side processing and Meet's ML noise cancellation",
            "real network jitter / packet loss (loopback has none)",
            "speaker -> microphone acoustic path, headsets, room noise",
            "mixing with other participants' audio",
        ],
        "recorder": "MediaRecorder audio/webm;codecs=opus 128 kbps (one extra near-transparent "
        "encode after the WebRTC Opus leg)",
        "script": "research/seal/webrtc_probe.py",
        "git_commit": git_commit(),
        "tools": tool_versions(),
        "runs": [],
        "notes": [],
    }
    rn_model = Path(a.rnnoise) if a.rnnoise else None
    if rn_model and rn_model.exists():
        out["rnnoise_model"] = {
            "file": rn_model.name,
            "sha256": sha256_file(rn_model),
            "source": "github.com/GregorR/rnnoise-models",
        }
    else:
        out["notes"].append("RNNoise (ffmpeg arnndn) skipped: no model file given")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for voice in [v for v in a.voices.split(",") if v]:
            x = load16(VOICES_DIR / f"{voice}.wav")
            sealed = vs.embed(x, keys, MEET)
            lead = np.zeros(int(LEAD_S * vs.SR))
            files = {
                "sealed": np.concatenate([lead, sealed]),
                "unsealed": np.concatenate([lead, x]),
            }
            dur = len(files["sealed"]) / vs.SR + 1.5
            for kind, apm in (("sealed", True), ("sealed", False), ("unsealed", True)):
                wav = tmp / f"{voice}_{kind}.wav"
                write48k(wav, files[kind])
                webm = tmp / f"{voice}_{kind}_apm{int(apm)}.webm"
                t0 = time.time()
                log = chrome_loopback(wav, apm, dur, webm)
                y = decode_path(webm)
                run: dict[str, Any] = {
                    "voice": voice,
                    "audio": kind,
                    "apm": apm,
                    "audio_file_sha256": sha256_file(VOICES_DIR / f"{voice}.wav"),
                    "recording_seconds": round(len(y) / vs.SR, 2),
                    "chrome": {
                        k: log.get(k)
                        for k in (
                            "browser_version",
                            "local_settings",
                            "codec",
                            "outbound",
                            "inbound",
                        )
                    },
                    "wall_s": round(time.time() - t0, 1),
                    "verify": verify(y, keys, MEET),
                }
                if kind == "sealed":
                    run["control_relay_other_meeting"] = verify(y, keys, OTHER)
                    run["control_replay_epoch_plus_3"] = verify(y, keys[3:], MEET)
                if kind == "sealed" and apm:
                    stress: dict[str, Any] = {}
                    for f in (0.97, 1.03):
                        st = tmp / f"tempo{f}.wav"
                        sox_tempo(_wav_of(webm, tmp), st, f)
                        ys = decode_path(st)
                        stress[f"sox_tempo_{f}"] = {
                            "fixed_rate": verify(ys, keys, MEET),
                            "rate_search": verify(ys, keys, MEET, rates=RATES),
                        }
                    if rn_model and rn_model.exists():
                        dn = tmp / "rnnoise.wav"
                        ffmpeg_filter(_wav_of(webm, tmp), dn, f"arnndn=m={rn_model}")
                        stress["rnnoise_arnndn"] = verify(decode_path(dn), keys, MEET)
                    run["stress_on_recording"] = stress
                out["runs"].append(run)
                vfy = run["verify"]
                print(
                    f"{voice} {kind} apm={apm}: sealed={vfy['sealed']} "
                    f"z_mean={vfy['z_mean_speech_epochs']} epochs "
                    f"{vfy['epochs_sealed']}/{vfy['epochs_with_speech']} "
                    f"t={vfy['time_to_verdict_s']}",
                    flush=True,
                )
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "seal_webrtc_probe.json").write_text(json.dumps(out, indent=1))
    print("wrote results/seal_webrtc_probe.json")


def _wav_of(webm: Path, tmp: Path) -> Path:
    dst = tmp / (webm.stem + "_dec.wav")
    if not dst.exists():
        wavfile.write(
            dst, vs.SR, np.round(np.clip(decode_path(webm), -1, 1) * 32767).astype(np.int16)
        )
    return dst


if __name__ == "__main__":
    main()
