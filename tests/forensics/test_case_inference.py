"""Cross-exhibit inferences (satyapan.forensics.inference): face replacement and copies of
synthetic pictures, plus the service pass that re-decides verdicts and logs custody."""

from __future__ import annotations

import io
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from satyapan.forensics import inference
from satyapan.forensics.models import (
    Category,
    EvidenceAnalysis,
    EvidenceLink,
    EvidenceStatus,
    Hashes,
    Hypothesis,
    LabEvidence,
    LinkKind,
    MediaInfo,
    MediaKind,
    Status,
    Strength,
    TechniqueResult,
)
from satyapan.forensics.service import LabService
from satyapan.forensics.store import LabStore
from satyapan.forensics.verdict import decide
from tests.forensics.conftest import StubModels, png, textured

NOW = datetime(2026, 10, 21, tzinfo=UTC)
FACE_A = [1.0] + [0.0] * 127
FACE_B = [0.0, 1.0] + [0.0] * 126


def face2(cosine: float) -> list[float]:
    """A unit embedding in the x-y plane whose cosine with FACE_A is `cosine`."""
    return [float(cosine), float(np.sqrt(max(0.0, 1 - cosine**2)))] + [0.0] * 126


def rotated(face: list[float], cosine: float) -> list[float]:
    """A unit embedding whose cosine with `face` is `cosine` (same 2-d plane)."""
    theta = float(np.arctan2(face[1], face[0]))
    d = float(np.arccos(cosine))
    return [float(np.cos(theta + d)), float(np.sin(theta + d))] + [0.0] * 126


def ev(eid: str, exhibit: str, kind: str, role: str = "questioned") -> LabEvidence:
    return LabEvidence(id=eid, case_id="c", exhibit=exhibit, filename=f"{eid}.bin", size_bytes=1,
                       md5="0", sha1="0", sha256=eid, kind=MediaKind(kind), mime="x/y",
                       role=role, received_at=NOW, status=EvidenceStatus.DONE)  # fmt: skip


def analysis(eid: str, kind: str, techs: list[TechniqueResult] | None = None) -> EvidenceAnalysis:
    techs = techs or [
        TechniqueResult(id="t1", name="t1", category=Category.TAMPERING, status=Status.OK),
        TechniqueResult(id="t2", name="t2", category=Category.SYNTHETIC, status=Status.OK),
    ]
    a = EvidenceAnalysis(evidence_id=eid, case_id="c", started_at=NOW,
                         media=MediaInfo(kind=MediaKind(kind), mime="x/y", format="x"),
                         hashes=Hashes(md5="0", sha1="0", sha256=eid, size_bytes=1),
                         integrity_verified=True, techniques=techs)  # fmt: skip
    a.verdict = decide(a.media.kind, techs)
    return a


def link(a: str, b: str, kind: LinkKind, detail: str = "Perceptual hashes differ in 2/64 bits: x"):
    return EvidenceLink(source=a, target=b, kind=kind, score=0.9, detail=detail)


@pytest.fixture()
def video_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    evs = [ev("q", "Q1", "video"), ev("r", "R1", "video", "reference"),
           ev("p", "R2", "image", "reference")]  # fmt: skip
    an = {e.id: analysis(e.id, e.kind.value) for e in evs}
    feats = {"q": {"faces": [FACE_A]}, "r": {"faces": [FACE_B]}, "p": {"faces": [FACE_A]}}
    for e in evs:
        (tmp_path / e.id).mkdir()
    monkeypatch.setattr(inference, "matched_frames", lambda a, b, n=3: ([], []))
    return evs, an, feats, tmp_path


def test_same_footage_other_face_with_face_source_and_focus_is_strong(video_case, monkeypatch):
    evs, an, feats, tmp = video_case
    frame = np.zeros((90, 160, 3), np.uint8)
    monkeypatch.setattr(inference, "face_change", lambda a, b: {
        "ratio": 6.0, "share": 0.7, "box_area": 0.1, "frames": 3,
        "best": {"a": frame, "b": frame, "d": np.zeros((90, 160), np.float32),
                 "box": (40, 20, 80, 60), "ratio": 6.0}})  # fmt: skip
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE), link("q", "p", LinkKind.SAME_FACE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs},
                          lambda i: tmp / i)  # fmt: skip
    f = out["q"][0][0]
    assert f.code == "FACE_REPLACED" and f.strength == Strength.STRONG
    assert f.hypothesis == Hypothesis.SYNTHETIC and f.observations["face_sources"] == ["p"]
    assert out["q"][1] and (tmp / "q" / out["q"][1][0].name).exists()
    assert [x.code for x in out["r"][0]] == ["FOOTAGE_REUSED"]
    assert [x.code for x in out["p"][0]] == ["FACE_SOURCE"]
    assert all(x.strength == Strength.NONE for x in out["r"][0] + out["p"][0])
    b = inference.with_case_findings(an["q"], *out["q"])
    assert b.verdict and b.verdict.label.value == "SYNTHETIC"
    assert inference.file_verdict(MediaKind.VIDEO, b).label.value == "NO_INDICATORS"


def test_face_source_without_localisation_is_moderate(video_case, monkeypatch):
    evs, an, feats, tmp = video_case
    monkeypatch.setattr(inference, "face_change", lambda a, b: None)
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE), link("p", "q", LinkKind.SAME_FACE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs}, lambda i: tmp / i)
    assert out["q"][0][0].strength == Strength.MODERATE


def test_same_person_in_same_footage_is_not_a_face_swap(video_case):
    evs, an, feats, tmp = video_case
    feats["r"]["faces"] = [FACE_A]
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE), link("q", "p", LinkKind.SAME_FACE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs}, lambda i: tmp / i)
    assert "q" not in out and "r" not in out


def test_face_median_uses_index_matched_frames_and_falls_back_to_all_pairs():
    a = [FACE_A, FACE_B, FACE_A]
    b = [FACE_B, FACE_A, FACE_A]
    # Frame-to-frame: cosines 0, 0, 1 -> median 0. The old max-pair rule saw 1 and said
    # "same person"; the median says the identity is not stable across the footage.
    assert inference.face_median(a, b) == pytest.approx(0.0)
    # Different lengths: every pair counts, then the median (0 and 1 -> 0.5).
    assert inference.face_median([FACE_A], [FACE_B, FACE_A]) == pytest.approx(0.5)
    assert inference.face_median([], [FACE_A]) is None


def test_ambiguous_face_similarity_without_source_makes_no_inference(video_case):
    evs, an, feats, tmp = video_case
    feats["q"]["faces"] = [FACE_A]
    feats["r"]["faces"] = [face2(0.40)]  # above the 0.363 same-identity point
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs}, lambda i: tmp / i)
    assert out == {}


def test_demo_like_medians_and_face_source_cosines_support_a_replacement(video_case, monkeypatch):
    evs, an, feats, tmp = video_case
    q = [face2(c) for c in (0.80, 0.83, 0.50)]
    r = [rotated(x, c) for x, c in zip(q, (0.34, 0.33, 0.43), strict=True)]
    feats["q"]["faces"], feats["r"]["faces"], feats["p"]["faces"] = q, r, [FACE_A]
    monkeypatch.setattr(inference, "face_change", lambda a, b: None)
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE), link("q", "p", LinkKind.SAME_FACE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs}, lambda i: tmp / i)
    f = out["q"][0][0]
    assert f.code == "FACE_REPLACED" and f.strength == Strength.MODERATE
    assert f.observations["face_sources"] == ["p"]
    assert f.observations["face_cosine"] == pytest.approx(0.34, abs=0.01)
    assert f.observations["face_source_cosines"]["p"] == pytest.approx(0.80, abs=0.01)
    assert f.observations["face_source_original_cosines"]["p"] < 0.363
    assert "median SFace cosine over matched frames" in f.detail
    assert "standard same-identity point 0.363" in f.detail
    assert "score -0.29 against it" in f.detail  # source vs the original video's face


def test_face_source_must_beat_the_other_video_by_the_margin(video_case, monkeypatch):
    evs, an, feats, tmp = video_case
    evs[1] = ev("r", "Q2", "video")  # no role to fall back on: only the source margin decides
    q = [face2(0.55)]
    r = [rotated(q[0], 0.34)]  # 0.55 - 0.34 = 0.21 < SOURCE_MARGIN: too weak a source
    feats["q"]["faces"], feats["r"]["faces"], feats["p"]["faces"] = q, r, [FACE_A]
    monkeypatch.setattr(inference, "face_change", lambda a, b: None)
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE), link("q", "p", LinkKind.SAME_FACE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs}, lambda i: tmp / i)
    codes = {x.code for v in out.values() for x in v[0]}
    assert codes == {"SAME_FOOTAGE_OTHER_FACE"}


def test_two_questioned_videos_without_face_source_are_only_noted(video_case, monkeypatch):
    evs, an, feats, tmp = video_case
    evs[1] = ev("r", "Q2", "video")
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE)]
    out = inference.infer(evs, an, feats, links, {e.id: tmp / e.id for e in evs}, lambda i: tmp / i)
    codes = {x.code for v in out.values() for x in v[0]}
    assert codes == {"SAME_FOOTAGE_OTHER_FACE"}
    assert all(x.strength == Strength.NONE for v in out.values() for x in v[0])


def test_copy_of_synthetic_inherits_and_never_double_counts(tmp_path: Path) -> None:
    from satyapan.forensics.base import finding

    strong = finding("SD_WATERMARK", "wm", "d", Hypothesis.SYNTHETIC, Strength.STRONG,
                     Category.SYNTHETIC)  # fmt: skip
    strong.technique = "image.watermark"
    syn_techs = analysis("o", "image").techniques + [
        TechniqueResult(id="image.watermark", name="wm", category=Category.SYNTHETIC,
                        status=Status.OK, findings=[strong])]  # fmt: skip
    evs = [ev("o", "Q1", "image"), ev("c", "Q2", "image"), ev("x", "Q3", "image")]
    an = {"o": analysis("o", "image", syn_techs), "c": analysis("c", "image"),
          "x": analysis("x", "image")}  # fmt: skip
    links = [link("c", "o", LinkKind.NEAR_DUPLICATE),
             link("x", "o", LinkKind.NEAR_DUPLICATE),
             link("x", "o", LinkKind.SHARES_CONTENT, "After alignment 2 region(s) differ (at …)")]  # fmt: skip
    out = inference.infer(evs, an, {}, links, {}, lambda i: tmp_path)
    assert [f.code for f in out["c"][0]] == ["COPY_OF_SYNTHETIC"]
    assert out["c"][0][0].strength == Strength.STRONG
    assert "x" not in out  # an edited copy is not a pure copy
    assert "o" not in out  # already synthetic on its own evidence


def test_service_reevaluates_a_reshared_copy_and_logs_custody(tmp_path: Path) -> None:
    imwatermark = pytest.importorskip("imwatermark")
    enc = imwatermark.WatermarkEncoder()
    enc.set_watermark("bytes", b"SDV2")
    img = textured(512, 512, seed=10)
    marked = np.ascontiguousarray(
        enc.encode(np.ascontiguousarray(img[..., ::-1]), "dwtDct")[..., ::-1]
    )
    buf = io.BytesIO()
    Image.fromarray(marked).resize((360, 360), Image.BICUBIC).save(buf, format="JPEG", quality=60)
    svc = LabService(store=LabStore(tmp_path / "lab"), models=StubModels(), workers=1)
    try:
        case = svc.create_case(actor="t", title="copy", fir_number="1")
        orig, _ = svc.add_evidence(case.id, png(marked), "gen.png", actor="t")
        copy, _ = svc.add_evidence(case.id, buf.getvalue(), "IMG-WA0001.jpg", actor="t")
        t0 = time.time()
        while time.time() - t0 < 120:
            es = svc.store.case_evidence(case.id)
            if all(e.status in (EvidenceStatus.DONE, EvidenceStatus.ERROR) for e in es):
                break
            time.sleep(0.1)
        svc.pool.shutdown(wait=True)
        o, c = svc.store.evidence(orig.id), svc.store.evidence(copy.id)
        assert o and c and o.verdict and o.verdict.value == "SYNTHETIC"
        a = svc.store.analysis(copy.id)
        assert a is not None and c.verdict is not None
        case_t = [t for t in a.techniques if t.id == "case.compare"]
        if not case_t:  # watermark survived the re-compression: synthetic on its own
            assert c.verdict.value == "SYNTHETIC"
            return
        assert case_t[0].findings[0].code == "COPY_OF_SYNTHETIC"
        assert c.verdict.value == "SYNTHETIC"
        rows = svc.store.custody_rows(case.id)
        re_eval = [r for r in rows if r.payload.get("reason") == "cross-exhibit re-evaluation"]
        assert re_eval and re_eval[-1].evidence_id == copy.id
        assert svc.store.verify_chain().ok
        view = svc.case_view(case.id)
        assert any("re-shared copy" in s for s in view["findings"]["sentences"])
    finally:
        svc.pool.shutdown(wait=True)


def test_infer_survives_missing_features_paths_and_embeddings(tmp_path: Path, video_case,
                                                             monkeypatch):  # fmt: skip
    evs, an, feats, tmp = video_case
    links = [link("q", "r", LinkKind.NEAR_DUPLICATE)]
    # No features at all: nothing to compare.
    assert inference.infer(evs, an, {}, links, {}, lambda i: tmp_path) == {}
    # Missing feature maps and malformed embeddings are a missing comparison, not a crash.
    weird = {"q": None, "r": {"faces": [[1.0], [1.0, 0.0]]}}
    assert inference.infer(evs, an, weird, links, {}, lambda i: tmp_path) == {}
    # Faces present but the paths are missing: the inference stands without localisation.
    out = inference.infer(evs, an, {"q": {"faces": [FACE_A]}, "r": {"faces": [FACE_B]}},
                          links, {}, lambda i: tmp_path)  # fmt: skip
    f = out["q"][0][0]
    assert f.code == "FACE_REPLACED" and f.strength == Strength.WEAK
    assert f.observations["face_focus"] is None
    # A missing artifact directory must not lose the finding either.
    monkeypatch.setattr(inference, "matched_frames", lambda a, b, n=3: ([np.zeros((2, 2, 3),
                                                                                np.uint8)] * 2))  # fmt: skip
    monkeypatch.setattr(inference, "face_change", lambda a, b: {
        "ratio": 6.0, "share": 0.7, "box_area": 0.1, "frames": 2,
        "best": {"a": np.zeros((2, 2, 3), np.uint8), "b": np.zeros((2, 2, 3), np.uint8),
                 "d": np.zeros((2, 2), np.float32), "box": (0, 0, 2, 2), "ratio": 6.0}})  # fmt: skip
    out = inference.infer(evs, an, {"q": {"faces": [FACE_A, FACE_A]},
                                    "r": {"faces": [FACE_B, FACE_B]}},
                          links, {e.id: tmp / e.id for e in evs},
                          lambda i: tmp_path / "does-not-exist")  # fmt: skip
    assert out["q"][0][0].code == "FACE_REPLACED"
    assert out["q"][1] == []


def test_matched_frames_handles_very_different_lengths(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    rng = np.random.default_rng(7)
    base = [rng.integers(0, 255, (36, 64, 3), dtype=np.uint8) for _ in range(90)]
    a_path, b_path = tmp_path / "a.avi", tmp_path / "b.avi"

    def write(path: Path, frames: list[np.ndarray]) -> None:
        w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (64, 36))
        try:
            for f in frames:
                w.write(f)
        finally:
            w.release()

    write(a_path, base)
    write(b_path, base[::15])  # 6 frames: the same moments at the same relative positions
    fa, fb = inference.matched_frames(a_path, b_path, 3)
    assert len(fa) == len(fb) == 3
    # The chosen B frame is the matching moment, not merely a nearby frame: the search
    # window scales with B's frame count.
    assert max(float(np.abs(x.astype(np.float32) - y.astype(np.float32)).mean())
               for x, y in zip(fa, fb, strict=True)) < 25  # compression, not a wrong frame  # fmt: skip
    # And the reverse direction (B short, A long) does not crash or drop pairs.
    fa, fb = inference.matched_frames(b_path, a_path, 3)
    assert len(fa) == len(fb) == 3
    assert inference.matched_frames(tmp_path / "missing.mp4", a_path, 3) == ([], [])


def test_apply_case_inferences_is_atomic_and_idempotent_under_concurrency(tmp_path: Path,
                                                                        monkeypatch):  # fmt: skip
    monkeypatch.setattr(inference, "matched_frames", lambda a, b, n=3: ([], []))
    store = LabStore(tmp_path / "lab")
    evs = [ev("q", "Q1", "video"), ev("r", "R1", "video"), ev("p", "R2", "image", "reference")]
    an = {e.id: analysis(e.id, e.kind.value) for e in evs}
    for e in evs:
        store.put_evidence(e)
        store.put_analysis(an[e.id], {})
    store.put_analysis(an["q"], {"faces": [FACE_A]})
    store.put_analysis(an["r"], {"faces": [FACE_B]})
    store.put_analysis(an["p"], {"faces": [FACE_A]})
    store.replace_links("c", "q", [link("q", "r", LinkKind.NEAR_DUPLICATE),
                                   link("q", "p", LinkKind.SAME_FACE)])  # fmt: skip
    svc = LabService(store=store, models=StubModels(), workers=1)
    try:
        changed: list[list[str]] = []
        threads = [threading.Thread(target=lambda: changed.append(
            svc.apply_case_inferences("c", "t"))) for _ in range(2)]  # fmt: skip
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(sum(changed, [])) == ["p", "q", "r"]  # one pass did the work, one saw it
        q, r, p = (store.analysis(i) for i in ("q", "r", "p"))
        assert q and r and p
        by_id = {t.id: t for t in q.techniques}
        assert by_id["case.compare"].findings[0].code == "FACE_REPLACED"
        assert by_id["case.compare"].findings[0].strength == Strength.MODERATE
        codes = {f.code for a in (r, p) for t in a.techniques if t.id == "case.compare"
                 for f in t.findings}  # fmt: skip
        assert {"FOOTAGE_REUSED", "FACE_SOURCE"} <= codes
        rows = [x for x in store.custody_rows("c")
                if x.payload.get("reason") == "cross-exhibit re-evaluation"]  # fmt: skip
        assert len(rows) == 3 and {x.evidence_id for x in rows} == {"q", "r", "p"}
        verdicts = {x.evidence_id: x.payload.get("verdict") for x in rows}
        assert verdicts["q"] == "SUSPICIOUS"  # one moderate synthetic finding
        assert verdicts["r"] == verdicts["p"] == "NO_INDICATORS"
        assert store.verify_chain().ok
    finally:
        svc.pool.shutdown(wait=True)


def test_apply_case_inferences_does_not_resurrect_a_requeued_exhibit(tmp_path: Path,
                                                                    monkeypatch):  # fmt: skip
    monkeypatch.setattr(inference, "matched_frames", lambda a, b, n=3: ([], []))
    store = LabStore(tmp_path / "lab")
    evs = [ev("q", "Q1", "video"), ev("r", "R1", "video"), ev("p", "R2", "image", "reference")]
    an = {e.id: analysis(e.id, e.kind.value) for e in evs}
    for e in evs:
        store.put_evidence(e)
        store.put_analysis(an[e.id], {})
    store.put_analysis(an["q"], {"faces": [FACE_A]})
    store.put_analysis(an["r"], {"faces": [FACE_B]})
    store.put_analysis(an["p"], {"faces": [FACE_A]})
    store.replace_links("c", "q", [link("q", "r", LinkKind.NEAR_DUPLICATE),
                                   link("q", "p", LinkKind.SAME_FACE)])  # fmt: skip
    p = store.evidence("p")
    assert p is not None
    p.status = EvidenceStatus.QUEUED
    store.put_evidence(p)
    svc = LabService(store=store, models=StubModels(), workers=1)
    try:
        changed = svc.apply_case_inferences("c", "t")
        assert "p" not in changed  # a re-queued exhibit is left to its own analysis
        assert store.evidence("p").status == EvidenceStatus.QUEUED
        # `current` is the worker that is finishing: it may be updated but stays QUEUED
        # until the analysis pipeline marks it DONE.
        changed = svc.apply_case_inferences("c", "t", current="p")
        assert "p" in changed
        assert store.evidence("p").status == EvidenceStatus.QUEUED
    finally:
        svc.pool.shutdown(wait=True)


def test_narrative_keeps_proper_names_and_acronyms() -> None:
    from satyapan.forensics.narrative import lower_first

    assert lower_first("Content Credentials declare generative AI").startswith("Content")
    assert lower_first("ENF trace breaks at 16.5 s").startswith("ENF")
    assert lower_first("Cloned region: 54 keypoints") == "cloned region: 54 keypoints"


def test_any_file_robustness() -> None:
    """Blank images abstain the AI classifier; the CLI skips empty files instead of aborting."""
    import subprocess
    import sys

    from satyapan.forensics.engine import analyze_bytes

    with tempfile.TemporaryDirectory() as d:
        buf = io.BytesIO()
        Image.new("RGB", (800, 600)).save(buf, format="PNG")
        a, _ = analyze_bytes(buf.getvalue(), "blank.png", Path(d), models=StubModels())
        aig = next(t for t in a.techniques if t.id == "image.aigen")
        assert aig.status in (Status.SKIPPED, Status.UNAVAILABLE)
        folder = Path(d) / "in"
        folder.mkdir()
        (folder / "empty.bin").write_bytes(b"")
        (folder / "notes.txt").write_text("hello")
        r = subprocess.run([sys.executable, "-m", "satyapan.forensics.cli", str(folder), "--no-color"],
                           capture_output=True, text=True, timeout=300,
                           env={**__import__("os").environ, "SATYAPAN_LAB_DIR": str(Path(d) / "lab")})  # fmt: skip
        assert "skip" in r.stdout and "custody chain: INTACT" in r.stdout
        assert r.returncode == 2
