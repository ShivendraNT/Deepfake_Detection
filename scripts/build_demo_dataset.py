"""Build the Satyapan Forensic Lab investigation dataset (the demo case and its ground truth).

    uv run python scripts/build_demo_dataset.py            # -> data/forensics/demo/
    uv run python scripts/build_demo_dataset.py --check    # verify files against manifest

Scenario: "Operation Pratibimb" — a 'digital arrest' extortion of a retired professor, built
only from (a) public-domain speech (LJSpeech), (b) consented sample media published for
deepfake research (UniData deepfake-videos sample, CC BY-NC-ND 4.0, copied unmodified), and
(c) exhibits we generate ourselves (Piper TTS voices, a synthetic call recording with mains
hum, a fictional notice and its forgery, an SD-Turbo portrait). No real person's likeness or
voice is cloned; every person in the scenario is fictional. Everything is labelled with how it
was made in manifest.json, which is the ground truth for the benchmark.

Needs internet once (Hugging Face) and: piper-tts, diffusers + torch (SD-Turbo), cryptography,
c2pa-python, invisible-watermark. Missing pieces are skipped and reported, never faked.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "forensics" / "demo"
DATA = Path(os.environ.get("SATYAPAN_DATA", str(ROOT.parent / "satyapan-data")))
WORK = DATA / "demo-build"
TTS = DATA / "tts"
VOICES = {
    "en_US-ljspeech-high": "en/en_US/ljspeech/high/en_US-ljspeech-high",
    "hi_IN-rohan-medium": "hi/hi_IN/rohan/medium/hi_IN-rohan-medium",
}
SEED = 20261021


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hf(repo: str, filename: str, kind: str = "dataset") -> Path:
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(repo, filename, repo_type=kind))


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def read_wav(p: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(p)) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    return (x.reshape(-1, ch).mean(axis=1) if ch > 1 else x), sr


def write_wav(p: Path, x: np.ndarray, sr: int) -> None:
    y = np.clip(x, -1, 1)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype(np.int16).tobytes())


def resample(x: np.ndarray, sr: int, to: int) -> np.ndarray:
    from scipy.signal import resample_poly

    g = np.gcd(sr, to)
    return resample_poly(x, to // g, sr // g).astype(np.float32)


# ------------------------------------------------------------------------------- voices
def piper(voice: str, text: str, out: Path, length_scale: float = 1.0) -> Path:
    from piper import PiperVoice, SynthesisConfig

    TTS.mkdir(parents=True, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        if not (TTS / f"{voice}{ext}").exists():
            shutil.copy(hf("rhasspy/piper-voices", VOICES[voice] + ext, kind="model"),
                        TTS / f"{voice}{ext}")  # fmt: skip
    v = PiperVoice.load(str(TTS / f"{voice}.onnx"))
    with wave.open(str(out), "wb") as w:
        v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=length_scale))
    return out


def ljspeech(ids: list[str]) -> list[tuple[np.ndarray, int]]:
    return [read_wav(hf("flexthink/ljspeech", f"wavs/{i}.wav")) for i in ids]


def to_whatsapp_voice_note(src: Path, dst: Path) -> None:
    """Mono Opus at 16 kHz in Ogg, as WhatsApp voice notes are."""
    ffmpeg("-i", str(src), "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k",
           "-application", "voip", "-map_metadata", "-1", str(dst))  # fmt: skip


# ------------------------------------------------------------------------------- ENF splice
def hum(n: int, sr: int, f0: float, rng: np.random.Generator, level: float) -> np.ndarray:
    """Mains hum whose frequency drifts like a real grid (random walk around f0)."""
    steps = n // sr + 2
    walk = np.cumsum(rng.normal(0, 0.0035, steps))
    walk = np.clip(walk - walk.mean(), -0.03, 0.03)
    f = f0 + np.interp(np.arange(n) / sr, np.arange(steps), walk)
    ph = 2 * np.pi * np.cumsum(f) / sr
    return level * (np.sin(ph) + 0.6 * np.sin(2 * ph + 0.3) + 0.25 * np.sin(3 * ph + 1.1))


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    w = rng.normal(0, 1, n)
    spec = np.fft.rfft(w)
    spec /= np.sqrt(np.arange(1, len(spec) + 1))
    y = np.fft.irfft(spec, n)
    return (y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def call_recording(out: Path, rng: np.random.Generator) -> dict:
    sr = 44100
    a = [resample(x, s, sr) for x, s in ljspeech(["LJ032-0040", "LJ032-0041", "LJ032-0042"])]
    b = [resample(x, s, sr) for x, s in ljspeech(["LJ045-0101", "LJ045-0102", "LJ045-0103"])]
    gap = np.zeros(int(0.6 * sr), np.float32)
    seg_a = np.concatenate(sum(([c * 0.55, gap] for c in a), []))
    seg_b = np.concatenate(sum(([c * 0.55, gap] for c in b), []))
    # Session A: recorded on 14 Oct (grid at 50.02 Hz, quiet room); session B: 21 Oct
    # (grid at 49.97 Hz, a fan running): two recordings joined into one file.
    seg_a = seg_a + hum(len(seg_a), sr, 50.02, rng, 0.006) + 0.0025 * pink(len(seg_a), rng)
    seg_b = seg_b + hum(len(seg_b), sr, 49.965, rng, 0.006) + 0.0105 * pink(len(seg_b), rng)
    x = np.concatenate([seg_a, seg_b])
    write_wav(out, x, sr)
    return {"splice_at_s": round(len(seg_a) / sr, 2), "sample_rate": sr,
            "enf_hz": [50.02, 49.965]}  # fmt: skip


# ------------------------------------------------------------------------------- documents
def font(size: int, bold: bool = False):
    from PIL import ImageFont

    f = (
        ROOT
        / "src/satyapan/forensics/report/fonts"
        / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    )
    return ImageFont.truetype(str(f), size)


def notice(name: str, amount: str, rng: np.random.Generator) -> tuple[np.ndarray, dict]:
    """A fictional agency notice, rendered like a photographed paper document. Returns the
    image and the boxes (x0, y0, x1, y1) of the addressee, the amount and the round stamp."""
    from PIL import Image, ImageDraw, ImageFilter

    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), (246, 243, 234))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, W - 60, 250], outline=(40, 52, 92), width=4)
    d.ellipse([90, 85, 230, 225], outline=(40, 52, 92), width=5)
    d.text((118, 132), "DFC", font=font(46, True), fill=(40, 52, 92))
    d.text((260, 95), "DIRECTORATE OF FINANCIAL CRIMES", font=font(44, True), fill=(30, 40, 80))
    d.text(
        (262, 155), "(FICTIONAL AGENCY — SATYAPAN DEMO EXHIBIT)", font=font(22), fill=(90, 90, 110)
    )
    d.text(
        (262, 192),
        "Mumbai Zonal Unit · Case Ref. DFC/MZU/2026/4471",
        font=font(24),
        fill=(60, 60, 80),
    )
    y = 300
    d.text((80, y), "NOTICE OF PRELIMINARY ENQUIRY", font=font(36, True), fill=(20, 20, 30))
    y += 80
    d.text((80, y), "To:", font=font(28, True), fill=(20, 20, 30))
    d.text((150, y), name, font=font(28), fill=(20, 20, 30))
    layout = {"to": (146, y - 6, W - 80, y + 42)}
    y += 60
    body = [
        "Your Aadhaar-linked account is under enquiry in connection with a parcel",
        "seized at Mumbai International Airport. You are directed to cooperate with",
        "the enquiry officer by video call and to keep this matter confidential.",
        "",
        "For verification of funds, the amount stated below is to be placed in the",
        "supervised account communicated by the enquiry officer. It will be returned",
        "after verification.",
    ]
    for line in body:
        d.text((80, y), line, font=font(26), fill=(25, 25, 35))
        y += 44
    y += 30
    label = "Amount for verification:"
    d.text((80, y), label, font=font(30, True), fill=(20, 20, 30))
    ax = 80 + int(font(30, True).getlength(label)) + 18
    d.text((ax, y), amount, font=font(30, True), fill=(120, 20, 20))
    layout["amount"] = (ax - 6, y - 6, W - 80, y + 46)
    y += 120
    d.text((80, y), "Issued under the authority of the Director.", font=font(24), fill=(40, 40, 50))
    # official round stamp + signature
    cx, cy = 900, y + 180
    for r, wdt in ((120, 6), (100, 3)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(52, 64, 160), width=wdt)
    d.text((cx - 78, cy - 22), "DFC · MZU", font=font(30, True), fill=(52, 64, 160))
    d.text((cx - 70, cy + 18), "VERIFIED", font=font(24, True), fill=(52, 64, 160))
    layout["stamp"] = (cx - 128, cy - 128, cx + 128, cy + 128)
    pts = [
        (700 + i * 9, cy + 150 + int(18 * np.sin(i / 2.2)) + int(rng.integers(-3, 4)))
        for i in range(40)
    ]
    d.line(pts, fill=(25, 25, 70), width=3)
    d.text((700, cy + 200), "Enquiry Officer", font=font(24), fill=(40, 40, 50))
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32)
    shade = np.linspace(1.0, 0.93, W)[None, :, None] * np.linspace(0.98, 1.0, H)[:, None, None]
    a = a * shade + rng.normal(0, 3.2, a.shape)
    return np.clip(a, 0, 255).astype(np.uint8), layout


def jpeg_bytes(arr: np.ndarray, q: int, **kw) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=q, **kw)
    return buf.getvalue()


def decode(b: bytes) -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).copy()


def forged_notice(
    template: np.ndarray, layout: dict, rng: np.random.Generator
) -> tuple[np.ndarray, dict]:
    """Forge the notice: the addressee and the amount are pasted in from a separately rendered
    and compressed copy (a splice), and the official stamp is cloned onto the left of the page
    with an ink mask, the way a forger lifts a seal (copy-move)."""
    img = template.copy()
    patch, _ = notice(
        "Shri Ramesh K. Mehta (Retd. Professor)", "₹ 4,50,000/-", np.random.default_rng(99)
    )
    patch = decode(jpeg_bytes(patch, 55))
    for key in ("to", "amount"):
        x0, y0, x1, y1 = layout[key]
        img[y0:y1, x0:x1] = patch[y0:y1, x0:x1]
    x0, y0, x1, y1 = layout["stamp"]
    stamp = img[y0:y1, x0:x1].astype(np.int16)
    ink = (stamp[..., 2] - stamp[..., 0] > 30) & (stamp.mean(axis=2) < 190)
    tx, ty = 160, y0 - 10
    target = img[ty : ty + (y1 - y0), tx : tx + (x1 - x0)]
    target[ink] = stamp[ink].astype(np.uint8)
    return img, {"spliced_regions": [list(layout["to"]), list(layout["amount"])],
                 "cloned_stamp": {"from": [x0, y0, x1, y1], "to": [tx, ty, tx + x1 - x0, ty + y1 - y0]}}  # fmt: skip


def whatsapp_image(arr: np.ndarray, out: Path, q: int = 80, long_side: int = 1600) -> None:
    from PIL import Image

    img = Image.fromarray(arr)
    img.thumbnail((long_side, long_side), Image.BICUBIC)
    img.save(out, format="JPEG", quality=q)


# ------------------------------------------------------------------------------- AI portrait
def sd_turbo_portrait(out_png: Path, seed: int) -> dict:
    import torch
    from diffusers import AutoPipelineForText2Image

    torch.set_num_threads(4)
    pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", variant="fp16",
                                                     torch_dtype=torch.float32)  # fmt: skip
    prompt = (
        "passport style studio portrait photograph of a stern middle-aged Indian man in a "
        "khaki police uniform, plain light grey background, sharp focus, 50mm photo"
    )
    g = torch.Generator().manual_seed(seed)
    img = pipe(prompt=prompt, num_inference_steps=2, guidance_scale=0.0, height=512, width=512,
               generator=g).images[0]  # fmt: skip
    # Stability AI's SD 2.x reference scripts mark every output with invisible-watermark "SDV2".
    from imwatermark import WatermarkEncoder

    bgr = np.asarray(img)[..., ::-1]
    enc = WatermarkEncoder()
    enc.set_watermark("bytes", b"SDV2")
    marked = enc.encode(np.ascontiguousarray(bgr), "dwtDct")[..., ::-1]
    from PIL import Image

    Image.fromarray(np.ascontiguousarray(marked)).save(out_png, format="PNG")
    return {"generator": f"SD-Turbo (stabilityai/sd-turbo), 2 steps, seed {seed}",
            "prompt": prompt, "watermark": "invisible-watermark dwtDct 'SDV2'"}  # fmt: skip


def test_ca(work: Path) -> tuple[bytes, bytes]:
    """A throw-away test CA + signing certificate for the demo Content Credentials."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.now(UTC) - timedelta(days=1)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Satyapan Demo Test Root CA"),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Satyapan Demo (test only)")])  # fmt: skip
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now).not_valid_after(now + timedelta(days=3650))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                       content_commitment=False, key_encipherment=False,
                                       data_encipherment=False, key_agreement=False,
                                       encipher_only=False, decipher_only=False), critical=True)
          .sign(ca_key, hashes.SHA256()))  # fmt: skip
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Demo GenAI Image Service"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Satyapan Demo (test only)")])  # fmt: skip
    leaf = (x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=False, crl_sign=False,
                                         content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                           critical=False)
            .sign(ca_key, hashes.SHA256()))  # fmt: skip
    chain = leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(
        serialization.Encoding.PEM
    )
    pk = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption())  # fmt: skip
    return chain, pk


def c2pa_sign(src: Path, dst: Path, work: Path) -> dict:
    import c2pa

    chain, pk = test_ca(work)
    manifest = {
        "claim_generator_info": [{"name": "Demo GenAI Image Service", "version": "1.0"}],
        "title": src.name,
        "format": "image/png",
        "assertions": [{"label": "c2pa.actions", "data": {"actions": [{
            "action": "c2pa.created",
            "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
            "softwareAgent": {"name": "SD-Turbo text-to-image"}}]}}],
    }  # fmt: skip
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, chain, pk, None)
    signer = c2pa.Signer.from_info(info)
    builder = c2pa.Builder(manifest)
    with open(src, "rb") as s, open(dst, "wb") as d:
        builder.sign(signer, "image/png", s, d)
    return {"c2pa": "c2pa.created / trainedAlgorithmicMedia, signed by a throw-away demo CA"}


# ------------------------------------------------------------------------------- main
SCENARIO = {
    "id": "case_demo_pratibimb",
    "title": "Operation Pratibimb — 'digital arrest' extortion of a retired professor",
    "fir_number": "FIR No. 0457/2026",
    "police_station": "Cyber Crime Police Station (demo)",
    "district": "South-West District, New Delhi",
    "state": "Delhi",
    "offence_sections": "BNS 2023 §§ 308(2), 318(4), 319(2), 204, 351, 336(3), 340(2), 61(2); IT Act 2000 §§ 66C, 66D",
    "investigating_officer": "Insp. Kavita Rao (fictional)",
    "examiner": "Scientific Officer (Cyber Forensics)",
    "lab_name": "Satyapan Multimedia Forensic Lab",
    "summary": (
        "On 21-10-2026 the complainant, a 68-year-old retired professor (fictional), received a "
        "WhatsApp video call from a man posing as an enquiry officer, a 'notice' threatening "
        "arrest, an 'officer ID' photo, and voice notes in his daughter's voice and in Hindi "
        "pleading for money. He transferred ₹4,50,000. The exhibits below were extracted from "
        "his phone and the suspect's seized laptop and sent for authentication, deepfake "
        "detection and source attribution."
    ),
}


NOTES = (
    "Ground truth for every exhibit. The scenario and its people are fictional. Media of real "
    "people come only from public research datasets: UniData's consented participants (the face "
    "swap is UniData's own sample) and LJSpeech (public domain); the 'daughter' voice note uses "
    "the public Piper voice trained on LJSpeech. These media are built locally by "
    "`make demo-dataset` and are never committed (AGENTS.md data hygiene)."
)


def build(args: argparse.Namespace) -> None:
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []

    def add(fname: str, role: str, truth: str, received_from: str, description: str, made: str,
            license_: str, **extra: object) -> None:  # fmt: skip
        p = OUT / fname
        items.append({"file": fname, "role": role, "ground_truth": truth,
                      "received_from": received_from, "description": description,
                      "how_made": made, "license": license_, "sha256": sha256(p),
                      "bytes": p.stat().st_size, **extra})  # fmt: skip
        print(f"  {fname:42s} {truth:12s} {p.stat().st_size / 1024:8.0f} KB", flush=True)

    print("1/7 deepfake video call + its sources (UniData sample, unmodified)")
    try:
        for src, dst in (("deepfake/1.mp4", "VID-20261021-WA0003.mp4"),
                         ("video/1.mp4", "laptop_seized_clip_0193.mp4"),
                         ("image/1.jpg", "profile_photo_source.jpg")):  # fmt: skip
            shutil.copy(hf("UniDataPro/deepfake-videos-dataset", src), OUT / dst)
        lic = (
            "UniData deepfake-videos-dataset sample, CC BY-NC-ND 4.0 (consented; copied unmodified)"
        )
        add("VID-20261021-WA0003.mp4", "questioned", "synthetic", "Complainant's phone (WhatsApp)",
            "Screen recording of the WhatsApp video call with the 'enquiry officer'.",
            "Real phone video with an AI-generated face overlaid by an online face-swap service "
            "(UniData sample deepfake/1.mp4).", lic)  # fmt: skip
        add("laptop_seized_clip_0193.mp4", "reference", "authentic", "Suspect's seized laptop",
            "Video clip recovered from the suspect's laptop.",
            "The genuine phone recording the deepfake was made from (UniData video/1.mp4).", lic)  # fmt: skip
        add("profile_photo_source.jpg", "reference", "authentic", "Open-source collection",
            "Profile photo found on a social-media account used by the suspects.",
            "The face image used for the swap (UniData image/1.jpg).", lic)  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        print("  SKIPPED (download failed):", exc)

    print("2/7 voice clone of the daughter + her genuine voice")
    ref = ljspeech(["LJ001-0001", "LJ001-0002", "LJ001-0003", "LJ001-0004"])
    sr = ref[0][1]
    # One continuous recording: clips joined with natural pauses over a steady room-noise floor
    # (no digital silence), as a phone recording of someone reading aloud would be.
    gap = np.zeros(int(0.45 * sr), np.float32)
    body = np.concatenate(sum(([x, gap] for x, _ in ref), []))
    room = 0.0018 * pink(len(body), np.random.default_rng(3))
    write_wav(WORK / "ref.wav", body * 0.9 + room, sr)
    ffmpeg(
        "-i",
        str(WORK / "ref.wav"),
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        str(OUT / "daughter_known_voice_sample.m4a"),
    )
    add("daughter_known_voice_sample.m4a", "reference", "authentic", "Collected by IO with consent",
        "Known voice sample of the complainant's daughter (control sample for speaker comparison).",
        "Genuine human speech: LJSpeech public-domain recordings LJ001-0001..0004.",
        "LJSpeech 1.1, public domain")  # fmt: skip
    piper("en_US-ljspeech-high", "Papa, it's me. Please listen, I don't have much time. The police "
          "have stopped me at the airport, they found a parcel in my name. The officer says if you "
          "transfer the money today to the supervised account, they will let me go. Please don't "
          "tell Mummy or anyone else, they said it will make things worse. Please, Papa, hurry.",
          WORK / "clone.wav")  # fmt: skip
    to_whatsapp_voice_note(WORK / "clone.wav", OUT / "PTT-20261021-WA0007.opus")
    add("PTT-20261021-WA0007.opus", "questioned", "synthetic", "Complainant's phone (WhatsApp)",
        "Voice note that appears to be from the complainant's daughter.",
        "Piper TTS voice en_US-ljspeech-high (a neural TTS trained on the same speaker as the known "
        "sample, i.e. a voice clone), encoded as a WhatsApp-style Opus voice note.",
        "Generated for this dataset (Piper MIT; LJSpeech public domain)")  # fmt: skip

    print("3/7 Hindi synthetic voice note")
    piper("hi_IN-rohan-medium", "हेलो सर, मैं सीबीआई मुंबई से बोल रहा हूँ। आपके आधार कार्ड से जुड़ा एक "
          "पार्सल पकड़ा गया है जिसमें ड्रग्स मिले हैं। आप डिजिटल अरेस्ट में हैं। किसी को मत बताइए और "
          "जाँच के लिए चार लाख पचास हज़ार रुपये सेफ अकाउंट में ट्रांसफर कीजिए, ओटीपी भी शेयर कीजिए।",
          WORK / "hindi.wav")  # fmt: skip
    to_whatsapp_voice_note(WORK / "hindi.wav", OUT / "PTT-20261021-WA0009.opus")
    add("PTT-20261021-WA0009.opus", "questioned", "synthetic", "Complainant's phone (WhatsApp)",
        "Hindi voice note from the 'CBI officer' announcing a 'digital arrest'.",
        "Piper TTS voice hi_IN-rohan-medium (synthetic Hindi speech), WhatsApp-style Opus.",
        "Generated for this dataset (Piper MIT)")  # fmt: skip

    print("4/7 call recording joined from two sessions (ENF + noise-floor discontinuity)")
    meta = call_recording(OUT / "call_recording_20261021_1412.wav", rng)
    add("call_recording_20261021_1412.wav", "questioned", "manipulated", "Submitted by the accused's counsel",
        "Recording of a phone call produced by the accused, in which the daughter appears to "
        "ask her father to transfer the money (to argue the payment was a family matter).",
        f"Genuine speech of the same speaker as the known sample (LJSpeech) from two recording "
        f"sessions with different mains-hum frequencies and background noise, joined at "
        f"{meta['splice_at_s']} s.",
        "Generated for this dataset (LJSpeech public domain)", truth_detail=meta)  # fmt: skip

    print("5/7 notice: genuine template and the forged copy")
    template, layout = notice(
        "________________________________", "₹ ________________", np.random.default_rng(7)
    )
    (OUT / "notice_template_from_laptop.jpg").write_bytes(jpeg_bytes(template, 92))
    add("notice_template_from_laptop.jpg", "reference", "authentic", "Suspect's seized laptop",
        "Blank notice template recovered from the suspect's laptop.",
        "Rendered for this dataset (fictional agency), saved once at JPEG quality 92.",
        "Generated for this dataset")  # fmt: skip
    forged, fmeta = forged_notice(
        decode((OUT / "notice_template_from_laptop.jpg").read_bytes()), layout, rng
    )
    whatsapp_image(forged, OUT / "IMG-20261021-WA0011.jpg", q=82, long_side=1600)
    add("IMG-20261021-WA0011.jpg", "questioned", "manipulated", "Complainant's phone (WhatsApp)",
        "'Notice of preliminary enquiry' sent to the complainant.",
        "The template with the addressee and amount pasted in from a separately compressed render "
        "(splice) and the round stamp lifted and cloned onto the left of the page (copy-move); resized to 1600 px and "
        "re-compressed like a WhatsApp image.", "Generated for this dataset", truth_detail=fmeta)  # fmt: skip

    print(
        "6/7 'officer ID' portrait generated by SD-Turbo (+ Content Credentials) and a re-shared copy"
    )
    try:
        signed = OUT / "officer_id_photo_original.png"
        old_m = OUT / "manifest.json"
        gen = {}
        if old_m.exists():
            gen = next((it.get("truth_detail") or {} for it in json.loads(old_m.read_text())["items"]
                        if it["file"] == signed.name), {})  # fmt: skip
        if signed.exists() and not args.resign:
            # The committed, signed original is kept byte for byte (its hash is in the
            # manifest); its pixels are the SD-Turbo output, so the re-shared copy is rebuilt.
            from PIL import Image as _Image

            _Image.open(signed).convert("RGB").save(WORK / "portrait.png")
        elif (WORK / "portrait.png").exists():  # made by scripts/make_ai_portrait.py (own env)
            meta_p = WORK / "portrait.png.json"
            gen = json.loads(meta_p.read_text()) if meta_p.exists() else {}
        else:
            gen = sd_turbo_portrait(WORK / "portrait.png", SEED)
        if not signed.exists() or args.resign:
            try:
                gen.update(c2pa_sign(WORK / "portrait.png", signed, WORK))
            except Exception as exc:  # noqa: BLE001
                print("  C2PA signing failed, keeping the unsigned file:", exc)
                shutil.copy(WORK / "portrait.png", signed)
        add("officer_id_photo_original.png", "questioned", "synthetic", "Telegram (sent as file)",
            "'Officer ID card' photo, original file sent on Telegram.",
            "SD-Turbo text-to-image (2 steps), signed C2PA manifest declaring "
            "trainedAlgorithmicMedia (test CA, not on a trust list). Stability's reference "
            "invisible watermark was applied, but on this flat-background portrait neither the "
            "reference decoder nor Satyapan's can read it back: watermarks are fragile.",
            "Generated for this dataset", truth_detail=gen)  # fmt: skip
        from PIL import Image

        im = Image.open(WORK / "portrait.png").convert("RGB")
        im = im.crop((18, 10, 500, 492)).resize((400, 400), Image.BICUBIC)
        im.save(OUT / "IMG-20261021-WA0012.jpg", format="JPEG", quality=72)
        add("IMG-20261021-WA0012.jpg", "questioned", "synthetic", "Complainant's phone (WhatsApp)",
            "Same 'officer' photo as received on WhatsApp.",
            "The SD-Turbo portrait cropped, resized to 400 px and re-compressed (watermark and "
            "Content Credentials lost).", "Generated for this dataset")  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        print("  SKIPPED (SD-Turbo unavailable):", exc)

    print("7/7 manifest + scenario")
    manifest = {"name": "Satyapan Forensic Lab investigation dataset v1", "built_at": datetime.now(UTC).isoformat(),
                "scenario": SCENARIO, "items": items,
                "notes": NOTES}  # fmt: skip
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(f"wrote {len(items)} exhibits to {OUT}")


def check() -> int:
    m = json.loads((OUT / "manifest.json").read_text())
    bad = 0
    for it in m["items"]:
        p = OUT / it["file"]
        ok = p.exists() and sha256(p) == it["sha256"]
        bad += not ok
        print(("ok  " if ok else "BAD ") + it["file"])
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument(
        "--resign",
        action="store_true",
        help="regenerate and re-sign the officer portrait (needs scripts/make_ai_portrait.py)",
    )
    a = ap.parse_args()
    raise SystemExit(check() if a.check else build(a) or 0)
