"""Image techniques backed by trained models or embedded signals: the Stable Diffusion
invisible watermark, the AI-generated image classifier and the face-swap (GenD) check."""

from __future__ import annotations

from typing import Any

import numpy as np

from satyapan.forensics.base import Technique, Unavailable, finding, info, make_result
from satyapan.forensics.context import AnalysisContext, overlay
from satyapan.forensics.image import watermark as wm
from satyapan.forensics.models import (
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Region,
    Status,
    Strength,
    TechniqueResult,
)

IMG = (MediaKind.IMAGE,)


# ---------------------------------------------------------------------------------------------
# Invisible watermark
# ---------------------------------------------------------------------------------------------


def run_watermark(ctx: AnalysisContext) -> TechniqueResult:
    t = WATERMARK
    rgb = np.asarray(ctx.pil(), dtype=np.uint8)  # full resolution: the mark lives in the pixels
    if min(rgb.shape[:2]) < 256:
        return make_result(t, summary="image smaller than 256 px", status=Status.SKIPPED)
    matches = wm.check(rgb)
    data = {m.name: {"bits": m.bits, "matching": m.matching, "accuracy": round(m.accuracy, 3),
                     "p_chance": m.p_chance} for m in matches}  # fmt: skip
    hits = [m for m in matches if m.accuracy >= 0.85 and m.p_chance < 1e-6]
    findings: list[Finding] = []
    for m in hits:
        findings.append(
            finding(
                "SD_WATERMARK",
                f"Invisible watermark: {m.name}",
                f"{m.matching} of {m.bits} watermark bits match the message that "
                f"{m.name} embeds in every image it generates (chance of this on an "
                f"unmarked image: {m.p_chance:.1e}). This supports generation by that "
                "pipeline, and shows the file was not resized or heavily re-compressed since. "
                "A watermark can in principle be copied onto another image, so it is strong "
                "support, not proof.",
                Hypothesis.SYNTHETIC,
                Strength.STRONG,
                Category.PROVENANCE,
                score=round(m.accuracy, 3),
                generator=m.name,
                bits=m.bits,
                matching=m.matching,
            )  # fmt: skip
        )
    best = max(matches, key=lambda m: m.accuracy) if matches else None
    if hits:
        summary = f"{hits[0].name} watermark decoded ({hits[0].matching}/{hits[0].bits} bits)"
    else:
        summary = "no known generator watermark" + (
            f" (best {best.accuracy:.0%} bit agreement ≈ chance)" if best else "")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# AI-generated image classifier
# ---------------------------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def run_aigen(ctx: AnalysisContext) -> TechniqueResult:
    t = AIGEN
    try:
        model = ctx.models.get("aigen")
    except Unavailable as exc:
        return make_result(t, summary=str(exc), status=Status.UNAVAILABLE)
    img = ctx.pil()
    if min(img.size) < 64:
        return make_result(t, summary="image too small for the model", status=Status.SKIPPED)
    if float(ctx.gray(512).std()) < 3.0:  # blank / near-uniform: outside the model's domain
        return make_result(t, summary="image is nearly uniform (no content to judge)",
                           status=Status.SKIPPED)  # fmt: skip
    logit, per_view = model.logit(img)
    spec = model.spec
    tau_hi, tau_lo = float(spec["tau_hi"]), float(spec["tau_lo"])
    p = _sigmoid(logit)
    metrics = spec.get("metrics", {})
    data = {"logit": round(logit, 3), "probability": round(p, 4), "views": per_view,
            "tau_hi": tau_hi, "tau_lo": tau_lo, "model": spec.get("name"),
            "model_license": spec.get("license"), "metrics": metrics}  # fmt: skip
    tpr_hi = float(metrics.get("test_tpr_at_tau_hi", 0.5))
    fpr_hi = max(float(metrics.get("test_fpr_at_tau_hi", spec.get("fpr_at_tau_hi", 0.01))), 1e-3)
    tpr_lo = float(metrics.get("test_tpr_at_tau_lo", 0.65))
    fpr_lo = max(float(metrics.get("test_fpr_at_tau_lo", spec.get("fpr_at_tau_lo", 0.05))), 1e-3)
    data["likelihood_ratio_strict"] = round(tpr_hi / fpr_hi, 1)
    data["likelihood_ratio_lenient"] = round(tpr_lo / fpr_lo, 1)
    findings: list[Finding] = []
    if logit >= tau_hi:
        findings.append(
            finding(
                "AI_IMAGE_CLASSIFIER",
                "AI-generated image classifier: above its strict threshold",
                f"The {spec.get('name')} classifier (trained on images from thousands of "
                "generators) scores this image above its strict threshold. On held-out test "
                f"images that threshold flagged {tpr_hi:.0%} of AI-generated images and "
                f"{fpr_hi:.1%} of real photographs (likelihood ratio ≈ {tpr_hi / fpr_hi:.0f}): "
                "moderate support on its own. It reads statistical traces generators leave in "
                "the pixels, independently of metadata.",
                Hypothesis.SYNTHETIC,
                Strength.MODERATE,
                Category.SYNTHETIC,
                score=round(p, 4),
                logit=round(logit, 3),
            )  # fmt: skip
        )
    elif logit >= tau_lo:
        findings.append(
            finding(
                "AI_IMAGE_CLASSIFIER",
                "AI-generated image classifier: above its lenient threshold",
                f"Above the lenient threshold (held-out: {tpr_lo:.0%} of AI images and "
                f"{fpr_lo:.1%} of real photos flagged, likelihood ratio ≈ {tpr_lo / fpr_lo:.0f}) "
                "but below the strict one: weak support. Heavy compression and filters can also "
                "raise the score.",
                Hypothesis.SYNTHETIC,
                Strength.WEAK,
                Category.SYNTHETIC,
                score=round(p, 4),
                logit=round(logit, 3),
            )  # fmt: skip
        )
    else:
        findings.append(
            info(
                "AI_IMAGE_CLASSIFIER_LOW",
                "AI-generated image classifier: below its thresholds",
                "Generators the model never saw can still pass, so this is not a proof of "
                "authenticity.",
                Category.SYNTHETIC,
                score=round(p, 4),
            )  # fmt: skip
        )
    level = "strict" if logit >= tau_hi else "lenient" if logit >= tau_lo else "no"
    summary = (f"classifier score {logit:+.2f} (uncalibrated); above {level} threshold" if level != "no"
               else f"classifier score {logit:+.2f}: below both thresholds")  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# Faces: face-swap / synthetic face model (GenD), every face in the picture
# ---------------------------------------------------------------------------------------------

MAX_FACES = 4
MIN_FACE_PX = 64.0


def detect_faces(tracker: Any, rgb: np.ndarray) -> list[np.ndarray]:
    """Landmarks (478x2) for up to MAX_FACES faces, largest first (YuNet + Face Landmarker)."""
    import cv2

    h, w = rgb.shape[:2]
    scale = min(1.0, 960 / max(h, w))
    small = rgb if scale == 1.0 else cv2.resize(rgb, (max(1, round(w * scale)),
                                                      max(1, round(h * scale))))  # fmt: skip
    sh, sw = small.shape[:2]
    tracker._yunet.setInputSize((sw, sh))
    _, faces = tracker._yunet.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
    out: list[np.ndarray] = []
    if faces is None:
        return out
    faces = sorted(faces, key=lambda f: -float(f[2] * f[3]))[:MAX_FACES]
    for f in faces:
        x, y, bw, bh = (float(v) / scale for v in f[:4])
        roi = (x + bw / 2, y + bh / 2, max(bw, bh) * 2.0)
        obs = tracker._landmarks(rgb, roi)
        if obs is not None:
            out.append(np.asarray(obs.pts))
    return out


def occlusion_map(scorer: Any, crop: np.ndarray, base: float, grid: int = 4) -> np.ndarray:
    """How much the fake-logit drops when each cell of the face crop is greyed out."""
    s = crop.shape[0] // grid
    batch = []
    for i in range(grid):
        for j in range(grid):
            c = crop.copy()
            c[i * s : (i + 1) * s, j * s : (j + 1) * s] = 127
            batch.append(c)
    logits = scorer.logits(np.stack(batch), batch=16)
    drop = np.maximum(base - logits.reshape(grid, grid), 0.0)
    return drop / (drop.max() + 1e-6)


def run_faces(ctx: AnalysisContext) -> TechniqueResult:
    t = FACES
    try:
        face = ctx.models.get("face_cnn")
    except Unavailable as exc:
        return make_result(t, summary=str(exc), status=Status.UNAVAILABLE)
    from satyapan.video.observe import face_crop

    rgb = ctx.rgb(1920)
    tracker = face["tracker"]()
    try:
        all_pts = detect_faces(tracker, rgb)
    finally:
        tracker.close()
    thr = face["thresholds"]
    scorer = face["scorer"]
    if not all_pts:
        return make_result(t, summary="no face found", status=Status.SKIPPED,
                           data={"faces": 0})  # fmt: skip
    H, W = rgb.shape[:2]
    findings: list[Finding] = []
    faces_data = []
    artifacts = []
    crops = []
    usable = []
    for pts in all_pts:
        size = float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))
        if size < MIN_FACE_PX:
            faces_data.append({"face_px": round(size, 1), "problem": "face too small"})
            continue
        crops.append(face_crop(rgb, pts))
        usable.append((pts, size))
    if crops:
        with ctx.models.lock("face_cnn_run"):
            logits = scorer.logits(np.stack(crops))
    else:
        logits = np.zeros(0)
    for k, ((pts, size), crop, lg) in enumerate(zip(usable, crops, logits, strict=True)):
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
        reg = Region(x=round(max(0, x0) / W, 4), y=round(max(0, y0) / H, 4),
                     w=round((x1 - x0) / W, 4), h=round((y1 - y0) / H, 4),
                     label=f"face {k + 1}", score=round(float(lg), 2))  # fmt: skip
        lg = float(lg)
        level = "high" if lg >= thr.tau_hi else "elevated" if lg >= thr.tau_lo else "low"
        names = [f"face_{k + 1}"]
        if lg >= thr.tau_lo:
            with ctx.models.lock("face_cnn_run"):
                heat = occlusion_map(scorer, crop, lg)
            import cv2

            hm = cv2.resize(heat.astype(np.float32), (224, 224), interpolation=cv2.INTER_CUBIC)
            ov = overlay(crop, hm, alpha=0.6, cmap="jet")
            pair = np.concatenate([crop, np.full((224, 4, 3), 255, np.uint8), ov], axis=1)
            art = ctx.save_png(f"face_{k + 1}", pair, "crop", f"Face {k + 1}: crop and saliency",
                               "Left: the face as the model sees it. Right: regions whose "
                               "removal lowers the deepfake score most (red = most influential).")  # fmt: skip
        else:
            art = ctx.save_png(f"face_{k + 1}", crop, "crop", f"Face {k + 1}")
        artifacts.append(art)
        names = [art.name]
        faces_data.append({"face_px": round(size, 1), "logit": round(lg, 3), "level": level,
                           "box": reg.model_dump()})  # fmt: skip
        if lg >= thr.tau_hi:
            findings.append(
                finding(
                    "FACE_SWAP",
                    f"Face {k + 1}: manipulated-face model score high",
                    f"The GenD face model (CLIP ViT-L/14, trained on face-swap and "
                    f"re-enactment fakes) scores this face {lg:.2f}, above its strict "
                    f"threshold {thr.tau_hi:.2f} (1% false alarms on real faces in "
                    "validation; photo crops: AUC 0.92 on FaceForensics++, so a single photo "
                    "hit is moderate support). The face shows blending or synthesis artefacts "
                    "typical of a face swap.",
                    Hypothesis.SYNTHETIC,
                    Strength.MODERATE,
                    Category.SYNTHETIC,
                    score=round(lg, 3),
                    regions=[reg],
                    artifacts=names,
                    face=k + 1,
                )  # fmt: skip
            )
        elif lg >= thr.tau_lo:
            findings.append(
                finding(
                    "FACE_SWAP",
                    f"Face {k + 1}: manipulated-face model score elevated",
                    f"Score {lg:.2f} is between the lenient ({thr.tau_lo:.2f}, 5% false "
                    f"alarms) and strict ({thr.tau_hi:.2f}) thresholds: weak support.",
                    Hypothesis.SYNTHETIC,
                    Strength.WEAK,
                    Category.SYNTHETIC,
                    score=round(lg, 3),
                    regions=[reg],
                    artifacts=names,
                    face=k + 1,
                )  # fmt: skip
            )
        else:
            findings.append(
                info(
                    "FACE_CHECKED",
                    f"Face {k + 1}: no face-swap indication",
                    f"Score {lg:.2f} is below the lenient threshold {thr.tau_lo:.2f}.",
                    Category.SYNTHETIC,
                    regions=[reg],
                    score=round(lg, 3),
                )  # fmt: skip
            )
    data = {"faces": faces_data, "tau_hi": thr.tau_hi, "tau_lo": thr.tau_lo,
            "model": thr.model_file, "calibrated_on": "FF++ c23 validation real faces"}  # fmt: skip
    n_hi = sum(1 for f in faces_data if f.get("level") == "high")
    summary = f"{len(all_pts)} face(s); {n_hi} with a high deepfake score"
    if not crops:
        return make_result(t, summary="faces too small to judge", status=Status.SKIPPED,
                           data=data)  # fmt: skip
    return make_result(t, summary=summary, findings=findings, data=data, artifacts=artifacts)


WATERMARK = Technique(
    "image.watermark", "Generator watermark (Stable Diffusion)", Category.PROVENANCE, IMG,
    run_watermark,
    "The DWT-DCT invisible watermark used by Stability AI's reference code and Hugging Face "
    "diffusers (SDXL) is decoded from the U channel's Haar approximation band (4×4 blocks) and "
    "compared bit by bit with each generator's known message; the binomial chance probability "
    "of the observed agreement is reported.",
    "ShieldMnt invisible-watermark (MIT); diffusers StableDiffusionXLWatermarker",
    "Resizing, cropping or strong re-compression erase this watermark; most other generators "
    "use different or proprietary marks (e.g. Google SynthID) that cannot be read offline.",
    order=6,
)  # fmt: skip
AIGEN = Technique(
    "image.aigen", "AI-generated image classifier", Category.SYNTHETIC, IMG, run_aigen,
    "A deep classifier trained to separate camera photographs from images made by diffusion "
    "and GAN generators scores the whole image (plus a native-resolution centre crop for large "
    "images). The two thresholds are the scores exceeded by only 1% and 5% of real "
    "photographs in a held-out validation set.",
    "Model card in config/aigen_model.json; selection protocol in docs/forensics/VALIDATION.md",
    "Generators released after the model was trained may evade it; screenshots and heavy "
    "compression shift scores.", order=30,
)  # fmt: skip
FACES = Technique(
    "image.faces", "Face-swap / synthetic face detector", Category.SYNTHETIC, IMG, run_faces,
    "Every face (up to four) is located with YuNet and MediaPipe Face Landmarker, cropped to "
    "224 px with context, and scored by GenD (CLIP ViT-L/14 with tuned layer norms, WACV 2026). "
    "Thresholds are the 1% and 5% false-alarm points on real faces from FaceForensics++ "
    "validation videos. For suspicious faces an occlusion map shows which regions drove the "
    "score.",
    "Yermakov et al., 'Deepfake Detection that Generalizes Across Benchmarks' (GenD, WACV 2026)",
    "Trained on face swaps and re-enactment; fully generated portraits are covered by the "
    "AI-image classifier instead. Faces under 64 px are not judged.", order=31,
)  # fmt: skip
