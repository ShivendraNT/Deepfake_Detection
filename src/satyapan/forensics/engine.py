"""Run every applicable technique on one evidence item and fuse the results.

    analysis = analyze_bytes(data, filename, artifact_dir, models=registry())

No technique can crash an analysis: errors become Status.ERROR with the message, missing models
Status.UNAVAILABLE, and both are listed in the verdict as "not checked".
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.forensics import catalogue, verdict
from satyapan.forensics.base import NotApplicable, Technique, Unavailable, make_result
from satyapan.forensics.context import AnalysisContext
from satyapan.forensics.filetype import Sniffed, extension_mismatch, extension_of, hashes, sniff
from satyapan.forensics.models import (
    EvidenceAnalysis,
    MediaInfo,
    MediaKind,
    Status,
    TechniqueResult,
    utcnow,
)
from satyapan.forensics.probe import ffprobe, fraction, streams

Progress = Callable[[str, str, float, str], None]


def media_info(
    data: bytes, filename: str, sn: Sniffed, path: Path | None
) -> tuple[MediaInfo, dict[str, Any] | None]:
    m = MediaInfo(kind=sn.kind, mime=sn.mime, format=sn.format, extension=extension_of(filename),
                  extension_mismatch=extension_mismatch(sn, filename))  # fmt: skip
    probe = None
    if sn.kind == MediaKind.IMAGE:
        import io

        from PIL import Image

        try:
            with Image.open(io.BytesIO(data)) as img:
                m.width, m.height = img.size
                m.color_mode = img.mode
                m.frames = getattr(img, "n_frames", 1)
        except Exception:  # noqa: BLE001 - the structure technique reports it
            pass
    elif sn.kind in (MediaKind.AUDIO, MediaKind.VIDEO):
        try:
            probe = ffprobe(data=None if path else data, path=path)
        except ValueError:
            return m, None
        fmt = probe.get("format", {})
        m.duration_s = float(fmt.get("duration") or 0) or None
        vs, au = streams(probe, "video"), streams(probe, "audio")
        if sn.kind == MediaKind.VIDEO and not vs and au:
            m.kind = MediaKind.AUDIO  # an .mp4 / .m4a with only sound is an audio exhibit
        if sn.kind == MediaKind.AUDIO and vs and not au:
            m.kind = MediaKind.VIDEO
        if vs:
            v = vs[0]
            m.width, m.height = v.get("width"), v.get("height")
            m.fps = fraction(v.get("avg_frame_rate")) or fraction(v.get("r_frame_rate"))
            m.codec = v.get("codec_name")
            m.frames = int(v["nb_frames"]) if str(v.get("nb_frames", "")).isdigit() else None
        if au:
            a = au[0]
            m.sample_rate = int(a.get("sample_rate") or 0) or None
            m.channels = a.get("channels")
            m.audio_codec = a.get("codec_name")
            if m.kind == MediaKind.AUDIO:
                m.codec = a.get("codec_name")
        m.has_audio = bool(au)
    return m, probe


def run_technique(t: Technique, ctx: AnalysisContext) -> TechniqueResult:
    t0 = time.perf_counter()
    try:
        res = t.run(ctx)
    except NotApplicable as exc:
        res = make_result(t, summary=str(exc), status=Status.SKIPPED)
    except Unavailable as exc:
        res = make_result(t, summary=str(exc), status=Status.UNAVAILABLE)
    except ValueError as exc:
        res = make_result(t, summary=f"could not analyse: {exc}"[:300], status=Status.ERROR)
        res.error = str(exc)[:1000]
    except Exception as exc:  # noqa: BLE001 - one technique must never stop the analysis
        res = make_result(t, summary=f"internal error: {type(exc).__name__}", status=Status.ERROR)
        res.error = "".join(traceback.format_exception_only(type(exc), exc))[:1500]
    res.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    for f in res.findings:
        f.technique = t.id
        f.category = f.category or t.category
    return res


def features(ctx: AnalysisContext, results: list[TechniqueResult]) -> dict[str, Any]:
    """Small per-item features for cross-evidence links."""
    from satyapan.forensics import links

    out: dict[str, Any] = {}
    kind = ctx.media.kind
    try:
        if kind == MediaKind.IMAGE:
            g = ctx.gray(1024)
            out["phash"], out["dhash"] = links.phash(g), links.dhash(g)
            out["faces"] = links.face_embeddings(ctx.rgb(1600), ctx.models)
        elif kind == MediaKind.VIDEO and ctx.cache.get("path"):
            frames = keyframes(ctx.cache["path"], 3)
            if frames:
                mid = frames[len(frames) // 2]
                out["phash"] = links.phash(mid.astype(np.float32).mean(axis=2))
                faces: list[list[float]] = []
                for fr in frames:
                    faces += links.face_embeddings(fr, ctx.models, max_faces=1)
                out["faces"] = faces[:3]
    except Exception:  # noqa: BLE001 - features are optional
        pass
    if kind in (MediaKind.AUDIO, MediaKind.VIDEO):
        try:
            x = ctx.audio(16000)
            from satyapan.forensics.audio.dsp import speech_seconds

            if speech_seconds(x) >= 3.0:
                emb = ctx.models.get("speaker").embed(x)
                out["speaker"] = [round(float(v), 5) for v in emb]
        except Exception:  # noqa: BLE001
            pass
    for r in results:
        for f in r.findings:
            if f.code in ("CAMERA_IDENTIFIED",):
                out["device"] = (
                    f"{f.observations.get('make', '')} {f.observations.get('model', '')}".strip()
                )
            if f.code in (
                "GENERATOR_SIGNATURE",
                "SD_WATERMARK",
                "C2PA_AI_GENERATED",
            ) and not out.get("generator"):
                out["generator"] = str(f.observations.get("generator") or "")
    return out


def keyframes(path: Path, n: int = 3) -> list[np.ndarray]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        out = []
        for i in range(n):
            idx = int((i + 0.5) / n * total) if total else i * 30
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, bgr = cap.read()
            if ok:
                out.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        return out
    finally:
        cap.release()


def analyze_bytes(
    data: bytes,
    filename: str,
    artifact_dir: Path,
    *,
    models: Any,
    evidence_id: str = "ev_adhoc",
    case_id: str = "case_adhoc",
    path: Path | None = None,
    role: str = "questioned",
    progress: Progress | None = None,
    only: set[str] | None = None,
) -> tuple[EvidenceAnalysis, dict[str, Any]]:
    """Returns (analysis, features)."""
    started = utcnow()
    emit = progress or (lambda *_: None)
    h = hashes(data)
    sn = sniff(data)
    media, probe = media_info(data, filename, sn, path)
    ctx = AnalysisContext(evidence_id=evidence_id, case_id=case_id, data=data,
                          filename=filename, sniffed=sn, media=media,
                          artifact_dir=artifact_dir, models=models, role=role)  # fmt: skip
    if path is not None:
        ctx.cache["path"] = path
    if probe is not None:
        ctx.cache["probe"] = probe

    def tech_progress(stage: str, message: str, frac: float) -> None:
        emit(stage, message, frac, "running")

    ctx.progress = tech_progress
    techs = [t for t in catalogue.for_kind(media.kind) if not only or t.id in only]
    results: list[TechniqueResult] = []
    for i, t in enumerate(techs):
        emit(t.id, f"{t.name}…", i / max(1, len(techs)), "running")
        res = run_technique(t, ctx)
        results.append(res)
        emit(t.id, res.summary, (i + 1) / max(1, len(techs)), res.status.value)
    emit("features", "computing perceptual hashes and identity embeddings", 0.99, "running")
    feats = features(ctx, results)
    v = verdict.decide(media.kind, results)
    analysis = EvidenceAnalysis(
        evidence_id=evidence_id, case_id=case_id, started_at=started, finished_at=utcnow(),
        media=media, hashes=h, integrity_verified=True, techniques=results, verdict=v,
        provenance=verdict.provenance(results),
        perceptual={k: feats[k] for k in ("phash", "dhash") if k in feats},
    )  # fmt: skip
    return analysis, feats
