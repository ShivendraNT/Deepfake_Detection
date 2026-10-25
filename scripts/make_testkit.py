"""Build a realistic, local-only test kit for every Satya media path.

    uv run python scripts/make_testkit.py             # builds in ~/Desktop/SATYA_DEMO_KIT
    uv run python scripts/make_testkit.py --skip-video
    uv run python scripts/make_testkit.py --verify

What it makes (sitting prominently on your Desktop as `SATYA_DEMO_KIT/`):

  1_VOICE_CALLS_AND_AUDIO/
      synthetic Indian-accented executive voice notes (macOS Rishi), neural vocoder clones (Piper),
      Hindi (Lekha), Hinglish, WhatsApp Opus re-encoded, short (<3s) edge case, noisy room note,
      and bonafide human speech controls.
  2_VIDEO_MEETINGS_AND_CLIPS/
      realistic Google Meet executive video conference deepfakes (executive in business suit and tie,
      Google Meet UI overlay, face swap manipulation, synced with CFO payment request audio),
      real executive control, Arup cheapfake (real face + fake voice), and 360p call quality.
  3_INVOICES_AND_EMAILS/
      altered bank account invoices (PDF + mobile photo + scanned PDF) and phishing emails
      (BEC bank change, DMARC spoof, lookalike domain, prompt injection) alongside genuine controls.
  4_SCAM_MESSAGES_AND_SCRIPTS/
      real-world Indian scam scripts (CBI digital arrest EN/Hinglish, courier customs parcel,
      CEO gift cards, vendor bank change) and genuine banking SMS/reminders.
  manifest.json & README.md
      file checksums, expected verdicts, and step-by-step instructions for the Companion UI.
"""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path("/Users/shivendranarayantripathi/Desktop/SATYA_DEMO_KIT")
CACHE_TESTKIT = ROOT / ".cache" / "testkit"
PIPER_MODEL = ROOT / ".cache" / "piper" / "en_US-ryan-medium.onnx"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/{file}"
FFPP = "https://huggingface.co/datasets/gonnerthetooner/FaceForensics/resolve/main/"
FFPP_DIR = "faceforensics_c23/FaceForensics%2B%2B_C23"
PUBLIC_SPEECH = (
    "https://upload.wikimedia.org/wikipedia/commons/7/7c/Marcus_Garvey%2C_speech%2C_1921.ogg"
)

CFO_EN = (
    "Priya, this is Rajesh. I am stuck in a board meeting, so I cannot talk long. "
    "We are closing a confidential acquisition today. I need you to transfer forty eight "
    "lakh rupees to the new escrow account I sent on chat. Please do not loop in Arjun, "
    "keep this between us. Skip the usual approval, I will sign it off later."
)
CFO_HINGLISH = (
    "Priya, Rajesh bol raha hoon. Main board meeting mein hoon, zyada baat nahi kar sakta. "
    "Aaj ek confidential acquisition close ho rahi hai. Naye escrow account mein forty eight "
    "lakh rupaye transfer kar do, details chat par bhej raha hoon. Arjun ko mat batana, "
    "yeh humare beech rahe. Approval skip kar do, main baad mein sign kar dunga."
)
CFO_HI = (
    "प्रिया, मैं राजेश बोल रहा हूँ। मैं बोर्ड मीटिंग में हूँ, ज़्यादा बात नहीं कर सकता। "
    "आज एक गोपनीय अधिग्रहण पूरा हो रहा है। नए एस्क्रो खाते में अड़तालीस लाख रुपये "
    "ट्रांसफर कर दो, डिटेल चैट पर भेज रहा हूँ। अर्जुन को मत बताना, यह हमारे बीच रहे। "
    "अप्रूवल स्किप कर दो, मैं बाद में साइन कर दूँगा।"
)
BENIGN_TTS = (
    "Hi team, please review the vendor delivery report before our next scheduled review. "
    "The invoice copy is attached for your records."
)

TEXTS = {
    "fake_digital_arrest_en.txt": (
        "This is Inspector Sharma from CBI. Your Aadhaar is linked to a money-laundering case. "
        "You are under digital arrest. Do not tell anyone. Transfer fifty thousand rupees to "
        "the RBI safe account and read me the OTP you receive. Stay on the video call."
    ),
    "fake_digital_arrest_hinglish.txt": (
        "Main CBI se Inspector Sharma bol raha hoon. Aapke Aadhaar par money laundering case "
        "hai. Aap digital arrest mein hain. Kisi ko mat batana. RBI safe account mein pachaas "
        "hazaar rupaye transfer karo aur OTP batao. Video call par raho."
    ),
    "fake_courier_parcel.txt": (
        "Your parcel from Mumbai has been seized. It contains illegal drugs and a fake passport. "
        "Pay the clearance fee of 25,000 rupees today or a police case will be filed. "
        "Call this number and share the UPI PIN for verification."
    ),
    "fake_ceo_gift_cards.txt": (
        "I am in a meeting and cannot talk. Buy ten Amazon gift cards of 10,000 rupees each "
        "and send me the codes. Keep this confidential, do not tell finance."
    ),
    "fake_vendor_bank_change.txt": (
        "Dear Accounts, our bank details have changed. Please update our record and use the "
        "new account 99997777009917, IFSC FAKD0000991 for invoice NDL-2026-1009. "
        "The old account is blocked, so pay today itself."
    ),
    "real_bank_otp_sms.txt": (
        "Your OTP for a transaction of Rs 1 is 123456. Do not share this OTP with anyone. "
        "Your bank never asks for an OTP or PIN."
    ),
    "real_meeting_notes.txt": (
        "Team, please review the vendor delivery report before Friday's scheduled review. "
        "The invoice copy is attached for your records."
    ),
    "real_invoice_reminder.txt": (
        "Gentle reminder: invoice KDP/2026/0917 for 2,10,000 rupees is due on 30 October. "
        "Please process it in the normal payment run. No change in bank details."
    ),
}


def _run(cmd: list[object], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([str(c) for c in cmd], check=True, **kwargs)  # type: ignore[arg-type]


def _ffmpeg(*args: object) -> None:
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args])


def _duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip() or 0.0)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _download(url: str, dest: Path, min_bytes: int = 1024) -> bool:
    if dest.exists() and dest.stat().st_size >= min_bytes:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {url.split('/')[-1]} …")
    try:
        request = urllib.request.Request(  # noqa: S310 - fixed https URLs only
            url, headers={"User-Agent": "satyapan-testkit/1.0 (+local research)"}
        )
        with urllib.request.urlopen(request, timeout=180) as response, tmp.open("wb") as fh:  # noqa: S310
            shutil.copyfileobj(response, fh)
    except Exception as exc:  # noqa: BLE001 - offline is a supported state
        print(f"  ! download failed: {exc}")
        tmp.unlink(missing_ok=True)
        if shutil.which("curl"):
            print("  retrying with curl …")
            proc = subprocess.run(
                [
                    "curl",
                    "-sSfL",
                    "--max-time",
                    "180",
                    "-A",
                    "satyapan-testkit/1.0",
                    "-o",
                    str(tmp),
                    url,
                ],
                capture_output=True,
            )
            if proc.returncode != 0:
                print(f"  ! curl failed: {proc.stderr.decode(errors='replace').strip()}")
                tmp.unlink(missing_ok=True)
                return False
        else:
            return False
    if tmp.stat().st_size < min_bytes:
        print(f"  ! download too small ({tmp.stat().st_size} bytes)")
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _piper_model() -> Path | None:
    if PIPER_MODEL.exists() and PIPER_MODEL.with_suffix(".onnx.json").exists():
        return PIPER_MODEL
    for name in ("en_US-ryan-medium.onnx", "en_US-ryan-medium.onnx.json"):
        if not _download(PIPER_URL.format(file=name), PIPER_MODEL.parent / name):
            return None
    return PIPER_MODEL if PIPER_MODEL.exists() else None


def _piper(text: str, out: Path) -> bool:
    model = _piper_model()
    if model is None:
        print("  ! Piper voice unavailable; skipping synthetic take")
        return False
    raw = out.with_name(out.stem + ".piper.wav")
    try:
        from piper import PiperVoice

        voice = PiperVoice.load(str(model))
        with wave.open(str(raw), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
    except Exception as exc:
        print(f"  ! Piper in-process failed ({exc}); falling back")
        return False
    _ffmpeg("-i", raw, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out)
    raw.unlink(missing_ok=True)
    return True


def _say(text: str, voice: str, out: Path) -> bool:
    if shutil.which("say") is None:
        return False
    raw = out.with_name(out.stem + ".say.aiff")
    try:
        _run(["say", "-v", voice, "-o", str(raw), text], capture_output=True)
    except subprocess.CalledProcessError:
        return False
    _ffmpeg("-i", raw, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out)
    raw.unlink(missing_ok=True)
    return True


def _silence(out: Path, seconds: float) -> None:
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono",
        "-t",
        f"{seconds:.3f}",
        "-c:a",
        "pcm_s16le",
        out,
    )


def make_audio(out: Path) -> dict[str, dict[str, object]]:
    audio = out / "1_VOICE_CALLS_AND_AUDIO"
    audio.mkdir(parents=True, exist_ok=True)
    notes: dict[str, dict[str, object]] = {}

    # 1. Authentic Indian English CFO clone (macOS Rishi - realistic executive accent)
    cfo_indian = audio / "fake_cfo_clone_indian_en.wav"
    if _say(CFO_EN, "Rishi", cfo_indian):
        notes[cfo_indian.name] = {
            "kind": "audio",
            "label": "synthetic",
            "expected": "realistic Indian English CFO voice clone; asks A1/A4/A5 trigger HOLD band",
        }

    # 2. Neural vocoder English CFO clone (Piper ONNX Ryan - triggers neural TTS detector)
    cfo_neural = audio / "fake_cfo_clone_neural_en.wav"
    if _piper(CFO_EN, cfo_neural):
        notes[cfo_neural.name] = {
            "kind": "audio",
            "label": "synthetic",
            "expected": "neural vocoder TTS; voice detector says LIKELY_SYNTHETIC; band HOLD",
        }

    # 3. Hindi voice note (macOS Lekha)
    hindi = audio / "fake_cfo_clone_hindi.wav"
    if _say(CFO_HI, "Lekha", hindi):
        notes[hindi.name] = {
            "kind": "audio",
            "label": "synthetic",
            "expected": "Hindi voice note synthesis; asks should fire on Hindi ASR transcript",
        }

    # 4. Hinglish voice note
    hinglish = audio / "fake_cfo_clone_hinglish.wav"
    if _say(CFO_HINGLISH, "Rishi", hinglish) or _piper(CFO_HINGLISH, hinglish):
        notes[hinglish.name] = {
            "kind": "audio",
            "label": "synthetic",
            "expected": "natural Hinglish executive voice note; asks should fire",
        }

    # 5. Benign TTS control
    benign = audio / "fake_benign_tts.wav"
    if _piper(BENIGN_TTS, benign) or _say(BENIGN_TTS, "Rishi", benign):
        notes[benign.name] = {
            "kind": "audio",
            "label": "synthetic-benign",
            "expected": "voice flagged synthetic even though text is benign (raise-only test)",
        }

    # Base audio for WhatsApp compression and noise
    base = cfo_indian if cfo_indian.exists() else cfo_neural

    if base.exists():
        # 6. WhatsApp voice note (Opus 16k)
        opus = audio / "fake_cfo_clone_whatsapp.ogg"
        _ffmpeg("-i", base, "-c:a", "libopus", "-b:a", "16k", opus)
        notes[opus.name] = {
            "kind": "audio",
            "label": "synthetic",
            "expected": "WhatsApp-compressed Opus voice note; asks and voice check fire",
        }

        # 7. Short note edge case (<3s)
        short = audio / "fake_cfo_clone_short_2sec.wav"
        _ffmpeg("-i", base, "-t", "2.4", "-c:a", "pcm_s16le", short)
        notes[short.name] = {
            "kind": "audio",
            "label": "synthetic-short",
            "expected": "under 3 seconds of audio: grey SPEECH_TOO_SHORT flag, never PASS",
        }

        # 8. Noisy room note
        noisy = audio / "fake_cfo_clone_noisy_room.wav"
        _ffmpeg(
            "-i",
            base,
            "-f",
            "lavfi",
            "-i",
            "anoisesrc=color=white:amplitude=0.05",
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0",
            "-c:a",
            "pcm_s16le",
            noisy,
        )
        notes[noisy.name] = {
            "kind": "audio",
            "label": "synthetic-noisy",
            "expected": "background ambient office noise test: asks still fire",
        }

    # 9. Genuine human speech control (Marcus Garvey 1921 speech, public domain)
    public = audio / "real_human_speech_control.wav"
    raw_public = audio / "_public.ogg"
    if _download(PUBLIC_SPEECH, raw_public, min_bytes=50_000):
        _ffmpeg(
            "-i", raw_public, "-t", "12", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", public
        )
        raw_public.unlink(missing_ok=True)
        notes[public.name] = {
            "kind": "audio",
            "label": "human-public-domain",
            "expected": "real human speech control: NO_SIGNS, band PASS",
            "source": "Wikimedia Commons, Marcus Garvey speech 1921 (public domain)",
        }
    raw_public.unlink(missing_ok=True)

    # 10. Instructions for maker's own voice note
    (audio / "real_voice_note_instructions.txt").write_text(
        "RECORD YOUR OWN BONAFIDE CONTROL:\n\n"
        "1. Open Voice Memos on your Mac or phone.\n"
        "2. Record a 10-second normal sentence, for example:\n"
        "   'Hi Priya, please review the vendor delivery report before our team sync today.'\n"
        "3. Drag and drop the recording into this folder as 'real_my_voice.wav'.\n"
        "4. Drop it onto Satya companion: the voice check will report NO_SIGNS (PASS).\n",
        encoding="utf-8",
    )
    notes["real_voice_note_instructions.txt"] = {
        "kind": "instructions",
        "label": "human",
        "expected": "record your own bonafide human voice control",
    }
    return notes


def _create_meet_overlay(out_png: Path) -> None:
    """Generate a crisp Google Meet conference overlay image using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1280, 720
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_large = font_small = font_bold = None
    candidates = [
        "/System/Library/Fonts/SFProText-Regular.otf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                font_large = ImageFont.truetype(c, 18)
                font_small = ImageFont.truetype(c, 13)
                font_bold = ImageFont.truetype(c, 15)
                break
            except Exception:
                pass
    if font_large is None:
        font_large = font_small = font_bold = ImageFont.load_default()

    # Top meeting bar
    draw.rectangle([(0, 0), (w, 50)], fill=(20, 20, 24, 210))
    draw.text(
        (24, 15),
        "Acquisition Sync - Urgent Escrow | Google Meet",
        fill=(255, 255, 255, 240),
        font=font_large,
    )
    draw.text((w - 150, 17), "REC * 00:04:18", fill=(235, 87, 87, 240), font=font_small)

    # Participant badge (bottom-left)
    badge_x, badge_y = 28, h - 100
    badge_w, badge_h = 240, 36
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=18,
        fill=(32, 33, 36, 220),
    )
    draw.ellipse(
        [(badge_x + 10, badge_y + 8), (badge_x + 30, badge_y + 28)], fill=(52, 168, 83, 255)
    )
    draw.text(
        (badge_x + 38, badge_y + 9), "Rajesh Kumar (CFO)", fill=(255, 255, 255, 255), font=font_bold
    )

    # Bottom control bar
    bar_h = 60
    draw.rectangle([(0, h - bar_h), (w, h)], fill=(32, 33, 36, 230))
    cx = w // 2
    btn_r = 18
    colors = [
        (60, 64, 67, 255),
        (60, 64, 67, 255),
        (60, 64, 67, 255),
        (60, 64, 67, 255),
        (234, 67, 53, 255),
    ]
    for i, col in enumerate(colors):
        bx = cx - 100 + i * 50
        by = h - 30
        draw.ellipse([(bx - btn_r, by - btn_r), (bx + btn_r, by + btn_r)], fill=col)

    # Self tile PiP (bottom-right)
    tile_w, tile_h = 180, 110
    tx, ty = w - tile_w - 24, h - bar_h - tile_h - 16
    draw.rounded_rectangle(
        [(tx, ty), (tx + tile_w, ty + tile_h)],
        radius=10,
        fill=(45, 52, 54, 230),
        outline=(90, 95, 100, 200),
        width=2,
    )
    draw.text(
        (tx + 14, ty + tile_h - 26),
        "You (Finance Maker)",
        fill=(220, 220, 220, 240),
        font=font_small,
    )

    overlay.save(out_png)


def make_video(out: Path) -> dict[str, dict[str, object]]:
    video = out / "2_VIDEO_MEETINGS_AND_CLIPS"
    video.mkdir(parents=True, exist_ok=True)
    notes: dict[str, dict[str, object]] = {}

    # Executive sequences: 002.mp4 (real executive) and 002_006.mp4 (deepfake swap)
    real_src = video / "_src_real_exec.mp4"
    fake_src = video / "_src_fake_exec.mp4"
    ok_real = _download(FFPP + FFPP_DIR + "/original/002.mp4", real_src, min_bytes=200_000)
    ok_fake = _download(FFPP + FFPP_DIR + "/Deepfakes/002_006.mp4", fake_src, min_bytes=200_000)

    if not (ok_real and ok_fake):
        print("  ! Video samples unavailable; continuing with remaining kit")
        return notes

    # Generate Google Meet overlay
    overlay_png = video / "_meet_overlay.png"
    _create_meet_overlay(overlay_png)

    # Audio sources
    cfo_audio = out / "1_VOICE_CALLS_AND_AUDIO" / "fake_cfo_clone_indian_en.wav"
    if not cfo_audio.exists():
        cfo_audio = out / "1_VOICE_CALLS_AND_AUDIO" / "fake_cfo_clone_neural_en.wav"

    filter_meet = (
        "[0:v]crop=1280:610:0:110,scale=1280:720[cropped];"
        "[cropped][1:v]overlay=0:0,format=yuv420p[v]"
    )

    # 1. Realistic Deepfake Video Meeting (Google Meet Call with CFO Face-Swap & Voice Clone)
    fake_meet = video / "fake_cfo_google_meet_deepfake_720p.mp4"
    if cfo_audio.exists():
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                fake_src,
                "-i",
                overlay_png,
                "-i",
                cfo_audio,
                "-filter_complex",
                filter_meet,
                "-map",
                "[v]",
                "-map",
                "2:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                fake_meet,
            ]
        )
        notes[fake_meet.name] = {
            "kind": "video",
            "label": "synthetic",
            "expected": "realistic Google Meet executive deepfake; face swap detected; asks escalate to HOLD",
            "source": "FaceForensics++ 002_006 executive clip with Google Meet interface + CFO audio",
        }

    # 2. Genuine Executive Video Meeting Control (Real Executive on Google Meet)
    real_meet = video / "real_cfo_google_meet_genuine_720p.mp4"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            real_src,
            "-i",
            overlay_png,
            "-filter_complex",
            filter_meet,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-an",
            "-t",
            "20",
            real_meet,
        ]
    )
    notes[real_meet.name] = {
        "kind": "video",
        "label": "human",
        "expected": "bonafide human executive video call: NO_SIGNS on face check; band PASS",
        "source": "FaceForensics++ 002 original executive clip with Google Meet interface",
    }

    # 3. Arup Hong Kong Cheapfake ($25M scam model: Real face footage + Voice clone)
    if cfo_audio.exists():
        arup_cheapfake = video / "fake_cfo_cheapfake_real_face_clone_voice.mp4"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                real_src,
                "-i",
                overlay_png,
                "-i",
                cfo_audio,
                "-filter_complex",
                filter_meet,
                "-map",
                "[v]",
                "-map",
                "2:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                arup_cheapfake,
            ]
        )
        notes[arup_cheapfake.name] = {
            "kind": "video",
            "label": "cheapfake",
            "expected": "Arup case: real face -> face check passes, but voice clone + asks escalate to HOLD",
            "source": "FaceForensics++ 002 real executive face + cloned CFO voice",
        }

    # 4. Low-bandwidth 360p WebM call (VP8 + Opus)
    if cfo_audio.exists():
        call360 = video / "fake_cfo_call_low_bandwidth_360p.webm"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                fake_src,
                "-i",
                overlay_png,
                "-i",
                cfo_audio,
                "-filter_complex",
                "[0:v]crop=1280:610:0:110,scale=640:360[cropped];[1:v]scale=640:360[ov];[cropped][ov]overlay=0:0,format=yuv420p[v]",
                "-map",
                "[v]",
                "-map",
                "2:a:0",
                "-c:v",
                "libvpx",
                "-b:v",
                "400k",
                "-c:a",
                "libopus",
                "-b:a",
                "16k",
                "-shortest",
                call360,
            ]
        )
        notes[call360.name] = {
            "kind": "video",
            "label": "synthetic-compressed",
            "expected": "360p low-bandwidth mobile video call; robust detection under compression",
            "source": "FaceForensics++ 002_006 VP8 400kbps + Opus 16kbps",
        }

    # 5. Visual-only silent deepfake
    silent_fake = video / "fake_cfo_silent_visual_only.mp4"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            fake_src,
            "-i",
            overlay_png,
            "-filter_complex",
            filter_meet,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-an",
            "-t",
            "20",
            silent_fake,
        ]
    )
    notes[silent_fake.name] = {
        "kind": "video",
        "label": "synthetic",
        "expected": "visual face swap only: tests computer vision detection without audio cues",
        "source": "FaceForensics++ 002_006",
    }

    # 6. Safety edge case: Face too small (<64px) -> Abstain
    small = video / "fake_cfo_face_small_abstain.mp4"
    if cfo_audio.exists():
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                fake_src,
                "-i",
                cfo_audio,
                "-vf",
                "scale=320:180",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-crf",
                "28",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-shortest",
                small,
            ]
        )
        notes[small.name] = {
            "kind": "video",
            "label": "synthetic-small",
            "expected": "face under 64px: video detector abstains (no false confidence); asks still fire",
            "source": "FaceForensics++ 002_006 scaled to 180p",
        }

    # Clean up temporary sources
    for temp in (real_src, fake_src, overlay_png):
        temp.unlink(missing_ok=True)
    return notes


def _scanned_pdf(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    font = None
    for cand in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(cand).exists():
            try:
                font = ImageFont.truetype(cand, 34)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()
    lines = [
        "KAVERI DEMO PACKAGING PVT LTD",
        "Fictional Bank A  |  GSTIN 00FAKEV0001A1Z5",
        "",
        "INVOICE  KDP/2026/0920",
        "Date: 03 October 2026",
        "",
        "Bill to: Demo Industries Pvt Ltd",
        "",
        "Description                         Amount",
        "Corrugated packaging, Q3            6,20,000",
        "",
        "Total payable                       6,20,000",
        "",
        "Pay to:",
        "Account  99996666006200",
        "IFSC     FAKE0000620",
        "Bank     Fictional Bank D",
        "",
        "This is a scanned copy of the invoice.",
    ]
    y = 120
    for line in lines:
        draw.text((100, y), line, fill="black", font=font)
        y += 64
    draw.rectangle((80, 80, 1160, 1500), outline="gray", width=3)
    draw.text((700, 1560), "SCANNED COPY", fill="gray", font=font)
    img.save(path, "PDF", resolution=150.0)


def make_documents(out: Path) -> dict[str, dict[str, object]]:
    docs = out / "3_INVOICES_AND_EMAILS"
    docs.mkdir(parents=True, exist_ok=True)
    notes: dict[str, dict[str, object]] = {}

    email_dir = ROOT / "data" / "demo" / "emails"
    email_map = {
        "01_legit_invoice_kaveri.eml": "real_email_legit_invoice_kaveri.eml",
        "02_bec_bank_change_narmada.eml": "fake_email_bec_bank_change_narmada.eml",
        "03_lookalike_kaveri.eml": "fake_email_lookalike_kaveri.eml",
        "04_dmarc_fail_spoofed_cfo.eml": "fake_email_dmarc_fail_spoofed_cfo.eml",
        "05_fake_auth_header.eml": "fake_email_fake_auth_header.eml",
        "06_bank_claim_not_bank_in.eml": "fake_email_bank_claim_not_bank_in.eml",
        "07_bank_in_legit.eml": "real_email_bank_in_legit.eml",
        "08_freemail_ceo.eml": "fake_email_freemail_ceo.eml",
        "09_prompt_injection.eml": "fake_email_prompt_injection.eml",
        "10_no_trusted_auth.eml": "grey_email_no_trusted_auth.eml",
    }
    for src_name, dst_name in email_map.items():
        src = email_dir / src_name
        if src.exists():
            shutil.copyfile(src, docs / dst_name)
            notes[dst_name] = {
                "kind": "email",
                "label": "fake"
                if dst_name.startswith("fake_")
                else ("real" if dst_name.startswith("real_") else "grey"),
                "expected": "see data/demo/emails/expected.json",
            }

    invoice_dir = ROOT / "data" / "demo" / "invoices"
    invoice_map = {
        "inv_kaveri_ok.pdf": "real_invoice_kaveri_legit.pdf",
        "inv_godavari_ok.pdf": "real_invoice_godavari_legit.pdf",
        "inv_tapti_upi_ok.pdf": "real_invoice_tapti_upi_legit.pdf",
        "inv_narmada_changed_bank.pdf": "fake_invoice_narmada_changed_bank.pdf",
        "inv_kaveri_edited_amount.pdf": "fake_invoice_kaveri_edited_amount.pdf",
        "inv_kaveri_edited_bank.pdf": "fake_invoice_kaveri_edited_bank.pdf",
    }
    for src_name, dst_name in invoice_map.items():
        src = invoice_dir / src_name
        if src.exists():
            shutil.copyfile(src, docs / dst_name)
            notes[dst_name] = {
                "kind": "pdf",
                "label": "fake" if dst_name.startswith("fake_") else "real",
                "expected": "see data/demo/invoices/expected.json",
            }

    scanned = docs / "fake_scanned_invoice_image_only.pdf"
    _scanned_pdf(scanned)
    notes[scanned.name] = {
        "kind": "pdf-scanned",
        "label": "fake",
        "expected": "no text layer -> PARSE_FAILURE grey, at least VERIFY, never PASS",
    }

    edited = invoice_dir / "inv_kaveri_edited_bank.pdf"
    photo = docs / "fake_invoice_photo.jpg"
    if edited.exists() and shutil.which("sips"):
        _run(["sips", "-s", "format", "jpeg", edited, "--out", photo], capture_output=True)
        notes[photo.name] = {
            "kind": "image",
            "label": "fake",
            "expected": "photo path: RapidOCR reads text; detects altered account",
        }

    for src_name in ("cfo_escrow_chat.txt", "courier_voice_note_transcript.txt"):
        src = ROOT / "data" / "demo" / "whatsapp" / src_name
        if src.exists():
            dst = docs / ("fake_" + src_name)
            shutil.copyfile(src, dst)
            notes[dst.name] = {
                "kind": "text",
                "label": "fake",
                "expected": "scam chat transcript; asks fire",
            }
    return notes


def make_text(out: Path) -> dict[str, dict[str, object]]:
    text = out / "4_SCAM_MESSAGES_AND_SCRIPTS"
    text.mkdir(parents=True, exist_ok=True)
    notes: dict[str, dict[str, object]] = {}
    for name, body in TEXTS.items():
        path = text / name
        path.write_text(body + "\n", encoding="utf-8")
        notes[name] = {
            "kind": "text",
            "label": "fake" if name.startswith("fake_") else "real",
            "expected": "scam asks raise to HOLD/VERIFY; genuine controls pass",
        }
    return notes


def _readme(out: Path) -> None:
    (out / "README.md").write_text(
        "# Satyapan Grand Finale Demo Kit\n\n"
        "This folder contains verified, real-world-shaped media samples for every detection "
        "modality in **Satyapan / Satya**.\n\n"
        "All data uses fictional names (Rajesh, Priya, Arjun), fake accounts (`9999...`), "
        "and fake IFSC codes (`FAK...`). Never upload real employee or banking data.\n\n"
        "---\n\n"
        "## Folder Structure\n\n"
        "### `1_VOICE_CALLS_AND_AUDIO/`\n"
        "* **`fake_cfo_clone_indian_en.wav`**: Rajesh (CFO) voice clone in Indian English asking Priya to transfer ₹48,50,000 to an unapproved escrow account.\n"
        "* **`fake_cfo_clone_neural_en.wav`**: Neural TTS vocoder synthesis triggering `likely_synthetic` in XLSR voice check.\n"
        "* **`fake_cfo_clone_hindi.wav`**: Hindi voice note asking for emergency transfer.\n"
        "* **`fake_cfo_clone_hinglish.wav`**: Hinglish voice note with authentic vernacular code-switching.\n"
        "* **`fake_cfo_clone_whatsapp.ogg`**: Realistic WhatsApp Opus audio with ambient acoustic compression.\n"
        "* **`fake_cfo_clone_short_2sec.wav`**: Safety edge-case: <3s audio triggers `SPEECH_TOO_SHORT` grey flag.\n"
        "* **`real_human_speech_control.wav`**: Public domain real human speech control (Marcus Garvey 1921) -> PASS.\n\n"
        "### `2_VIDEO_MEETINGS_AND_CLIPS/`\n"
        "* **`fake_cfo_google_meet_deepfake_720p.mp4`**: Executive Rajesh in a business suit and tie on a Google Meet call ('Acquisition Sync') with face-swap deepfake and cloned audio.\n"
        "* **`real_cfo_google_meet_genuine_720p.mp4`**: Genuine executive video meeting control -> PASS.\n"
        "* **`fake_cfo_cheapfake_real_face_clone_voice.mp4`**: The $25M Arup attack vector: genuine video footage paired with cloned audio.\n"
        "* **`fake_cfo_call_low_bandwidth_360p.webm`**: VP8/Opus low-bandwidth call simulating poor network conditions.\n"
        "* **`fake_cfo_silent_visual_only.mp4`**: Visual face swap only (tests CV pipeline without audio hints).\n\n"
        "### `3_INVOICES_AND_EMAILS/`\n"
        "* **`fake_invoice_kaveri_edited_bank.pdf`**: Altered bank account & IFSC on Kaveri Packaging invoice.\n"
        "* **`fake_invoice_photo.jpg`**: Camera photo of edited invoice on desk (tests RapidOCR extraction).\n"
        "* **`fake_scanned_invoice_image_only.pdf`**: Image-only PDF with zero text layer -> PARSE_FAILURE grey flag.\n"
        "* **`real_invoice_kaveri_legit.pdf`**: Authentic invoice matching vendor master -> PASS.\n"
        "* **`fake_email_bec_bank_change_narmada.eml`**: Business Email Compromise claiming vendor bank update.\n"
        "* **`fake_email_dmarc_fail_spoofed_cfo.eml`**: Spoofed CFO email failing DMARC/SPF authentication.\n"
        "* **`fake_email_lookalike_kaveri.eml`**: Typosquatted lookalike domain (`kaver1-enterprises.example`).\n\n"
        "### `4_SCAM_MESSAGES_AND_SCRIPTS/`\n"
        "* **`fake_digital_arrest_english.txt`**: CBI Officer Sharma digital arrest extortion message -> HOLD.\n"
        "* **`fake_digital_arrest_hinglish.txt`**: CBI digital arrest Hinglish phone script -> HOLD.\n"
        "* **`fake_courier_parcel_drugs.txt`**: Mumbai customs seized parcel extortion -> HOLD.\n"
        "* **`real_bank_otp_sms.txt`**: Genuine bank OTP alert control -> PASS.\n\n"
        "---\n\n"
        "## How to Test\n\n"
        "### Option A: Using the Satya Desktop Companion\n"
        "1. Launch Satya: `cd desktop && npm run dev` (or web mode `npm run dev:web`).\n"
        "2. Ensure backend is running: `make run`.\n"
        "3. Drag and drop any file from this folder directly onto the Satya mascot on your screen.\n"
        "4. Satya inspects the evidence and raises a bubble card with the verdict (HOLD / VERIFY / PASS) and reason.\n\n"
        "### Option B: Offline CLI Batch Scan (Judges' Demonstration)\n"
        "```bash\n"
        "uv run python scripts/satya.py scan /Users/shivendranarayantripathi/Desktop/SATYA_DEMO_KIT/1_VOICE_CALLS_AND_AUDIO\n"
        "uv run python scripts/satya.py scan /Users/shivendranarayantripathi/Desktop/SATYA_DEMO_KIT/3_INVOICES_AND_EMAILS\n"
        "uv run python scripts/satya.py scan /Users/shivendranarayantripathi/Desktop/SATYA_DEMO_KIT/4_SCAM_MESSAGES_AND_SCRIPTS\n"
        "```\n\n"
        "### Option C: Live Call Simulation\n"
        "```bash\n"
        "uv run python scripts/replay_live_media.py audio /Users/shivendranarayantripathi/Desktop/SATYA_DEMO_KIT/1_VOICE_CALLS_AND_AUDIO/fake_cfo_clone_indian_en.wav\n"
        "```\n",
        encoding="utf-8",
    )


def fix_macos_visibility(out: Path) -> None:
    """Ensure Finder displays every folder and file clearly without hidden BSD flags or xattrs."""
    if sys.platform == "darwin":
        subprocess.run(["chflags", "-R", "nohidden", str(out)], check=False)
        subprocess.run(["xattr", "-cr", str(out)], check=False)


def build(out: Path, *, skip_video: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    notes: dict[str, dict[str, object]] = {}
    print("1. Generating voice calls & audio …")
    notes.update(make_audio(out))
    print("2. Generating invoices & emails …")
    notes.update(make_documents(out))
    print("3. Generating scam scripts & texts …")
    notes.update(make_text(out))
    if not skip_video:
        print("4. Generating Google Meet executive deepfake videos …")
        notes.update(make_video(out))

    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "README.md"}:
            meta = notes.get(path.name, {})
            files.append(
                {
                    "path": str(path.relative_to(out)),
                    "sha256": _sha(path),
                    "bytes": path.stat().st_size,
                    **meta,
                }
            )

    (out / "manifest.json").write_text(
        json.dumps(
            {
                "generated_by": "scripts/make_testkit.py",
                "note": "Grand Finale Demo Kit. Fictional accounts & research media.",
                "files": files,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _readme(out)
    fix_macos_visibility(out)
    print(f"\nDemo kit successfully created at:\n  {out}")
    print(f"Total files: {len(files)}")


def verify(out: Path) -> int:
    if not out.exists():
        print(f"not built: {out}")
        return 2
    bad = 0
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size == 0:
            print(f"EMPTY {path.relative_to(out)}")
            bad += 1
        else:
            print(f"ok    {path.relative_to(out):55} {size:>10,} bytes")
    fix_macos_visibility(out)
    print("kit ready" if bad == 0 else f"{bad} empty file(s)")
    return 0 if bad == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        default=os.environ.get("SATYAPAN_TESTKIT", str(DEFAULT_OUT)),
        help=f"where to write the kit (default: {DEFAULT_OUT})",
    )
    parser.add_argument("--skip-video", action="store_true", help="skip video generation")
    parser.add_argument("--verify", action="store_true", help="only check an existing kit")
    args = parser.parse_args(argv)
    out = Path(args.out).expanduser().resolve()
    if args.verify:
        return verify(out)
    build(out, skip_video=args.skip_video)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
