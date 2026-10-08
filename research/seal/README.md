# Voice Seal evidence: what was measured, how to reproduce it, what it does NOT show

Design: `docs/SEAL.md`. Code under test: `src/satyapan/seal/` (the same module the API uses).
All audio is **synthetic** (Kokoro-82M stock voices, Apache-2.0). No real person's voice is used.
Audio is generated **outside the repo** (`$SATYAPAN_SEAL_DATA`, default `~/.cache/satyapan/seal`);
only hashes of it are committed (data manifests inside the result files). No number below comes
from a random-number "simulation" of a result: every one is produced by running the scripts on
real audio through real codecs or a real browser. Seeded generators are used only for
experimental conditions (network delay, packet-loss pattern, noise), and the seeds are recorded.

## 1. Files

| Script | Output | What it measures |
|---|---|---|
| `gen_voices.py` | `$SATYAPAN_SEAL_DATA/voices/*.wav` | 10 synthetic voices (6 English, 4 Hindi), 38-65 s each, 16 kHz |
| `run_codec_eval.py` | `results/seal_codec_eval.csv`, `results/seal_codec_epochs.csv`, `results/seal_summary.json` | genuine vs attack sessions through 14 real codec chains |
| `webrtc_probe.py` | `results/seal_webrtc_probe.json` | sealed audio through real Chrome WebRTC (APM on/off), Opus, NetEQ |
| `quality.py` | `results/seal_quality.json` | PESQ-WB / STOI proxies of audibility |
| `channels.py`, `common.py` | — | codec chains (ffmpeg libopus / pcm_mulaw / libmp3lame, sox AMR-NB), paths, manifest helpers |

## 2. Codec-chain evaluation (`run_codec_eval.py`)

**Cases** (per voice × chain): H1 sealed by Rajesh for meeting M, checked as Rajesh/M; H0u
unsealed speech (stands for any clone); H0r relay (sealed for meeting M′); H0s replay (epoch e
played at e+3); H0i wrong identity (Meera's key, claimed as Rajesh). Unknown network delay
0-120 ms; live receiver protocol (`voiceseal.detect`, looks after epoch 0 and epochs 0+1,
±200 ms acquisition, threshold 5.49 for 51 lags at 10⁻⁶; alpha-spending Stouffer afterwards).

**How to read the numbers**
- *Genuine verified*: sessions (one per voice) whose protocol reached "sealed".
- *Attacks falsely sealed*: attack sessions (4 per voice) that reached "sealed". Must be 0.
- *Time to verdict*: seconds of sealed speech from the first sealed epoch until the verdict;
  key-disclosure latency (≤ 1 s) not included.
- *z*: per-epoch correlation score of epochs AFTER acquisition (fixed lag, so unbiased).
  Under "not sealed" it is N(0,1) by construction.

**Result** (n = 10 voices; 140 genuine and 560 attack sessions; commit `d6ae619`):

| Chain | Genuine verified | Median / max time to verdict | Genuine z mean (epochs z ≥ 4) | Attacks falsely sealed | Attack z mean / std / max |
|---|---|---|---|---|---|
| No codec | 10/10 | 5 / 5 s | 7.12 (100 %) | 0/40 | +0.06 / 1.06 / 2.98 |
| Opus 32k 48 kHz (Meet-like) | 10/10 | 5 / 5 s | 6.47 (96 %) | 0/40 | −0.06 / 0.98 / 2.75 |
| Opus 24k | 10/10 | 5 / 10 s | 6.30 (97 %) | 0/40 | +0.05 / 1.00 / 3.04 |
| Opus 16k 16 kHz (WhatsApp-style note) | 10/10 | 5 / 10 s | 5.98 (96 %) | 0/40 | +0.02 / 1.01 / 2.67 |
| Opus 12k | 10/10 | 5 / 10 s | 5.16 (90 %) | 0/40 | −0.03 / 1.01 / 2.63 |
| Opus 8k narrowband | 10/10 | 10 / 20 s | 4.74 (77 %) | 0/40 | −0.08 / 1.05 / 3.13 |
| AMR-NB 12.2k (mobile call) | 10/10 | 5 / 10 s | 5.18 (83 %) | 0/40 | +0.10 / 1.00 / 3.13 |
| AMR-NB 4.75k (worst mode) | 10/10 | 20 / 45 s | 3.27 (24 %) | 0/40 | +0.10 / 0.98 / 2.86 |
| G.711 µ-law (PSTN) | 10/10 | 5 / 5 s | 6.92 (99 %) | 0/40 | +0.02 / 1.01 / 2.80 |
| MP3 32k | 10/10 | 5 / 5 s | 6.63 (99 %) | 0/40 | +0.05 / 1.04 / 2.59 |
| Opus 24k + 5 % frame loss (no PLC) | 10/10 | 5 / 10 s | 6.05 (93 %) | 0/40 | +0.08 / 1.04 / 3.08 |
| Opus 24k + white noise 15 dB SNR | **9/10** | 10 / 25 s | 3.87 (49 %) | 0/40 | +0.13 / 0.94 / 2.36 |
| Opus 24k → AMR-NB 12.2 (dial-in) | 10/10 | 5 / 20 s | 4.74 (70 %) | 0/40 | +0.05 / 1.14 / 3.10 |
| −9 dB gain + Opus 16k | 10/10 | 5 / 10 s | 5.81 (94 %) | 0/40 | +0.03 / 1.07 / 2.30 |

Pooled: **0/560 attack sessions falsely sealed**; 3,920 post-acquisition attack epochs with
**mean +0.04, std 1.03, max 3.13, none ≥ 4**; per attack type: clone +0.03/1.02, relay −0.01/1.05,
replay +0.09/0.99, wrong identity +0.04/1.04. **139/140 genuine sessions verified** (decided at
5 s: 93, at 10 s: 36, by later Stouffer looks: 10; miss: hf_alpha, Opus 24k + 15 dB noise; the
miss is fail-safe: "not sealed" means a callback, not harm). Language (pooled over all 14 chains):
English 6 voices genuine z 5.46, attack z +0.06 / 1.03 (n = 2,856); Hindi 4 voices genuine z
5.94, attack z −0.02 / 1.03 (n = 1,064) (`seal_summary.json → pooled.by_language`). Python embed
cost 0.4 % of real time; detection median 6 ms per session (one 38-65 s stream, 51 lags).

Compared with the lab notebook (§5.A of the innovation report: 0/560, 139/140, miss at AMR-NB
4.75): the in-repo module now uses exact 5.000 s epochs, alpha-spending later looks and a
fresh corpus; the numbers move slightly (AMR-NB 4.75 is now 10/10 at a 20 s median; the one miss
moved to the 15 dB-noise chain). Both runs agree on the headline: no false seals.

## 3. Chrome WebRTC realism probe (`webrtc_probe.py`)

Headless Chromium 141 (Playwright), `--use-fake-device-for-media-stream
--use-file-for-fake-audio-capture=<sealed 48 kHz wav>%noloop`; `getUserMedia` with
echoCancellation / noiseSuppression / autoGainControl all **true** (Chrome's WebRTC APM: AEC3,
NS, AGC2) or all **false**; a real loopback `RTCPeerConnection` pair (Opus 48 kHz, in-band FEC,
NetEQ on receive); the remote track recorded with MediaRecorder (Opus/WebM 128 kbps); seal
verified on the recording with the upload verifier (unknown offset).

| Voice | APM | Sealed? | Time to verdict | Sealed epochs | z mean | Controls on the same recording |
|---|---|---|---|---|---|---|
| am_michael (EN) | on | yes | 5 s | 13/13 | 6.89 | other meeting: not sealed (A 3.22 < 5.98); replay e+3: not sealed (2.99) |
| am_michael (EN) | off | yes | 5 s | 13/13 | 6.79 | relay 3.61, replay 2.85: not sealed |
| hf_alpha (HI) | on | yes | 10 s | 9/9 | 5.27 | relay 2.37, replay 3.38: not sealed |
| hf_alpha (HI) | off | yes | 10 s | 9/9 | 5.48 | relay 2.73, replay 3.15: not sealed |
| am_michael / hf_alpha UNSEALED | on | no / no | — | 0/13, 0/9 | — | acquisition 3.39 / 3.33 < 5.98 |

NetEQ was active (≈1,080-1,440 samples inserted for deceleration, up to 247 removed for
acceleration per run; no loss in loopback). **Stress on the APM-on recordings:**

| Stress | am_michael | hf_alpha |
|---|---|---|
| RNNoise ML denoiser (ffmpeg `arnndn`, GregorR `sh.rnnn`, sha256 70bb6685…) | sealed, 13/13, z 6.69 | sealed, 9/9, z 5.49 |
| sox `tempo 0.97` (constant 3 % slower), fixed-rate verifier | **not sealed** (0/14) | **not sealed** (0/9) |
| same, with playback-rate search (17 rates 0.96-1.04, threshold 6.42) | sealed, but 5/13 epochs | sealed, 4/9 epochs |
| sox `tempo 1.03`, fixed rate / rate search | not sealed / sealed 5/13 | not sealed / sealed 5/9 |

Reading: Chrome's own client processing (APM on or off, Opus, NetEQ under loopback) does not
hurt the seal. A **constant** 3 % time-scale breaks fixed-rate verification; the rate search
recovers the verdict but not every epoch (WSOLA time-stretch also cuts/duplicates segments, and
the rate grid is coarse). NetEQ in practice stretches in short bursts that kept the seal intact
here, but under real jitter it could do more: this is the first thing to measure on two laptops,
and a finer drift tracker (paid for in the threshold, never re-maximised per epoch) is the
planned fix.

**Not covered** (must be tested on two laptops): Google Meet's server side and its ML noise
cancellation, real network jitter and loss, the speaker→microphone path, headsets, and other
participants mixed into the tab audio.

## 4. Audibility proxies (`quality.py`)

PESQ-WB and STOI vs the clean original, first 30 s of each of the 10 voices (`results/seal_quality.json`):

| Condition | PESQ-WB mean (min) | STOI mean |
|---|---|---|
| Seal ±1.0 dB | 4.63 (4.62) | 0.997 |
| Seal ±1.5 dB | 4.62 (4.61) | 0.993 |
| **Seal ±2.0 dB (used)** | **4.61 (4.60)** | **0.988** |
| Seal ±2.5 dB | 4.59 (4.58) | 0.982 |
| Seal ±2.0 dB, then Opus 16k | 4.24 (4.13) | 0.976 |
| Anchor: plain Opus 16k, no seal | 4.29 (4.20) | 0.986 |
| Anchor: plain Opus 32k, no seal | 4.46 (4.41) | 0.994 |
| Anchor: plain MP3 32k, no seal | 3.47 (3.23) | 0.994 |

Reading: by these proxies the seal costs less than the codec it travels through (seal alone
4.61 vs plain Opus 32k 4.46). PESQ is lenient on slow level changes (the seal is a 21 Hz band
"flutter"), so these do **not** replace the listening test in §6.

## 5. Reproduce

```bash
# deps: ffmpeg (libopus, libmp3lame), sox with AMR-NB (libsox-fmt-all + libopencore-amrnb0),
#       numpy, scipy; kokoro-onnx (voices); playwright + Chromium (WebRTC); pesq, pystoi (quality)
export SATYAPAN_SEAL_DATA=~/.cache/satyapan/seal
python research/seal/gen_voices.py --models /path/to/kokoro   # kokoro-v1.0.int8.onnx + voices-v1.0.bin
python research/seal/run_codec_eval.py --workers 2              # ~5 min on 2 cores
python research/seal/webrtc_probe.py --voices am_michael,hf_alpha --rnnoise sh.rnnn   # ~6 min
python research/seal/quality.py
python scripts/seal_screenshots.py                              # demo PNGs (needs `uv sync`)
```

## 6. Two-laptop Google Meet test (the team runs this on the Mac; ~1 hour)

Goal: does the seal survive Meet's own pipeline, with **Meet noise cancellation ON and OFF**?

1. **Make the test audio** (synthetic or a consented teammate's voice only):
   `python scripts/seal_cli.py seal --seed meet-test-1 --meeting <meet code> voice.wav sealed.wav`
   (use the real code of the meeting you will open, e.g. `abc-defg-hij`). Also keep the
   unsealed `voice.wav` as the control.
2. **Laptop A (sender)**: install BlackHole 2ch; set Meet's microphone to BlackHole; play
   `sealed.wav` into BlackHole (QuickTime/afplay with output = BlackHole). Join the meeting.
3. **Laptop B (receiver)**: join the same meeting, record the tab audio (the T07 extension
   capture, or QuickTime "New Audio Recording" with a loopback device) for the whole file.
4. Run four recordings: Meet **noise cancellation ON** and **OFF** (Settings → Audio), each with
   `sealed.wav` and with `voice.wav` (control). Note Wi-Fi, Meet version, Chrome version.
5. **Verify on laptop B**:
   `python scripts/seal_cli.py verify --seed meet-test-1 --meeting <meet code> rec.m4a --json out.json`
   and, for drift, `--rates 0.98 0.985 0.99 0.995 1.0 1.005 1.01 1.015 1.02`.
   Also verify the sealed recording with a *different* meeting code (must say NOT SEALED).
6. **Report** per recording: verdict, sealed epochs / epochs with speech, z per epoch, time to
   verdict. Pass criteria: sealed recordings verified with median z ≥ 4; controls not sealed.
7. If z drops below ~4: retest with noise cancellation off; if still low, re-seal at 2.5 dB
   (`--amp 2.5`) or ask for 10 s epochs; if only later epochs fail, it is drift (use `--rates`).
8. **Listening test** (10 minutes, 3 teammates): A/B the original vs sealed at 1.5 and 2.0 dB
   (make them with `--amp`), blind, and record "can hear a difference: yes/no" per pair in the
   deck's assumptions table. If 2.0 dB is audible, use 1.5 dB.
