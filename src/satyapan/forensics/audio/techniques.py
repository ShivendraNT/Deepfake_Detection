"""Audio forensic techniques (also run on the audio track of a video)."""

from __future__ import annotations

import re
from typing import Any

import numpy as np

from satyapan.forensics.audio import dsp
from satyapan.forensics.base import (
    NotApplicable,
    Technique,
    Unavailable,
    finding,
    info,
    make_result,
)
from satyapan.forensics.context import AnalysisContext, colormap
from satyapan.forensics.models import (
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Status,
    Strength,
    TechniqueResult,
    TimeSpan,
)
from satyapan.forensics.probe import all_tags, ffprobe, streams

AV = (MediaKind.AUDIO, MediaKind.VIDEO)
AUD = (MediaKind.AUDIO,)


def probe_info(ctx: AnalysisContext) -> dict[str, Any]:
    if "probe" not in ctx.cache:
        path = ctx.cache.get("path")
        ctx.cache["probe"] = ffprobe(data=None if path else ctx.data, path=path)
    return ctx.cache["probe"]  # type: ignore[no-any-return]


def x16(ctx: AnalysisContext) -> np.ndarray:
    try:
        return ctx.audio(16000)
    except ValueError as exc:
        raise NotApplicable(f"no audio stream ({exc})") from exc


def has_audio(ctx: AnalysisContext) -> bool:
    try:
        return bool(streams(probe_info(ctx), "audio"))
    except ValueError:
        return ctx.media.kind == MediaKind.AUDIO


# ---------------------------------------------------------------------------------------------
# Container metadata
# ---------------------------------------------------------------------------------------------

TTS_HINTS = [
    (r"elevenlabs", "ElevenLabs"), (r"\bplay\.ht\b|playht", "PlayHT"), (r"resemble", "Resemble AI"),
    (r"murf", "Murf"), (r"speechify", "Speechify"), (r"coqui|xtts", "Coqui XTTS"),
    (r"piper", "Piper TTS"), (r"bark", "Suno Bark"), (r"tortoise", "Tortoise TTS"),
    (r"rvc|so-vits|sovits", "RVC / so-vits voice conversion"), (r"vall-?e", "VALL-E"),
    (r"openai|tts-1", "OpenAI TTS"), (r"polly", "Amazon Polly"), (r"wavenet|google tts", "Google TTS"),
    (r"azure|microsoft speech", "Azure Speech"),
]  # fmt: skip


def run_audio_container(ctx: AnalysisContext) -> TechniqueResult:
    t = AUDIO_CONTAINER
    info_ = probe_info(ctx)
    fmt = info_.get("format", {})
    aud = streams(info_, "audio")
    tags = all_tags(info_)
    findings: list[Finding] = []
    if not aud:
        return make_result(t, summary="no audio stream", status=Status.SKIPPED)
    a = aud[0]
    data = {
        "container": fmt.get("format_long_name") or fmt.get("format_name"),
        "duration_s": round(float(fmt.get("duration") or 0), 3),
        "bit_rate": fmt.get("bit_rate"),
        "codec": a.get("codec_long_name") or a.get("codec_name"),
        "sample_rate": a.get("sample_rate"), "channels": a.get("channels"),
        "channel_layout": a.get("channel_layout"), "sample_fmt": a.get("sample_fmt"),
        "bits_per_sample": a.get("bits_per_raw_sample") or a.get("bits_per_sample"),
        "tags": tags,
    }  # fmt: skip
    enc = " ".join(v for k, v in tags.items() if "encoder" in k.lower() or "software" in k.lower())
    blob = " ".join(f"{k}={v}" for k, v in tags.items() if any(
        w in k.lower() for w in ("encoder", "software", "comment", "title", "artist", "tool")))  # fmt: skip
    for pat, name in TTS_HINTS:
        if re.search(rf"\b(?:{pat})\b", blob, re.I):
            findings.append(
                finding(
                    "TTS_SIGNATURE",
                    f"Metadata names a speech-synthesis tool: {name}",
                    "A tag or the file name mentions a text-to-speech or voice-conversion "
                    f"tool ({name}). Tools that create synthetic voices often leave their "
                    "name in metadata; it can also be added by hand, so verify.",
                    Hypothesis.SYNTHETIC,
                    Strength.WEAK,
                    Category.PROVENANCE,
                    tool=name,
                )  # fmt: skip
            )
            break
    if enc:
        lib = "FFmpeg (libavformat)" if "lavf" in enc.lower() or "lavc" in enc.lower() else enc[:60]
        findings.append(
            info(
                "ENCODER_TAG",
                f"Written by {lib}",
                f"Encoder tag “{enc[:120]}”. FFmpeg writes this when it converts or edits a file; "
                "phones' voice recorders and messaging apps usually write their own.",
                Category.PROVENANCE,
                encoder=enc[:200],
            )  # fmt: skip
        )
    base = (ctx.filename or "").rsplit("/", 1)[-1]
    codec = str(a.get("codec_name", ""))
    if re.match(r"^PTT-\d{8}-WA\d{3,5}", base) or re.match(r"^WhatsApp (Ptt|Audio) ", base):
        findings.append(info("PLATFORM_TRACE", "Platform trace: WhatsApp voice note",
                             f"File name “{base}” follows WhatsApp's voice-note naming.",
                             Category.PROVENANCE, platform="WhatsApp"))  # fmt: skip
    elif codec == "opus" and str(a.get("channels")) == "1" and fmt.get("format_name") == "ogg":
        findings.append(info("PLATFORM_TRACE", "Consistent with a messaging-app voice note",
                             "Mono Opus in an Ogg container is the format WhatsApp and Telegram "
                             "use for voice notes.", Category.PROVENANCE, platform="voice note"))  # fmt: skip
    if tags.get("creation_time"):
        findings.append(info("CREATION_TIME", f"Container creation time {tags['creation_time']}",
                             "Recorded by the writing software; clocks and tags can be wrong or "
                             "edited.", Category.METADATA, creation_time=tags["creation_time"]))  # fmt: skip
    summary = f"{data['codec']} {a.get('sample_rate')} Hz, {a.get('channels')} ch, {data['duration_s']:.1f} s"
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Spectrogram and bandwidth (transcoding history)
# ---------------------------------------------------------------------------------------------


def run_spectral(ctx: AnalysisContext) -> TechniqueResult:
    t = SPECTRAL
    x, sr = ctx.audio_native()
    if len(x) < sr * 0.5:
        return make_result(t, summary="audio shorter than 0.5 s", status=Status.SKIPPED)
    n_fft = 2048 if sr > 24000 else 1024
    p, freqs, times = dsp.stft_power(x, sr, n_fft, max_frames=1400)
    db = 10 * np.log10(p + 1e-12)
    top = float(np.percentile(db, 99.5))
    img = np.clip((db - (top - 85)) / 85.0, 0, 1)[::-1]
    import cv2

    img = cv2.resize(img.astype(np.float32), (min(1400, max(400, img.shape[1])), 360),
                     interpolation=cv2.INTER_AREA)  # fmt: skip
    art = ctx.save_png("spectrogram", colormap(img, "magma"), "spectrogram", "Spectrogram",
                       f"0–{sr / 2000:.1f} kHz (bottom to top) over {len(x) / sr:.1f} s.")  # fmt: skip
    bw = dsp.effective_bandwidth(x, sr)
    findings: list[Finding] = []
    data = {"sample_rate": sr, "duration_s": round(len(x) / sr, 3), "max_hz": sr / 2,
            "cutoff_hz": round(bw.cutoff_hz, 1), "sharp_cutoff": bw.sharp,
            "drop_db": round(bw.drop_db, 1), "ltas_db": bw.ltas_db, "ltas_hz": bw.ltas_hz}  # fmt: skip
    if bw.sharp and bw.ratio < 0.92:
        meaning = dsp.explain_cutoff(bw.cutoff_hz, sr)
        findings.append(
            info(
                "BANDWIDTH_LIMIT",
                f"Content stops at {bw.cutoff_hz / 1000:.1f} kHz (file allows {sr / 2000:.1f} kHz)",
                f"The spectrum ends in a sharp wall ({bw.drop_db:.0f} dB drop) well below "
                f"what a {sr} Hz file can hold. This is typical of {meaning}, later saved at "
                f"{sr} Hz. It tells the audio's history (re-encoded or up-sampled), not "
                "whether the speech is genuine.",
                Category.PROVENANCE,
                cutoff_hz=round(bw.cutoff_hz),
                meaning=meaning,
            )  # fmt: skip
        )
        summary = f"band-limited to {bw.cutoff_hz / 1000:.1f} kHz ({meaning})"
    else:
        summary = f"content reaches {bw.cutoff_hz / 1000:.1f} kHz of {sr / 2000:.1f} kHz"
    return make_result(t, summary=summary, findings=findings, data=data, artifacts=[art])


# ---------------------------------------------------------------------------------------------
# Synthetic / cloned voice
# ---------------------------------------------------------------------------------------------


def score_with_features(det: Any, windows: list[np.ndarray]) -> tuple[list[float], np.ndarray]:
    """One XLS-R pass per window: the shipped head's P(synthetic) and the pooled features
    (shared with the open-TTS head)."""
    sess = det.model_session
    inp = sess.get_inputs()[0].name
    lr = det.logreg_session
    lr_in = lr.get_inputs()[0].name
    probs, feats = [], []
    for w in windows:
        hs = sess.run(None, {inp: np.asarray(w, np.float32)[None, :]})[0]
        pooled = hs.mean(axis=1).astype(np.float32)
        out = lr.run(None, {lr_in: pooled})
        p = 0.0
        for item in out:
            if isinstance(item, np.ndarray) and item.shape[-1] == 2:
                p = float(item[0, 1])
                break
        probs.append(float(np.clip(p, 0.0, 1.0)))
        feats.append(pooled[0])
    return probs, np.stack(feats) if feats else np.zeros((0, 1024), np.float32)


class OpenTtsHead:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.mean = np.asarray(raw["mean"], np.float64)
        self.scale = np.asarray(raw["scale"], np.float64)
        self.coef = np.asarray(raw["coef"], np.float64)
        self.intercept = float(raw["intercept"])
        self.tau_hi, self.tau_lo = float(raw["tau_hi"]), float(raw["tau_lo"])
        self.metrics: dict[str, float] = dict(raw.get("metrics", {}))

    def logits(self, feats: np.ndarray) -> np.ndarray:
        if len(feats) == 0:
            return np.zeros(0)
        return ((feats - self.mean) / self.scale) @ self.coef + self.intercept


_HEAD: list[OpenTtsHead | None] = []


def opentts_head() -> OpenTtsHead | None:
    """config/voice_opentts_head.json, only if it passed its pre-registered ship rule."""
    if not _HEAD:
        import json
        from pathlib import Path

        p = Path(__file__).resolve().parents[4] / "config" / "voice_opentts_head.json"
        head = None
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            head = OpenTtsHead(raw) if raw.get("ships") else None
        _HEAD.append(head)
    return _HEAD[0]


def run_voice(ctx: AnalysisContext) -> TechniqueResult:
    t = VOICE
    try:
        m = ctx.models.get("voice")
    except Unavailable as exc:
        return make_result(t, summary=str(exc), status=Status.UNAVAILABLE)
    from satyapan.contracts.enums import VoiceLabel
    from satyapan.voice.audio_io import split_windows
    from satyapan.voice.rules import classify_windows

    x = x16(ctx)
    segs = dsp.speech_segments(x)
    sp = float(sum(e - s for s, e in segs))
    thr = m["thresholds"]
    if sp < 3.0:
        return make_result(t, summary=f"only {sp:.1f} s of speech: too short to judge",
                           status=Status.SKIPPED, data={"speech_seconds": sp})  # fmt: skip
    all_windows = split_windows(x)

    def speech_in(i: int) -> float:
        a, b = i * 5.0, (i + 1) * 5.0
        return sum(max(0.0, min(b, e) - max(a, s)) for s, e in segs)

    keep = [i for i in range(len(all_windows)) if speech_in(i) >= 1.5]
    if not keep:
        return make_result(t, summary="no 5-second window has enough speech to judge",
                           status=Status.SKIPPED, data={"speech_seconds": sp})  # fmt: skip
    windows = [all_windows[i] for i in keep]
    with ctx.models.lock("voice_run"):
        scores, pooled = score_with_features(m["detector"], windows)
    verdict = classify_windows(scores, thr, sp)
    head = opentts_head()
    head_scores = [float(v) for v in head.logits(pooled)] if head is not None else []
    spans = [TimeSpan(start_s=keep[j] * 5.0, end_s=min(len(x) / 16000, (keep[j] + 1) * 5.0),
                      label="synthetic" if s >= thr.tau_hi else "elevated", score=round(s, 3))
             for j, s in enumerate(scores) if s >= thr.tau_lo]  # fmt: skip
    data = {"window_s": 5.0, "scores": [round(float(s), 4) for s in scores],
            "window_starts": [keep[j] * 5.0 for j in range(len(scores))],
            "speech_segments": [[round(s, 2), round(e, 2)] for s, e in segs][:200],
            "tau_hi": thr.tau_hi, "tau_lo": thr.tau_lo, "speech_seconds": round(sp, 1),
            "label": str(verdict.label), "model": thr.model_version,
            "benchmark": "In-the-Wild deepfake audio (speakers unseen): AUC 0.921"}  # fmt: skip
    findings: list[Finding] = []
    hi = sum(1 for s in scores if s >= thr.tau_hi)
    if verdict.label == VoiceLabel.LIKELY_SYNTHETIC:
        findings.append(
            finding(
                "SYNTHETIC_VOICE",
                f"Synthetic voice: {hi} of {len(scores)} windows above the strict threshold",
                f"The XLS-R deepfake-speech model scores {verdict.max_consecutive_over_hi} "
                f"consecutive 5-second windows above its strict threshold ({thr.tau_hi:.2f}, "
                "1% false alarms on genuine speech from unseen speakers). Neural "
                "text-to-speech and voice-conversion systems leave these traces in the "
                "signal even when the voice sounds natural.",
                Hypothesis.SYNTHETIC,
                Strength.STRONG,
                Category.SYNTHETIC,
                score=round(max(scores), 4),
                spans=spans,
                windows=len(scores),
            )  # fmt: skip
        )
    elif hi >= 1 or any(s >= thr.tau_lo for s in scores):
        n_lo = sum(1 for s in scores if s >= thr.tau_lo)
        findings.append(
            finding(
                "SYNTHETIC_VOICE",
                f"Voice partly suspicious: {n_lo} of {len(scores)} windows elevated",
                "Some windows score above the lenient threshold (5% false alarms) but the "
                "strict rule (two consecutive windows above 1%) is not met. A partly "
                "synthetic recording (real speech with inserted synthetic words) also "
                "looks like this; compare with the splice analysis.",
                Hypothesis.SYNTHETIC,
                Strength.MODERATE if hi else Strength.WEAK,
                Category.SYNTHETIC,
                score=round(max(scores), 4),
                spans=spans,
            )  # fmt: skip
        )
    if head is not None and head_scores:
        data["opentts_scores"] = [round(v, 3) for v in head_scores]
        data["opentts_tau_hi"], data["opentts_tau_lo"] = head.tau_hi, head.tau_lo
        data["opentts_metrics"] = head.metrics
        h_hi = [v >= head.tau_hi for v in head_scores]
        run = max((len(r) for r in "".join("1" if b else "0" for b in h_hi).split("0")), default=0)
        strong = run >= 2 or (len(head_scores) == 1 and h_hi[0])
        n_lo2 = sum(v >= head.tau_lo for v in head_scores)
        if strong or n_lo2:
            hspans = [TimeSpan(start_s=keep[j] * 5.0, end_s=min(len(x) / 16000, (keep[j] + 1) * 5.0),
                               label="open-TTS", score=round(v, 3))
                      for j, v in enumerate(head_scores) if v >= head.tau_lo]  # fmt: skip
            findings.append(
                finding(
                    "OPEN_TTS_VOICE",
                    "Open-source neural TTS signature" if strong else "Weak open-TTS signature",
                    "Satyapan's open-TTS head (trained on Piper/VITS voices and real English + "
                    "Hindi speech; tested on voices and speakers it never saw: AUC "
                    f"{head.metrics.get('test_auc', 0):.2f}) scores "
                    f"{sum(h_hi)} of {len(head_scores)} speech windows above its strict threshold "
                    f"({head.metrics.get('test_real_flagged_tau_hi', 0):.1%} of genuine test clips "
                    "exceed it). The voice carries the vocoder traces of the freely available "
                    "neural TTS family used to clone voices offline.",
                    Hypothesis.SYNTHETIC,
                    Strength.STRONG
                    if strong
                    else (Strength.MODERATE if n_lo2 >= 2 else Strength.WEAK),
                    Category.SYNTHETIC,
                    score=round(max(head_scores), 3),
                    spans=hspans,
                )  # fmt: skip
            )
    summary = (f"max synthetic score {max(scores):.2f} over {len(scores)} windows "
               f"({verdict.label})")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Splices and edits
# ---------------------------------------------------------------------------------------------


def run_splice(ctx: AnalysisContext) -> TechniqueResult:
    t = SPLICE
    x, sr = ctx.audio_native()
    if len(x) < sr * 2:
        return make_result(t, summary="audio shorter than 2 s", status=Status.SKIPPED)
    cues = dsp.digital_silence(x, sr)
    jumps, lt, levels = dsp.noise_floor_jumps(x, sr)
    cues += jumps
    cues += dsp.discontinuities(x, sr)
    groups = dsp.merge_cues(cues, within_s=1.0)
    # ENF is its own technique; a coinciding mains-hum jump is noted, never counted twice.
    for g in groups:
        for j in ctx.cache.get("enf_jumps", []):
            if abs(float(j["t"]) - float(g["t"])) <= 1.5:
                g["details"].append(f"coincides with a mains-hum jump at {float(j['t']):.1f} s")
                break
    data = {"cues": groups, "noise_floor_t": lt, "noise_floor_db": levels,
            "duration_s": round(len(x) / sr, 2)}  # fmt: skip
    findings: list[Finding] = []
    strong = [g for g in groups if g["weight"] >= 2.0 or len(set(g["kinds"])) >= 2]
    weak = [g for g in groups if g not in strong and g["weight"] >= 1.0]
    if strong or weak:
        sel = strong or weak
        spans = [TimeSpan(start_s=max(0.0, g["t"] - 0.3), end_s=g["t"] + 0.3,
                          label=", ".join(sorted(set(g["kinds"]))), score=round(g["weight"], 2))
                 for g in sel[:12]]  # fmt: skip
        detail = "; ".join(f"{g['t']:.1f} s: {', '.join(g['details'])}" for g in sel[:5])
        findings.append(
            finding(
                "AUDIO_SPLICE",
                f"{len(sel)} possible edit point(s)",
                "The recording changes abruptly at these points: " + detail + ". A single "
                "continuous recording keeps a steady background and no inserted digital "
                "silence; joins of separately recorded or generated pieces do not.",
                Hypothesis.MANIPULATED,
                Strength.MODERATE if strong else Strength.WEAK,
                Category.TAMPERING,
                spans=spans,
                points=len(sel),
            )  # fmt: skip
        )
        summary = f"{len(sel)} possible edit point(s)"
    else:
        summary = "no abrupt changes in background, silence or waveform continuity"
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Electrical Network Frequency
# ---------------------------------------------------------------------------------------------


def run_enf(ctx: AnalysisContext) -> TechniqueResult:
    t = ENF
    x = x16(ctx)
    if len(x) < 16000 * 8:
        return make_result(t, summary="needs at least 8 s of audio", status=Status.SKIPPED)
    res = dsp.enf_trace(x)
    data = {"present": res.present, "harmonic_hz": 50 * res.harmonic, "snr_db": round(res.snr_db, 1),
            "times": [round(v, 2) for v in res.times], "freqs": [round(v, 4) for v in res.freqs],
            "jumps": res.jumps, "nominal_hz": 50.0}  # fmt: skip
    findings: list[Finding] = []
    if not res.present:
        return make_result(t, summary=f"no mains hum found (SNR {res.snr_db:.1f} dB): not applicable",
                           status=Status.SKIPPED, data=data)  # fmt: skip
    ctx.cache["enf_jumps"] = res.jumps
    if res.jumps:
        spans = [TimeSpan(start_s=max(0.0, j["t"] - 1), end_s=j["t"] + 1, label="ENF jump",
                          score=round(abs(j["delta_hz"]), 4)) for j in res.jumps[:10]]  # fmt: skip
        findings.append(
            finding(
                "ENF_DISCONTINUITY",
                (
                    f"Mains-frequency trace breaks at {res.jumps[0]['t']:.1f} s"
                    if len(res.jumps) == 1
                    else f"Mains-frequency trace breaks at {len(res.jumps)} points"
                ),
                "The 50 Hz power-grid hum captured in the recording drifts slowly and "
                "continuously in real time. Here it jumps abruptly ("
                + ", ".join(
                    f"{j['t']:.1f} s: {j['delta_hz'] * 1000:+.0f} mHz" for j in res.jumps[:4]
                )
                + "), which happens when pieces recorded at different times are joined.",
                Hypothesis.MANIPULATED,
                Strength.STRONG,
                Category.TAMPERING,
                spans=spans,
                jumps=len(res.jumps),
            )  # fmt: skip
        )
        summary = f"ENF present ({res.snr_db:.0f} dB); {len(res.jumps)} discontinuity(ies)"
    else:
        findings.append(
            finding(
                "ENF_CONTINUOUS",
                "Mains-frequency trace is continuous",
                f"A 50 Hz grid signature is present (SNR {res.snr_db:.0f} dB at the "
                f"{50 * res.harmonic} Hz harmonic) and drifts smoothly for the whole "
                "recording, as in an unedited recording. With grid-operator frequency logs "
                "it can also date the recording.",
                Hypothesis.AUTHENTIC,
                Strength.MODERATE,
                Category.TAMPERING,
            )  # fmt: skip
        )
        summary = f"ENF present ({res.snr_db:.0f} dB) and continuous"
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Transcript and fraud language
# ---------------------------------------------------------------------------------------------

ASK_NAMES = {
    "A1": "transfer to a new / 'safe' account", "A2": "asks for OTP / PIN / password",
    "A3": "asks to install a remote-access app", "A4": "demands secrecy / isolation",
    "A5": "asks to bypass a process", "A6": "asks for gift cards / crypto / UPI collect",
    "A7": "changes payee or bank details",
}  # fmt: skip
RULE_NAMES = {
    "digital_arrest": "'digital arrest' threat", "rbi_safe_account": "'RBI safe account'",
    "otp_request": "OTP request", "kyc_expiry": "KYC-expiry pressure",
    "courier_fee": "courier / customs fee", "power_cut": "electricity disconnection threat",
}  # fmt: skip


def content_findings(text: str, spans_by_text: Any = None) -> tuple[list[Finding], dict[str, Any]]:
    from satyapan.asks.extractor import extract_asks
    from satyapan.citizen.rules import scam_check
    from satyapan.contracts.enums import Lang

    asks = extract_asks(text)
    rules = scam_check(text, Lang.EN).rule_hits if text.strip() else []
    kinds = sorted({str(a.ask_type) for a in asks})
    data = {"asks": [{"type": str(a.ask_type), "text": a.text, "meaning": ASK_NAMES.get(
        str(a.ask_type), "")} for a in asks], "rules": rules}  # fmt: skip
    out: list[Finding] = []
    if asks or rules:
        what = [ASK_NAMES.get(k, k) for k in kinds] + [RULE_NAMES.get(r, r) for r in rules]
        out.append(
            info(
                "FRAUD_LANGUAGE",
                "Speech contains fraud / extortion requests",
                "The words match known cyber-fraud scripts: "
                + "; ".join(dict.fromkeys(what))
                + ". This is investigative context (modus operandi), not evidence about "
                "whether the voice is real.",
                Category.CONTENT,
                asks=kinds,
                rules=rules,
            )  # fmt: skip
        )
    return out, data


def run_transcript(ctx: AnalysisContext) -> TechniqueResult:
    t = TRANSCRIPT
    try:
        asr = ctx.models.get("asr")
    except Unavailable as exc:
        return make_result(t, summary=str(exc), status=Status.UNAVAILABLE)
    x = x16(ctx)
    if dsp.speech_seconds(x) < 0.5:
        return make_result(t, summary="no speech", status=Status.SKIPPED)
    tr = asr.transcribe(dsp.normalise_loudness(x[: 16000 * 600]))
    text = tr.text
    english = " ".join(s.text for s in tr.translation).strip()
    findings, cdata = content_findings(text + ("\n" + english if english else ""))
    ctx.cache["transcript"] = text
    data = {"language": tr.language, "language_probability": round(tr.language_probability, 3),
            "engine": tr.engine, "text": text, "translation": english,
            "segments": [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text}
                         for s in tr.segments],
            "translation_segments": [{"start": round(s.start, 2), "end": round(s.end, 2),
                                      "text": s.text} for s in tr.translation], **cdata}  # fmt: skip
    summary = f"{tr.language} speech, {len(text.split())} words" + (
        f"; fraud language: {len(cdata['asks']) + len(cdata['rules'])} cue(s)" if findings else "")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data)


AUDIO_CONTAINER = Technique(
    "audio.container", "Container & encoder metadata", Category.METADATA, AUD,
    run_audio_container,
    "ffprobe reads the container, codec, sample rate, bit rate, duration and every tag. Tags "
    "and file names are matched against encoders, messaging-app formats and known "
    "speech-synthesis tools.", "FFmpeg ffprobe", order=1,
)  # fmt: skip
SPECTRAL = Technique(
    "audio.spectral", "Spectrogram & bandwidth history", Category.PROVENANCE, AV, run_spectral,
    "A short-time Fourier transform gives the spectrogram. The long-term average spectrum of "
    "the active frames shows the highest frequency that carries signal; a sharp wall below "
    "the file's Nyquist frequency reveals an earlier lower sample rate (telephone, VoIP, TTS) "
    "or a lossy codec's low-pass.",
    "Maher, 'Audio forensic examination' (IEEE SPM 2009)", order=10,
)  # fmt: skip
VOICE = Technique(
    "audio.voice", "Synthetic / cloned voice detector", Category.SYNTHETIC, AV, run_voice,
    "5-second windows are scored by a wav2vec2 XLS-R model fine-tuned for deepfake speech "
    "(selected in a pre-registered comparison; In-the-Wild AUC 0.921 on unseen speakers). "
    "Thresholds are the 1% and 5% false-alarm points on genuine speech; 'likely synthetic' "
    "requires two consecutive windows above the strict one; under 3 s of speech is not judged.",
    "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification; Müller et al., 'Does audio "
    "deepfake detection generalize?' (Interspeech 2022)",
    "Background noise lowers the score of cloned voices (measured: docs/VOICE_DEEPFAKE.md); a "
    "low score is not proof of a genuine voice.", order=30,
)  # fmt: skip
SPLICE = Technique(
    "audio.splice", "Splice & edit-point detection", Category.TAMPERING, AV, run_splice,
    "Three cues are located and merged: runs of exact digital silence inside a recording that "
    "otherwise has background noise, abrupt steps in the background noise floor between "
    "adjacent 1.5 s windows, and isolated sample-to-sample jumps (hard cuts without a fade). "
    "A coinciding mains-frequency jump from the ENF analysis is noted, not counted twice.",
    "Grigoras, 'Digital audio recording analysis: the ENF criterion' (2005); SWGDE Best "
    "Practices for Digital Audio Authentication", order=21,
)  # fmt: skip
ENF = Technique(
    "audio.enf", "Electrical Network Frequency (ENF)", Category.TAMPERING, AV, run_enf,
    "Recordings made near mains-powered equipment capture the grid's hum (50 Hz in India), "
    "whose frequency drifts randomly by a few millihertz. The hum and its harmonics are "
    "band-pass filtered and tracked with zero-padded 4 s STFT frames and quadratic peak "
    "interpolation. A continuous trace supports an unedited recording; an abrupt jump marks "
    "a likely edit; the trace can be matched to grid logs to date a recording.",
    "Grigoras 2005; Hua et al., 'ENF signal analysis' (IEEE SPM 2021)",
    "Battery-powered phones often capture no hum: then the method does not apply.", order=20,
)  # fmt: skip
TRANSCRIPT = Technique(
    "audio.transcript", "Transcript & fraud-language cues", Category.CONTENT, AV, run_transcript,
    "Speech is transcribed offline with Whisper (automatic language detection: Hindi, "
    "English, Hinglish and others) with timestamps. The text is matched against Satyapan's "
    "deterministic fraud lexicon (OTP / safe-account / secrecy / remote-access requests in "
    "English, Hinglish and Devanagari) and the impossible-claim rules (digital arrest, RBI "
    "safe account, KYC expiry).",
    "Radford et al., 'Whisper' (2022); Satyapan ask lexicon v1.1",
    "Context for the investigator; it does not decide authenticity.", order=40,
)  # fmt: skip
