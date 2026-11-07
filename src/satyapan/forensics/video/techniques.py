"""Video forensic techniques: container provenance, frame-level integrity and the face
deepfake timeline. The audio track is analysed by the audio techniques (they accept video)."""

from __future__ import annotations

import re
from typing import Any

import numpy as np

from satyapan.forensics.audio.techniques import probe_info
from satyapan.forensics.base import (
    NotApplicable,
    Technique,
    Unavailable,
    finding,
    info,
    make_result,
)
from satyapan.forensics.context import AnalysisContext
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
from satyapan.forensics.probe import all_tags, fraction, streams

VID = (MediaKind.VIDEO,)
MAX_DEEPFAKE_S = 120.0
MAX_FRAMES_S = 300.0


def video_path(ctx: AnalysisContext) -> Any:
    path = ctx.cache.get("path")
    if path is None:
        raise NotApplicable("video file path not available")
    return path


# ---------------------------------------------------------------------------------------------
# Container & device provenance
# ---------------------------------------------------------------------------------------------

DEVICE_TAGS = (
    "com.apple.quicktime.make", "com.apple.quicktime.model", "com.apple.quicktime.software",
    "com.apple.quicktime.creationdate", "com.android.version", "com.android.manufacturer",
    "com.android.model", "make", "model",
)  # fmt: skip
VIDEO_GEN_HINTS = [
    (r"\bsora\b", "OpenAI Sora"), (r"\brunway\b|gen-?3", "Runway"), (r"\bpika\b", "Pika"),
    (r"\bkling\b", "Kling"), (r"\bluma\b|dream machine", "Luma Dream Machine"),
    (r"\bveo\b", "Google Veo"), (r"heygen", "HeyGen"), (r"synthesia", "Synthesia"),
    (r"d-?id\b", "D-ID"), (r"deepfacelab|dfl", "DeepFaceLab"), (r"faceswap", "Faceswap"),
    (r"facefusion", "FaceFusion"), (r"roop", "roop"), (r"deep-?live-?cam", "Deep-Live-Cam"),
    (r"hailuo|minimax", "Hailuo / MiniMax"), (r"wan2|wan-?video", "Wan video"),
]  # fmt: skip


def run_video_container(ctx: AnalysisContext) -> TechniqueResult:
    t = VIDEO_CONTAINER
    pi = probe_info(ctx)
    fmt = pi.get("format", {})
    vs = streams(pi, "video")
    au = streams(pi, "audio")
    if not vs:
        return make_result(t, summary="no video stream", status=Status.SKIPPED)
    v = vs[0]
    tags = all_tags(pi)
    fps = fraction(v.get("avg_frame_rate")) or fraction(v.get("r_frame_rate"))
    rfps = fraction(v.get("r_frame_rate"))
    data: dict[str, Any] = {
        "container": fmt.get("format_long_name"), "brand": tags.get("major_brand"),
        "compatible_brands": tags.get("compatible_brands"),
        "duration_s": round(float(fmt.get("duration") or 0), 3), "bit_rate": fmt.get("bit_rate"),
        "video_codec": v.get("codec_long_name"), "profile": v.get("profile"),
        "width": v.get("width"), "height": v.get("height"), "fps": round(fps, 3) if fps else None,
        "frames": v.get("nb_frames"), "pix_fmt": v.get("pix_fmt"),
        "rotation": next((sd.get("rotation") for sd in v.get("side_data_list", [])
                          if "rotation" in sd), None),
        "audio_codec": au[0].get("codec_long_name") if au else None, "tags": tags,
    }  # fmt: skip
    findings: list[Finding] = []
    dev = {k: tags[k] for k in tags if any(k.endswith(d) for d in DEVICE_TAGS)}
    if dev:
        name = " ".join(dict.fromkeys(v for k, v in dev.items()
                                      if "make" in k or "model" in k or "manufacturer" in k))  # fmt: skip
        findings.append(
            info(
                "DEVICE_METADATA",
                f"Recording device metadata: {name or 'present'}",
                "The container carries the capturing device's own tags ("
                + ", ".join(f"{k.split(':')[-1]}={v}" for k, v in list(dev.items())[:5])
                + "). Phones write these at capture; editors and messaging apps usually drop "
                "them. They can be forged, so treat them as a claim.",
                Category.PROVENANCE,
                **{k.split(":")[-1]: v for k, v in dev.items()},
            )  # fmt: skip
        )
    loc = next((v for k, v in tags.items() if k.endswith("location") or "ISO6709" in k), None)
    if loc:
        findings.append(info("GPS_LOCATION", f"Location recorded: {loc}",
                             "ISO 6709 location written by the recording device.",
                             Category.PROVENANCE, location=loc))  # fmt: skip
    enc = " ".join(v for k, v in tags.items() if "encoder" in k.lower())
    handlers = " ".join(v for k, v in tags.items() if "handler_name" in k)
    if enc:
        is_ff = "lavf" in enc.lower() or "lavc" in enc.lower()
        findings.append(
            info(
                "ENCODER_TAG",
                f"Encoded by {'FFmpeg (libavformat)' if is_ff else enc[:60]}",
                f"Encoder tag “{enc[:120]}”. "
                + (
                    "FFmpeg is how most editing tools, converters and deepfake pipelines "
                    "(DeepFaceLab, FaceFusion, roop) write their output; a phone camera does "
                    "not. The file is not a camera original."
                    if is_ff
                    else ""
                ),
                Category.PROVENANCE,
                encoder=enc[:200],
            )  # fmt: skip
        )
    blob = " ".join(f"{k}={v}" for k, v in tags.items()) + " " + (ctx.filename or "")
    for pat, name in VIDEO_GEN_HINTS:
        if re.search(pat, blob, re.I):
            findings.append(
                finding(
                    "VIDEO_GENERATOR_SIGNATURE",
                    f"Metadata names a synthetic-video tool: {name}",
                    f"A tag or the file name mentions {name}, a tool that generates or "
                    "face-swaps video. Names can be edited, so corroborate with the "
                    "face analysis.",
                    Hypothesis.SYNTHETIC,
                    Strength.MODERATE,
                    Category.PROVENANCE,
                    tool=name,
                )  # fmt: skip
            )
            break
    if au:
        vd = float(v.get("duration") or 0)
        ad = float(au[0].get("duration") or 0)
        if vd > 0 and ad > 0 and abs(vd - ad) > 0.75:
            findings.append(
                finding(
                    "STREAM_DURATION_MISMATCH",
                    "Audio and video tracks differ in length",
                    f"Video {vd:.2f} s vs audio {ad:.2f} s. A camera records both tracks "
                    "together; a mismatch appears when tracks are cut, replaced or re-muxed "
                    "separately (for example a voice-over or a dubbed deepfake voice).",
                    Hypothesis.MANIPULATED,
                    Strength.WEAK,
                    Category.INTEGRITY,
                    video_s=vd,
                    audio_s=ad,
                )  # fmt: skip
            )
    if fps and rfps and abs(fps - rfps) / max(rfps, 1) > 0.05:
        data["variable_frame_rate"] = True
    if handlers:
        data["handlers"] = handlers
    summary = (f"{v.get('codec_name')} {v.get('width')}×{v.get('height')} @ "
               f"{fps or 0:.2f} fps, {data['duration_s']:.1f} s"
               + (f", device {list(dev.values())[0]}" if dev else ""))  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Frame-level integrity: duplicates, cuts, timestamp gaps, contact sheet
# ---------------------------------------------------------------------------------------------


def run_frames(ctx: AnalysisContext) -> TechniqueResult:
    t = FRAMES
    try:
        import av
    except ImportError:
        return make_result(t, summary="PyAV not installed", status=Status.UNAVAILABLE)
    path = video_path(ctx)
    smalls: list[np.ndarray] = []
    hists: list[np.ndarray] = []
    pts: list[float] = []
    thumbs: list[tuple[float, np.ndarray]] = []
    duration = float(ctx.media.duration_s or 0)
    want_thumbs = np.linspace(0.02, 0.98, 8) * duration if duration else []
    ti = 0
    with av.open(str(path)) as container:
        if not container.streams.video:
            return make_result(t, summary="no video stream", status=Status.SKIPPED)
        st = container.streams.video[0]
        st.thread_type = "AUTO"
        tb = float(st.time_base) if st.time_base else 1 / 25
        for frame in container.decode(video=0):
            ts = float(frame.pts * tb) if frame.pts is not None else (len(pts) / 25.0)
            if ts > MAX_FRAMES_S:
                break
            g = frame.to_ndarray(width=96, height=54, format="gray").astype(np.float32)
            smalls.append(g)
            hists.append(np.histogram(g, bins=16, range=(0, 256))[0].astype(np.float32))
            pts.append(ts)
            if ti < len(want_thumbs) and ts >= want_thumbs[ti]:
                thumbs.append((ts, frame.to_ndarray(width=320, height=int(320 * frame.height /
                                                    max(1, frame.width)), format="rgb24")))  # fmt: skip
                ti += 1
    n = len(smalls)
    if n < 3:
        return make_result(t, summary="too few frames decoded", status=Status.SKIPPED)
    arr = np.stack(smalls)
    diff = np.abs(np.diff(arr, axis=0)).mean(axis=(1, 2))
    h = np.stack(hists)
    h = h / (h.sum(axis=1, keepdims=True) + 1e-6)
    hd = 0.5 * np.abs(np.diff(h, axis=0)).sum(axis=1)
    p = np.array(pts)
    dt = np.diff(p)
    med_dt = float(np.median(dt[dt > 0])) if (dt > 0).any() else 0.04
    moving = np.convolve(diff, np.ones(9) / 9, mode="same")
    dup = (diff < 0.15) & (moving > 1.5)
    dup_idx = np.where(dup)[0]
    cuts = np.where((hd > 0.35) & (diff > 12))[0]
    gaps = np.where(dt > 2.5 * med_dt)[0] if med_dt > 0 else np.array([], int)
    findings: list[Finding] = []
    data: dict[str, Any] = {
        "frames": n, "median_interval_ms": round(med_dt * 1000, 2),
        "t": [round(float(x), 3) for x in p[1:][:: max(1, n // 1500)]],
        "motion": [round(float(x), 3) for x in diff[:: max(1, n // 1500)]],
        "cuts_s": [round(float(p[i + 1]), 2) for i in cuts[:50]],
        "duplicates_s": [round(float(p[i + 1]), 2) for i in dup_idx[:100]],
        "gaps": [{"t": round(float(p[i]), 2), "ms": round(float(dt[i] * 1000), 1)}
                 for i in gaps[:50]],
    }  # fmt: skip
    if len(dup_idx) >= 2:
        periodic = False
        if len(dup_idx) >= 6:
            iv = np.diff(dup_idx)
            periodic = float(np.std(iv)) < 0.6 and float(np.median(iv)) <= 6
        if periodic:
            findings.append(info("FRAME_RATE_CONVERSION", "Regularly repeated frames",
                                 "Frames repeat at a fixed interval, the signature of frame-rate "
                                 "conversion (e.g. 25 → 30 fps) when the video was re-encoded.",
                                 Category.PROVENANCE, count=int(len(dup_idx))))  # fmt: skip
        else:
            spans = [TimeSpan(start_s=float(p[i]), end_s=float(p[i + 1]), label="duplicate")
                     for i in dup_idx[:20]]  # fmt: skip
            findings.append(
                finding(
                    "DUPLICATED_FRAMES",
                    f"{len(dup_idx)} duplicated frame(s) inside motion",
                    "Identical consecutive frames appear while the scene is otherwise "
                    "moving. Frames are duplicated when footage is padded or a frozen "
                    "image is inserted to hide removed content.",
                    Hypothesis.MANIPULATED,
                    Strength.WEAK,
                    Category.TAMPERING,
                    spans=spans,
                    count=int(len(dup_idx)),
                )  # fmt: skip
            )
    if len(gaps):
        spans = [TimeSpan(start_s=float(p[i]), end_s=float(p[i + 1]), label="timestamp gap",
                          score=round(float(dt[i] * 1000), 1)) for i in gaps[:20]]  # fmt: skip
        findings.append(
            finding(
                "TIMESTAMP_GAPS",
                f"{len(gaps)} gap(s) in the frame timestamps",
                f"Frame interval is normally {med_dt * 1000:.0f} ms but jumps to "
                + ", ".join(f"{dt[i] * 1000:.0f} ms at {p[i]:.1f} s" for i in gaps[:4])
                + ". Missing time inside a single recording indicates frames were removed "
                "(or the recorder dropped them under load).",
                Hypothesis.MANIPULATED,
                Strength.MODERATE if float(dt[gaps].max()) > 0.5 else Strength.WEAK,
                Category.TAMPERING,
                spans=spans,
                gaps=int(len(gaps)),
            )  # fmt: skip
        )
    if len(cuts):
        findings.append(
            info(
                "SHOT_BOUNDARIES",
                f"{len(cuts)} hard cut(s) between shots",
                "Abrupt scene changes at "
                + ", ".join(f"{p[i + 1]:.1f} s" for i in cuts[:8])
                + ". Expected in edited videos; in a recording that claims to be one "
                "continuous take (a call, CCTV) each cut is an edit point.",
                Category.TAMPERING,
                cuts=int(len(cuts)),
            )  # fmt: skip
        )
    arts = []
    if thumbs:
        import cv2

        hh = min(im.shape[0] for _, im in thumbs)
        tiles = []
        for ts, im in thumbs:
            im = np.ascontiguousarray(im[:hh])
            cv2.putText(im, f"{ts:6.1f}s", (6, hh - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)  # fmt: skip
            tiles.append(im)
        while len(tiles) % 4:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.concatenate(tiles[i : i + 4], axis=1) for i in range(0, len(tiles), 4)]
        sheet = np.concatenate(rows, axis=0)
        arts.append(ctx.save_jpeg("contact_sheet", sheet, "figure", "Key frames",
                                  "Evenly spaced frames with their time stamps."))  # fmt: skip
    summary = (f"{n} frames; {len(cuts)} cut(s), {len(dup_idx)} duplicate(s), "
               f"{len(gaps)} timestamp gap(s)")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data, artifacts=arts)


# ---------------------------------------------------------------------------------------------
# Face deepfake timeline (GenD + validated window fusion)
# ---------------------------------------------------------------------------------------------


def run_video_deepfake(ctx: AnalysisContext) -> TechniqueResult:
    t = VIDEO_DEEPFAKE
    try:
        base = ctx.models.get("video")
    except Unavailable as exc:
        return make_result(t, summary=str(exc), status=Status.UNAVAILABLE)
    from satyapan.contracts.enums import VideoLabel
    from satyapan.video.analyzer import VideoAnalyzer
    from satyapan.video.io import iter_frames

    crops: dict[float, tuple[float, np.ndarray]] = {}

    class Recording(VideoAnalyzer):
        def score_window(self, index, records, audio=None, sr=16000, audio_t0=0.0, cache=None):  # type: ignore[no-untyped-def,override]
            res = super().score_window(index, records, audio, sr, audio_t0, cache)
            for r in records:
                if r.crop is not None and cache and r.t in cache and r.t not in crops:
                    crops[r.t] = (float(cache[r.t]), r.crop)
            return res

    an = Recording(base.fusion, base.thresholds, base.scorer, base.tracker_factory,
                   base.crop_every_s)  # fmt: skip
    path = video_path(ctx)
    audio = None
    try:
        audio = ctx.audio(16000)[: int(MAX_DEEPFAKE_S * 16000)]
    except ValueError:
        audio = None
    total = float(ctx.media.duration_s or MAX_DEEPFAKE_S)
    progress_every = max(1, int(total // 10))

    def frames() -> Any:
        last = -1
        for ts, rgb in iter_frames(path, max_s=MAX_DEEPFAKE_S):
            if int(ts) // progress_every != last:
                last = int(ts) // progress_every
                ctx.progress("video.deepfake", f"face model at {ts:.0f}s / {total:.0f}s",
                             min(0.99, ts / max(total, 1)))  # fmt: skip
            yield ts, rgb

    with ctx.models.lock("video_run"):
        windows = an.analyze_frames(frames(), audio)
    verdict = an.verdict(windows)
    thr = an.thresholds
    rows = [{"i": w.index, "start": round(w.t_start, 2), "end": round(w.t_end, 2),
             "score": None if w.score is None else round(w.score, 4), "cues": w.cues,
             "faces": round(w.coverage.found_frac, 3) if hasattr(w.coverage, "found_frac") else None}
            for w in windows]  # fmt: skip
    crop_series = sorted((ts, lg) for ts, (lg, _) in crops.items())
    data = {"windows": rows, "tau_hi": thr.tau_hi, "tau_lo": thr.tau_lo,
            "label": str(verdict.label), "usable_windows": verdict.usable_windows,
            "crop_logits": [{"t": round(a, 2), "logit": round(b, 3)} for a, b in crop_series],
            "analysed_s": min(total, MAX_DEEPFAKE_S),
            "benchmark": "FF++ c23 test AUC 0.946; 0/563 real videos called synthetic"}  # fmt: skip
    arts = []
    top = sorted(crops.items(), key=lambda kv: -kv[1][0])[:4]
    if top:
        tiles = [c for _, (_, c) in sorted(top)]
        strip = np.concatenate([np.pad(c, ((0, 0), (0, 4), (0, 0)), constant_values=255)
                                for c in tiles], axis=1)  # fmt: skip
        arts.append(ctx.save_png("face_frames", strip, "crop", "Most suspicious face frames",
                                 "Face crops with the highest deepfake scores, in time order: "
                                 + ", ".join(f"{ts:.1f}s" for ts, _ in sorted(top))))  # fmt: skip
    findings: list[Finding] = []
    hot = [w for w in windows if w.score is not None and w.score >= thr.tau_lo]
    spans = [TimeSpan(start_s=round(w.t_start, 2), end_s=round(w.t_end, 2),
                      label="likely synthetic" if (w.score or 0) >= thr.tau_hi else "elevated",
                      score=round(w.score or 0, 3)) for w in hot]  # fmt: skip
    if verdict.label == VideoLabel.LIKELY_SYNTHETIC:
        findings.append(
            finding(
                "VIDEO_DEEPFAKE",
                "Face in the video is likely synthetic (deepfake)",
                f"{verdict.max_consecutive_over_hi} consecutive 6-second windows score above "
                f"the strict threshold ({thr.tau_hi:.3f}, 1% of windows of real videos in "
                "validation). The face model (GenD) and the temporal cues"
                + (
                    f" ({', '.join(sorted({c for w in hot for c in w.cues}))})"
                    if any(w.cues for w in hot)
                    else ""
                )
                + " consistently indicate a swapped or generated face.",
                Hypothesis.SYNTHETIC,
                Strength.STRONG,
                Category.SYNTHETIC,
                score=round(verdict.max_score, 4),
                spans=spans,
                artifacts=[a.name for a in arts],
            )  # fmt: skip
        )
    elif hot:
        findings.append(
            finding(
                "VIDEO_DEEPFAKE",
                f"Face score elevated in {len(hot)} window(s)",
                "Some windows exceed the lenient threshold (5% false alarms) without the "
                "two-consecutive-window rule for a strict result. Examine those segments "
                "frame by frame.",
                Hypothesis.SYNTHETIC,
                Strength.MODERATE
                if any((w.score or 0) >= thr.tau_hi for w in hot)
                else Strength.WEAK,
                Category.SYNTHETIC,
                score=round(verdict.max_score, 4),
                spans=spans,
                artifacts=[a.name for a in arts],
            )  # fmt: skip
        )
    if verdict.usable_windows == 0:
        return make_result(t, summary="no usable face in the video (too small, absent or dark)",
                           status=Status.SKIPPED, data=data, artifacts=arts)  # fmt: skip
    summary = (f"{verdict.usable_windows}/{len(windows)} windows with a face; max score "
               f"{verdict.max_score:.3f} ({verdict.label})")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data, artifacts=arts)


VIDEO_CONTAINER = Technique(
    "video.container", "Container, device & encoder metadata", Category.PROVENANCE, VID,
    run_video_container,
    "ffprobe reads the container brand, streams, frame rate, rotation and all tags. Device "
    "tags written at capture (Apple QuickTime make/model/software/location, Android model) "
    "are reported; encoder tags identify re-encoding (FFmpeg is used by editors and deepfake "
    "pipelines); tags and names are matched against synthetic-video tools; audio and video "
    "track lengths are compared.", "ISO/IEC 14496-12 (ISO BMFF); Apple QuickTime metadata",
    order=1,
)  # fmt: skip
FRAMES = Technique(
    "video.frames", "Frame-level integrity", Category.TAMPERING, VID, run_frames,
    "Every frame (up to 5 minutes) is decoded at 96×54 grey. Consecutive-frame differences "
    "find duplicated frames inside motion, colour-histogram jumps find hard cuts, and frame "
    "presentation timestamps reveal gaps where frames are missing. Regularly repeated frames "
    "are attributed to frame-rate conversion. A contact sheet of key frames is produced.",
    "Wang & Farid, 'Exposing digital forgeries in video by detecting duplication' (2007)",
    order=20,
)  # fmt: skip
VIDEO_DEEPFAKE = Technique(
    "video.deepfake", "Deepfake face timeline", Category.SYNTHETIC, VID, run_video_deepfake,
    "Faces are tracked at 15 fps (YuNet + MediaPipe Face Landmarker). Every 2.25 s a 224 px "
    "face crop is scored by GenD; 6-second windows (3 s hop) fuse the crop scores with "
    "temporal cues (blinks, landmark jitter, remote-PPG pulse, lip-sync) in a logistic model "
    "fitted on FaceForensics++ validation. 'Likely synthetic' requires two consecutive "
    "windows above the 1% false-alarm threshold. The first 120 s are analysed.",
    "GenD (WACV 2026); FaceForensics++ (Rössler et al., ICCV 2019); Satyapan video protocol "
    "(docs/VIDEO_DEEPFAKE.md)",
    "Unseen face-swap methods are caught less often (FaceShifter 32%); small or dark faces "
    "abstain. Fully generated videos (Sora, Veo) are not what this model was trained on.",
    order=30,
)  # fmt: skip
