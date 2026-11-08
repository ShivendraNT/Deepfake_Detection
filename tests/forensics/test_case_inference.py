"""Cross-exhibit inferences (satyapan.forensics.inference): face replacement and copies of
synthetic pictures, plus the service pass that re-decides verdicts and logs custody."""

from __future__ import annotations

import io
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
    marked = np.ascontiguousarray(enc.encode(np.ascontiguousarray(img[..., ::-1]), "dwtDct")[..., ::-1])
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


def test_narrative_keeps_proper_names_and_acronyms() -> None:
    from satyapan.forensics.narrative import lower_first

    assert lower_first("Content Credentials declare generative AI").startswith("Content")
    assert lower_first("ENF trace breaks at 16.5 s").startswith("ENF")
    assert lower_first("Cloned region: 54 keypoints") == "cloned region: 54 keypoints"
