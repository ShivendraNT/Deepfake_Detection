"""Cross-evidence links: which exhibits share a source, a device, a voice or a face.

Per evidence we keep small features (perceptual hashes, face and speaker embeddings, device
and generator strings); links are recomputed whenever an item finishes analysis. For two
images that share content, the newer one is aligned onto the other (SIFT + RANSAC homography)
and the difference map shows exactly what changed — the derivation of a forgery from its
source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from satyapan.forensics.models import EvidenceLink, LinkKind

YUNET = "face_detection_yunet_2023mar.onnx"
SFACE_SAME = 0.45  # stricter than OpenCV's LFW operating point (0.363): links must be solid
SPEAKER_SAME = (
    0.55  # WeSpeaker ResNet34 cosine; docs/forensics/VALIDATION.md (different speakers <= 0.45)
)


def phash(gray: np.ndarray) -> str:
    import cv2

    small = cv2.resize(gray.astype(np.float32), (32, 32), interpolation=cv2.INTER_AREA)
    d = cv2.dct(small)[:8, :8].flatten()
    med = np.median(d[1:])
    bits = "".join("1" if v > med else "0" for v in d)
    return f"{int(bits, 2):016x}"


def dhash(gray: np.ndarray) -> str:
    import cv2

    small = cv2.resize(gray.astype(np.float32), (9, 8), interpolation=cv2.INTER_AREA)
    bits = "".join("1" if v else "0" for v in (small[:, 1:] > small[:, :-1]).flatten())
    return f"{int(bits, 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def face_embeddings(rgb: np.ndarray, models: Any, max_faces: int = 3) -> list[list[float]]:
    """SFace embeddings (128-d) of the largest faces, aligned with YuNet landmarks."""
    import cv2

    from satyapan.video.landmarks import model_dir

    det_path = model_dir() / YUNET
    if not det_path.exists():
        return []
    try:
        rec = models.get("face_id")
    except Exception:  # noqa: BLE001 - optional model
        return []
    h, w = rgb.shape[:2]
    scale = min(1.0, 1280 / max(h, w))
    img = rgb if scale == 1.0 else cv2.resize(rgb, (round(w * scale), round(h * scale)))
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    det = cv2.FaceDetectorYN.create(str(det_path), "", (bgr.shape[1], bgr.shape[0]), 0.7, 0.3, 50)
    _, faces = det.detect(bgr)
    if faces is None:
        return []
    out = []
    with models.lock("face_id_run"):
        for f in sorted(faces, key=lambda f: -float(f[2] * f[3]))[:max_faces]:
            if min(f[2], f[3]) < 48:
                continue
            aligned = rec.alignCrop(bgr, f)
            feat = rec.feature(aligned).reshape(-1)
            out.append([round(float(v), 5) for v in feat / (np.linalg.norm(feat) + 1e-9)])
    return out


def _cos(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a), np.asarray(b)
    return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))


def plausible_homography(
    H: np.ndarray, src_shape: tuple[int, ...], dst_shape: tuple[int, ...]
) -> bool:
    """Reject degenerate fits that RANSAC produces between unrelated images: extreme scale,
    reflection, strong perspective, or a source that maps onto a sliver."""
    import cv2

    A = H[:2, :2]
    det = float(np.linalg.det(A))
    if not 0.05 < abs(det) < 20 or det < 0:
        return False
    if abs(H[2, 0]) > 2e-3 or abs(H[2, 1]) > 2e-3:
        return False
    h, w = src_shape[:2]
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    proj = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    area = abs(cv2.contourArea(proj.astype(np.float32)))
    dh, dw = dst_shape[:2]
    return area > 0.04 * dh * dw and cv2.isContourConvex(proj.astype(np.float32))


def shared_content(a_rgb: np.ndarray, b_rgb: np.ndarray) -> dict[str, Any] | None:
    """Align b onto a with SIFT + RANSAC; return inliers, the warped b and a difference map."""
    import cv2

    def prep(x: np.ndarray) -> tuple[np.ndarray, float]:
        s = min(1.0, 1200 / max(x.shape[:2]))
        return (x if s == 1.0 else cv2.resize(x, (round(x.shape[1] * s), round(x.shape[0] * s)),
                                              interpolation=cv2.INTER_AREA)), s  # fmt: skip

    a, _ = prep(a_rgb)
    b, _ = prep(b_rgb)
    ga, gb = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    sift = cv2.SIFT_create(nfeatures=4000)
    ka, da = sift.detectAndCompute(ga, None)
    kb, db = sift.detectAndCompute(gb, None)
    if da is None or db is None or len(ka) < 20 or len(kb) < 20:
        return None
    knn = cv2.BFMatcher(cv2.NORM_L2).knnMatch(db, da, k=2)
    good = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 20:
        return None
    src = np.float32([kb[m.queryIdx].pt for m in good])
    dst = np.float32([ka[m.trainIdx].pt for m in good])
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None or mask is None:
        return None
    inl = int(mask.sum())
    if inl < 30 or inl / len(good) < 0.25 or not plausible_homography(H, gb.shape, ga.shape):
        return None
    warped = cv2.warpPerspective(b, H, (a.shape[1], a.shape[0]))
    valid = cv2.warpPerspective(np.ones(gb.shape, np.uint8), H, (a.shape[1], a.shape[0])) > 0
    diff = np.abs(a.astype(np.float32) - warped.astype(np.float32)).mean(axis=2)
    diff = cv2.GaussianBlur(diff, (0, 0), 2.0)
    diff[~valid] = 0
    vals = diff[valid] if valid.any() else diff.ravel()
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) * 1.4826 + 1e-3
    thr = max(15.0, med + 8.0 * mad)  # robust: edits can cover more than 1% of the picture
    mask_c = (diff > thr).astype(np.uint8)
    mask_c = cv2.morphologyEx(mask_c, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask_c)
    boxes = []
    H_, W_ = mask_c.shape
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area > 0.0015 * H_ * W_:
            boxes.append(
                {"x": x / W_, "y": y / H_, "w": w / W_, "h": h / H_, "area": area / (H_ * W_)}
            )
    boxes.sort(key=lambda r: -r["area"])
    overlap = float(valid.mean())
    return {"inliers": inl, "matches": len(good), "overlap": overlap, "a": a, "warped": warped,
            "diff": diff, "boxes": boxes[:6], "changed_frac": float(mask_c.mean())}  # fmt: skip


def diff_figure(res: dict[str, Any]) -> np.ndarray:
    import cv2

    from satyapan.forensics.context import colormap

    a, w, d = res["a"], res["warped"], res["diff"]
    heat = colormap(np.clip(d / 60.0, 0, 1), "inferno")
    marked = a.copy()
    H, W = a.shape[:2]
    for b in res["boxes"]:
        x0, y0 = int(b["x"] * W), int(b["y"] * H)
        cv2.rectangle(
            marked, (x0, y0), (x0 + int(b["w"] * W), y0 + int(b["h"] * H)), (255, 40, 40), 3
        )
    sep = np.full((H, 6, 3), 255, np.uint8)
    return np.concatenate([marked, sep, w, sep, heat], axis=1)


def compute_links(me: dict[str, Any], peers: list[dict[str, Any]], artifact_dir: Path,
                  load_rgb: Any) -> list[EvidenceLink]:  # fmt: skip
    """me / peers: {"id", "exhibit", "kind", "features": {...}}."""
    from PIL import Image

    out: list[EvidenceLink] = []
    fm = me.get("features") or {}
    for p in peers:
        fp = p.get("features") or {}
        pid, pex = p["id"], p.get("exhibit", p["id"])
        if fm.get("phash") and fp.get("phash"):
            d = min(hamming(fm["phash"], fp["phash"]), 64)
            if d <= 10:
                if "video" in (me["kind"], p["kind"]):
                    what = (f"the key frames show the same scene as {pex}: the same footage, "
                            "possibly with the face or the audio replaced.")  # fmt: skip
                else:
                    what = f"the same picture as {pex}, re-encoded, resized or lightly edited."
                out.append(EvidenceLink(source=me["id"], target=pid, kind=LinkKind.NEAR_DUPLICATE,
                                        score=round(1 - d / 64, 3),
                                        detail=f"Perceptual hashes differ in {d}/64 bits: {what}"))  # fmt: skip
        if me["kind"] == "image" and p["kind"] == "image" and fm.get("phash") and fp.get("phash"):
            try:
                res = shared_content(load_rgb(pid), load_rgb(me["id"]))
            except Exception:  # noqa: BLE001 - comparison is best effort
                res = None
            if res and res["overlap"] > 0.2:
                name = f"diff_vs_{pid}.jpg"
                Image.fromarray(diff_figure(res)).save(artifact_dir / name, quality=88)
                where = ", ".join(
                    f"{b['x'] * 100:.0f}%/{b['y'] * 100:.0f}%" for b in res["boxes"][:3]
                )
                detail = (f"{res['inliers']} matching keypoints align this item onto {pex} "
                          f"({res['overlap']:.0%} overlap). "
                          + (f"After alignment {len(res['boxes'])} region(s) differ (at {where} "
                             f"of {pex}): content was changed there."
                             if res["boxes"] else "After alignment the content is the same."))  # fmt: skip
                out.append(EvidenceLink(source=me["id"], target=pid, kind=LinkKind.SHARES_CONTENT,
                                        score=round(min(1.0, res["inliers"] / 200), 3),
                                        detail=detail, artifacts=[name]))  # fmt: skip
        for fa in fm.get("faces", [])[:3]:
            best = max((_cos(fa, fb) for fb in fp.get("faces", [])[:3]), default=-1.0)
            if best >= SFACE_SAME:
                out.append(EvidenceLink(source=me["id"], target=pid, kind=LinkKind.SAME_FACE,
                                        score=round(best, 3),
                                        detail=f"A face here matches a face in {pex} (SFace "
                                        f"cosine {best:.2f} ≥ {SFACE_SAME}): the same person's "
                                        "face, or a deepfake built from it."))  # fmt: skip
                break
        if fm.get("speaker") and fp.get("speaker"):
            c = _cos(fm["speaker"], fp["speaker"])
            if c >= SPEAKER_SAME:
                out.append(EvidenceLink(source=me["id"], target=pid, kind=LinkKind.SAME_SPEAKER,
                                        score=round(c, 3),
                                        detail=f"Voices match (speaker-embedding cosine {c:.2f} ≥ "
                                        f"{SPEAKER_SAME}): the same speaker as {pex}, or a "
                                        "clone of that speaker's voice."))  # fmt: skip
        if fm.get("device") and fm.get("device") == fp.get("device"):
            out.append(EvidenceLink(source=me["id"], target=pid, kind=LinkKind.SAME_DEVICE,
                                    score=1.0, detail=f"Both name the device “{fm['device']}”."))  # fmt: skip
        if fm.get("generator") and fm.get("generator") == fp.get("generator"):
            out.append(EvidenceLink(source=me["id"], target=pid, kind=LinkKind.SAME_GENERATOR,
                                    score=1.0, detail=f"Both carry the signature of "
                                    f"{fm['generator']}."))  # fmt: skip
    return out
