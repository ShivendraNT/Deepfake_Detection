"""Cross-exhibit inferences: conclusions that need two or more exhibits (METHODOLOGY.md §2).

One file cannot show that a video call is someone else's footage with a new face, or that a
small WhatsApp picture is a copy of a file that carries AI provenance; the case can. The
rules are deterministic and recomputed whenever an exhibit finishes:

  FACE_REPLACED      two videos show the same footage (key frames match: the near-duplicate
                     link) but not the same person (median SFace cosine over matched frames
                     below OpenCV's 0.363 same-identity point), or one video's face matches a
                     third exhibit far better than the other's does (the face source). The
                     altered one is the exhibit whose face matches that source. Strong support
                     when, in addition, the frame difference between the two is concentrated on
                     the face; moderate with only one of the two corroborations; otherwise both
                     are only noted.
  COPY_OF_SYNTHETIC  an image is a near-duplicate of an exhibit whose own (file-only) analysis
                     is SYNTHETIC, with no regions changed after alignment; it inherits that
                     support, at most strong. Not applied to an item already SYNTHETIC on its
                     own evidence, so nothing is counted twice.

Findings are attached to the exhibit as the technique "case.compare" and its verdict is
re-decided from its own findings plus these. Inferences use only file-only verdicts, so they
never feed on each other.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from satyapan.forensics.base import finding, info
from satyapan.forensics.links import SFACE_DIFFERENT, SFACE_SAME, YUNET, _cos
from satyapan.forensics.models import (
    Artifact,
    Category,
    EvidenceAnalysis,
    EvidenceLink,
    Finding,
    Hypothesis,
    LabEvidence,
    LinkKind,
    Status,
    Strength,
    TechniqueResult,
    VerdictLabel,
)
from satyapan.forensics.verdict import decide

TECH_ID = "case.compare"
TECH_NAME = "Cross-exhibit comparison"
METHOD = (
    "Exhibits are compared with each other: perceptual hashes of images and video key frames, "
    "SFace face embeddings, speaker embeddings and keypoint alignment. Two rules turn these "
    "links into findings. FACE_REPLACED: two videos with the same footage but different people "
    "(median SFace cosine below 0.363), or one whose face matches a third exhibit far better "
    "than the other's does; the altered one is the video whose face matches that source, and "
    "the frame difference between the two must be concentrated on the face for strong support. "
    "COPY_OF_SYNTHETIC: "
    "a near-duplicate of an exhibit that is SYNTHETIC on its own evidence inherits that support. "
    "Only file-only verdicts are used, so inferences never build on each other."
)
REFERENCE = (
    "SWGDE Best Practices for Image Authentication (comparison with known sources); "
    "Yu et al., 'SFace' (IEEE TIP 2021); Zauner, 'Implementation and benchmarking of perceptual "
    "image hash functions' (2010)"
)
FACE_FOCUS = 2.5  # mean difference on the face ≥ 2.5 × elsewhere = "concentrated on the face"
SOURCE_MARGIN = 0.25  # the face source must beat the other video's face by this cosine


def matched_frames(
    path_a: Path, path_b: Path, n: int = 3, search: int = 3
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """n frames of A (evenly spaced) and, for each, the frame of B within ±search frames of the
    same relative position that matches it best overall (so a one-frame offset between two
    copies of the footage does not show up as motion on the face)."""
    import cv2

    if n <= 0:
        return [], []

    def small(x: np.ndarray) -> np.ndarray:
        return cv2.resize(x, (128, 72), interpolation=cv2.INTER_AREA).astype(np.float32)

    ca, cb = cv2.VideoCapture(str(path_a)), cv2.VideoCapture(str(path_b))
    try:
        na, nb = (
            int(ca.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
            int(cb.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
        )
        if na <= 0 or nb <= 0:
            return [], []
        # The ±search window is in A frames; cover the same span of time on B when the two
        # files have very different frame counts (e.g. a 30 fps clip and a 5 fps re-encode).
        span = max(search, round(search * nb / na))
        out_a: list[np.ndarray] = []
        out_b: list[np.ndarray] = []
        for i in range(n):
            ia = int((i + 0.5) / n * na)
            ca.set(cv2.CAP_PROP_POS_FRAMES, ia)
            ok, fa = ca.read()
            if not ok:
                continue
            fa = cv2.cvtColor(fa, cv2.COLOR_BGR2RGB)
            ta = small(fa)
            centre = round(ia * nb / max(na, 1))
            best: tuple[float, np.ndarray] | None = None
            for ib in range(max(0, centre - span), min(nb, centre + span + 1)):
                cb.set(cv2.CAP_PROP_POS_FRAMES, ib)
                ok, fb = cb.read()
                if not ok:
                    continue
                fb = cv2.cvtColor(fb, cv2.COLOR_BGR2RGB)
                d = float(np.abs(small(fb) - ta).mean())
                if best is None or d < best[0]:
                    best = (d, fb)
            if best is not None:
                out_a.append(fa)
                out_b.append(best[1])
        return out_a, out_b
    finally:
        ca.release()
        cb.release()


def file_only(a: EvidenceAnalysis) -> list[TechniqueResult]:
    return [t for t in a.techniques if t.id != TECH_ID]


def file_verdict(kind: Any, a: EvidenceAnalysis) -> Any:
    return decide(kind, file_only(a))


def _linked(links: list[EvidenceLink], a: str, b: str, kind: LinkKind) -> EvidenceLink | None:
    for ln in links:
        if ln.kind == kind and {ln.source, ln.target} == {a, b}:
            return ln
    return None


def face_median(fa: list[list[float]], fb: list[list[float]]) -> float | None:
    """Median SFace cosine between two face-embedding sets.

    When both sets have one embedding per key frame (the engine stores them at the same
    relative positions), compare frame to frame. Otherwise compare every pair and take the
    median.
    """
    if not fa or not fb:
        return None
    try:
        if len(fa) == len(fb):
            cosines = [_cos(x, y) for x, y in zip(fa, fb, strict=True)]
        else:
            cosines = [_cos(x, y) for x in fa for y in fb]
        return float(np.median(cosines))
    except (TypeError, ValueError):  # a malformed embedding is a missing comparison, not a crash
        return None


def faces_of(features: dict[str, dict[str, Any]] | None, evidence_id: str) -> list[list[float]]:
    """Face embeddings stored for an exhibit, tolerating absent features."""
    f = (features or {}).get(evidence_id) or {}
    return f.get("faces") or []


def face_box(rgb: np.ndarray) -> tuple[int, int, int, int] | None:
    """Largest YuNet face as (x, y, w, h) in pixels, or None."""
    import cv2

    from satyapan.video.landmarks import model_dir

    p = model_dir() / YUNET
    if not p.exists():
        return None
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    det = cv2.FaceDetectorYN.create(str(p), "", (bgr.shape[1], bgr.shape[0]), 0.7, 0.3, 20)
    _, faces = det.detect(bgr)
    if faces is None or len(faces) == 0:
        return None
    f = max(faces, key=lambda f: float(f[2] * f[3]))
    return int(f[0]), int(f[1]), int(f[2]), int(f[3])


def face_change(frames_a: list[np.ndarray], frames_b: list[np.ndarray]) -> dict[str, Any] | None:
    """How much of the difference between matching frames lies on the face.

    frames_a[i] and frames_b[i] show the same moment; B is resized to A. The absolute
    difference is smoothed (compression noise) and compared inside the face box (YuNet on A,
    enlarged 1.3x) and outside it. Returns the median ratio over frames and one figure frame.
    """
    import cv2

    ratios: list[float] = []
    shares: list[float] = []
    best: dict[str, Any] | None = None
    for a, b in zip(frames_a, frames_b, strict=False):
        if b.shape[:2] != a.shape[:2]:
            b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
        box = face_box(a) or face_box(b)
        if box is None:
            continue
        d = np.abs(a.astype(np.float32) - b.astype(np.float32)).mean(axis=2)
        d = cv2.GaussianBlur(d, (0, 0), 2.0)
        x, y, w, h = box
        cx, cy = x + w / 2, y + h / 2
        w2, h2 = w * 1.3, h * 1.3
        x0, x1 = max(0, int(cx - w2 / 2)), min(a.shape[1], int(cx + w2 / 2))
        y0, y1 = max(0, int(cy - h2 / 2)), min(a.shape[0], int(cy + h2 / 2))
        mask = np.zeros(d.shape, bool)
        mask[y0:y1, x0:x1] = True
        if mask.all() or not mask.any():
            continue
        inside, outside = float(d[mask].mean()), float(d[~mask].mean())
        ratio = inside / max(outside, 0.25)
        ratios.append(ratio)
        shares.append(float(d[mask].sum() / max(float(d.sum()), 1e-6)))
        if best is None or ratio > best["ratio"]:
            best = {"a": a, "b": b, "d": d, "box": (x0, y0, x1, y1), "ratio": ratio}
    if not ratios or best is None:
        return None
    x0, y0, x1, y1 = best["box"]
    area = (x1 - x0) * (y1 - y0) / float(best["d"].size)
    return {"ratio": float(np.median(ratios)), "share": float(np.median(shares)),
            "box_area": area, "frames": len(ratios), "best": best}  # fmt: skip


def face_change_figure(res: dict[str, Any], label_a: str, label_b: str) -> np.ndarray:
    """[questioned frame | source frame | difference heat map] with the face box."""
    import cv2

    from satyapan.forensics.context import colormap

    b = res["best"]
    x0, y0, x1, y1 = b["box"]
    d = b["d"]
    heat = colormap(np.clip(d / max(float(np.percentile(d, 99.5)), 1.0), 0, 1))
    panels = []
    for img, label in ((b["a"], label_a), (b["b"], label_b), (heat, "difference")):
        p = np.ascontiguousarray(img.copy())
        cv2.rectangle(p, (x0, y0), (x1, y1), (34, 211, 238), max(2, p.shape[1] // 240))
        scale = 420 / p.shape[0]
        p = cv2.resize(p, (round(p.shape[1] * scale), 420), interpolation=cv2.INTER_AREA)
        cv2.putText(p, label[:28], (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        panels.append(p)
    return np.concatenate(panels, axis=1)


def infer(
    evidence: list[LabEvidence],
    analyses: dict[str, EvidenceAnalysis],
    features: dict[str, dict[str, Any]],
    links: list[EvidenceLink],
    paths: dict[str, Path],
    artifact_dir: Callable[[str], Path],
) -> dict[str, tuple[list[Finding], list[Artifact]]]:
    """Case findings per evidence id (only ids that get at least one finding)."""
    from PIL import Image

    features = features or {}
    paths = paths or {}
    ev = {e.id: e for e in evidence if e.id in analyses}
    tag = {e.id: f"{e.exhibit} ({e.filename})" for e in ev.values()}
    own = {i: file_verdict(e.kind, analyses[i]) for i, e in ev.items()}
    out: dict[str, tuple[list[Finding], list[Artifact]]] = {}

    def add(eid: str, f: Finding, art: Artifact | None = None) -> None:
        f.technique = TECH_ID
        fs, arts = out.setdefault(eid, ([], []))
        fs.append(f)
        if art is not None:
            arts.append(art)

    ids = sorted(ev, key=lambda i: ev[i].exhibit)
    # ---------------------------------------------------------------- FACE_REPLACED
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if not (ev[a].kind.value == ev[b].kind.value == "video"):
                continue
            nd = _linked(links, a, b, LinkKind.NEAR_DUPLICATE)
            fa, fb = faces_of(features, a), faces_of(features, b)
            if nd is None or not fa or not fb:
                continue
            s_ab = face_median(fa, fb)
            if s_ab is None:
                continue
            different = s_ab < SFACE_DIFFERENT

            def source_candidates(
                side: str, other: str, own_similarity: float
            ) -> list[tuple[str, float, float]]:
                """Third exhibits that can be the face source of `side`: a SAME_FACE link, a
                solid median match to `side`, no match to `other`, and a clear margin over the
                two videos' own similarity."""
                side_faces = faces_of(features, side)
                other_faces = faces_of(features, other)
                found: list[tuple[str, float, float]] = []
                for p in ids:
                    if p in (side, other) or not _linked(links, side, p, LinkKind.SAME_FACE):
                        continue
                    c_side = face_median(side_faces, faces_of(features, p))
                    c_other = face_median(other_faces, faces_of(features, p))
                    if c_side is None or c_other is None:
                        continue
                    if (c_side >= SFACE_SAME and c_other < SFACE_DIFFERENT
                            and c_side - own_similarity >= SOURCE_MARGIN):  # fmt: skip
                        found.append((p, c_side, c_other))
                return found

            src_a, src_b = source_candidates(a, b, s_ab), source_candidates(b, a, s_ab)
            if not different and not (src_a or src_b):
                continue  # no reason to call this a face replacement
            if src_a and not src_b:
                alt, orig, src = a, b, src_a
            elif src_b and not src_a:
                alt, orig, src = b, a, src_b
            elif not different:
                continue  # both sides have a source; their faces are not different
            else:
                roles = {ev[a].role.value, ev[b].role.value}
                if roles == {"questioned", "reference"}:
                    alt = a if ev[a].role.value == "questioned" else b
                    orig, src = (b if alt == a else a), []
                else:
                    for x, y in ((a, b), (b, a)):
                        add(x, info("SAME_FOOTAGE_OTHER_FACE",
                                    f"Same footage as {ev[y].exhibit}, but a different face",
                                    f"The key frames match {tag[y]} ({nd.detail.split(':')[0]}) "
                                    f"while the median SFace cosine over matched frames is "
                                    f"{s_ab:.2f} < {SFACE_DIFFERENT} (standard same-identity "
                                    "point 0.363). One of the two had its face replaced; the case "
                                    "holds no third exhibit that shows which.",
                                    Category.SYNTHETIC, peer=y, face_cosine=round(s_ab, 3)))  # fmt: skip
                    continue
            path_alt, path_orig = paths.get(alt), paths.get(orig)
            change = None
            if path_alt is not None and path_orig is not None:
                try:
                    change = face_change(*matched_frames(path_alt, path_orig, 3))
                except Exception:  # noqa: BLE001 - localisation is a corroboration, best effort
                    change = None
            focused = change is not None and change["ratio"] >= FACE_FOCUS
            n_corr = int(bool(src)) + int(focused)
            strength = (Strength.STRONG if n_corr == 2 else Strength.MODERATE if n_corr == 1
                        else Strength.WEAK)  # fmt: skip
            art = None
            if change is not None:
                name = f"face_change_vs_{orig}.jpg"
                try:
                    fig = face_change_figure(change, ev[alt].exhibit, ev[orig].exhibit)
                    Image.fromarray(fig).save(artifact_dir(alt) / name, quality=88)
                    art = Artifact(name=name, kind="figure",
                                   title=f"Frame comparison with {ev[orig].exhibit}",
                                   caption=f"Same moment in {tag[alt]} and {tag[orig]}; the "
                                   f"difference map is {change['ratio']:.1f}× stronger on the face "
                                   "(box) than elsewhere.")  # fmt: skip
                except OSError:  # a figure that cannot be written must not lose the finding
                    art = None
            src_txt = (
                " The face matches "
                + ", ".join(
                    f"{tag[p]} (median SFace cosine {c_side:.2f}; the faces in {tag[orig]} "
                    f"score {c_other:.2f} against it)"
                    for p, c_side, c_other in src
                )
                + ": that exhibit is the likely face source."
                if src
                else ""
            )
            if different:
                face_txt = (
                    f"The key frames match {tag[orig]} ({nd.detail.split(':')[0]}), yet the "
                    f"median SFace cosine over matched frames is {s_ab:.2f} < {SFACE_DIFFERENT} "
                    "(standard same-identity point 0.363): the same recording shows two "
                    "different people."
                )
            else:
                face_txt = (
                    f"The key frames match {tag[orig]} ({nd.detail.split(':')[0]}); the median "
                    f"SFace cosine over matched frames is {s_ab:.2f} (standard same-identity "
                    "point 0.363), but the face matches a third exhibit far more closely than it "
                    "matches the other video."
                )
            loc_txt = (f" Between the two videos the frame difference is {change['ratio']:.1f}× "
                       f"stronger on the face than on the rest of the picture ({change['share']:.0%} "
                       f"of all change falls in a box covering {change['box_area']:.0%} of the frame)."
                       if change is not None else "")  # fmt: skip
            add(alt, finding(
                "FACE_REPLACED",
                f"Face replaced: footage of {ev[orig].exhibit} with another person's face",
                f"{face_txt}{src_txt}{loc_txt} This is the signature of a face-swap deepfake "
                "made from that footage.",
                Hypothesis.SYNTHETIC, strength, Category.SYNTHETIC,
                original=orig, face_sources=[p for p, _, _ in src],
                face_cosine=round(s_ab, 3),
                face_source_cosines={p: round(c_side, 3) for p, c_side, _ in src},
                face_source_original_cosines={p: round(c_other, 3) for p, _, c_other in src},
                face_focus=round(change["ratio"], 2) if change else None,
            ), art)  # fmt: skip
            add(orig, info("FOOTAGE_REUSED", f"This footage reappears in {ev[alt].exhibit} with "
                           "another face",
                           f"{tag[alt]} shows the same frames with a different person's face: this "
                           "exhibit is consistent with being the source footage of that deepfake.",
                           Category.PROVENANCE, altered=alt))  # fmt: skip
            for p, c_side, c_other in src:
                add(p, info("FACE_SOURCE", f"Its face appears in {ev[alt].exhibit}",
                            f"The face in this exhibit matches the replaced face in {tag[alt]} "
                            f"(median SFace cosine {c_side:.2f}), while the face in {tag[orig]} "
                            f"does not (median {c_other:.2f}): consistent with being the source "
                            "image of the face swap.",
                            Category.PROVENANCE, altered=alt))  # fmt: skip
    # ---------------------------------------------------------------- COPY_OF_SYNTHETIC
    for a in ids:
        if ev[a].kind.value != "image" or own[a].label == VerdictLabel.SYNTHETIC:
            continue
        for b in ids:
            if b == a or ev[b].kind.value != "image" or own[b].label != VerdictLabel.SYNTHETIC:
                continue
            nd = _linked(links, a, b, LinkKind.NEAR_DUPLICATE)
            sc = _linked(links, a, b, LinkKind.SHARES_CONTENT)
            if nd is None or (sc is not None and "region(s) differ" in sc.detail):
                continue
            strength = Strength.STRONG if own[b].risk_index >= 88 else Strength.MODERATE
            add(a, finding(
                "COPY_OF_SYNTHETIC",
                f"Copy of a synthetic picture ({ev[b].exhibit})",
                f"This picture is the same as {tag[b]} ({nd.detail.split(':')[0].lower()}), "
                "with no region changed. That exhibit's own analysis is SYNTHETIC "
                f"({own[b].confidence}: {'; '.join(r.split('] ', 1)[-1] for r in own[b].rationale[:2])}). "
                "Re-sharing removed the metadata and Content Credentials, not the content.",
                Hypothesis.SYNTHETIC, strength, Category.PROVENANCE, original=b,
            ))  # fmt: skip
            break
    return out


def case_result(findings: list[Finding], artifacts: list[Artifact]) -> TechniqueResult:
    n = sum(1 for f in findings if f.strength > Strength.NONE)
    return TechniqueResult(
        id=TECH_ID, name=TECH_NAME, category=Category.PROVENANCE, status=Status.OK,
        summary=(f"{n} cross-exhibit finding(s)" if n else "cross-exhibit context noted"),
        method=METHOD, reference=REFERENCE, findings=findings, artifacts=artifacts,
        limitations="Depends on the exhibits in the case: an original or a source that was not "
        "seized cannot be compared.",
    )  # fmt: skip


def with_case_findings(
    a: EvidenceAnalysis, findings: list[Finding], artifacts: list[Artifact]
) -> EvidenceAnalysis:
    """A copy of the analysis whose case technique and verdict reflect these findings."""
    techs = file_only(a) + ([case_result(findings, artifacts)] if findings else [])
    b = a.model_copy(deep=True)
    b.techniques = techs
    b.verdict = decide(a.media.kind, techs)
    return b


def signature(a: EvidenceAnalysis | None) -> list[tuple[str, str, int]]:
    if a is None:
        return []
    t = next((t for t in a.techniques if t.id == TECH_ID), None)
    return sorted((f.code, f.title, int(f.strength)) for f in (t.findings if t else []))
