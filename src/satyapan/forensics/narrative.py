"""Case-level findings in plain sentences, built deterministically from the verdicts and the
cross-exhibit links (no language model: every sentence is traceable to a finding or a link).
Used by the case API and the first page of the report."""

from __future__ import annotations

from typing import Any

from satyapan.forensics.models import EvidenceAnalysis, EvidenceLink, LabEvidence, LinkKind

LABEL_WORDS = {
    "SYNTHETIC": "synthetic (AI-generated or deepfaked)",
    "MANIPULATED": "manipulated after capture",
    "SUSPICIOUS": "suspicious and needs further examination",
    "NO_INDICATORS": "without indications of manipulation",
    "INCONCLUSIVE": "inconclusive",
}


def lower_first(text: str) -> str:
    """Lower-case the first letter unless it starts an acronym (AI, ELA, ENF, C2PA...)."""
    if len(text) > 1 and text[:2].isupper():
        return text
    return text[:1].lower() + text[1:]


def case_findings(evidence: list[LabEvidence], analyses: dict[str, EvidenceAnalysis | None],
                  links: list[EvidenceLink], chain_ok: bool | None = None) -> dict[str, Any]:  # fmt: skip
    ex = {e.id: e for e in evidence}
    tag = {e.id: f"{e.exhibit} ({e.filename})" for e in evidence}
    done = [e for e in evidence if e.verdict is not None]
    counts: dict[str, int] = {}
    for e in done:
        counts[e.verdict.value] = counts.get(e.verdict.value, 0) + 1  # type: ignore[union-attr]
    sentences: list[str] = []
    if done:
        parts = [f"{n} {LABEL_WORDS[k].split(' (')[0]}" for k, n in sorted(counts.items(),
                 key=lambda kv: list(LABEL_WORDS).index(kv[0]))]  # fmt: skip
        sentences.append(
            f"{len(done)} of {len(evidence)} exhibits examined: " + ", ".join(parts) + "."
        )
    for e in sorted(done, key=lambda e: e.exhibit):
        if e.verdict is None or e.verdict.value not in ("SYNTHETIC", "MANIPULATED", "SUSPICIOUS"):
            continue
        a = analyses.get(e.id)
        why = (
            a.verdict.rationale[0].split("] ", 1)[-1]
            if a and a.verdict and a.verdict.rationale
            else ""
        )
        sentences.append(f"{tag[e.id]} is {LABEL_WORDS[e.verdict.value]}"
                         + (f": {lower_first(why)}." if why else "."))  # fmt: skip
    seen: set[tuple[str, str, str]] = set()
    for ln in sorted(links, key=lambda ln: (ln.kind.value, -ln.score)):
        a_id, b_id = ln.source, ln.target
        key = (*sorted((a_id, b_id)), ln.kind.value)
        if key in seen or a_id not in ex or b_id not in ex:
            continue
        seen.add(key)  # type: ignore[arg-type]
        a, b = ex[a_id], ex[b_id]
        q, r = (a, b) if a.role.value == "questioned" or b.role.value != "questioned" else (b, a)
        syn = {x.id for x in (a, b) if x.verdict is not None and x.verdict.value == "SYNTHETIC"}
        if ln.kind == LinkKind.SAME_SPEAKER:
            if q.id in syn:
                sentences.append(f"{tag[q.id]} is a synthetic voice that matches the speaker of "
                                 f"{tag[r.id]} (cosine {ln.score:.2f}): consistent with a voice "
                                 "clone of that person.")  # fmt: skip
            else:
                sentences.append(
                    f"{tag[q.id]} and {tag[r.id]} have the same speaker (cosine {ln.score:.2f})."
                )
        elif ln.kind == LinkKind.SAME_FACE:
            sentences.append(f"The face in {tag[q.id]} matches the face in {tag[r.id]} (SFace "
                             f"{ln.score:.2f})" + (": the deepfake reuses that identity." if q.id in syn
                                                   or (q.verdict and q.verdict.value == "SUSPICIOUS") else "."))  # fmt: skip
        elif ln.kind == LinkKind.SHARES_CONTENT:
            changed = "differ" in ln.detail and "the content is the same" not in ln.detail
            sentences.append(f"{tag[q.id]} shares its content with {tag[r.id]}"
                             + (" and was edited from it: the changed regions are boxed in the "
                                "comparison figure." if changed else "."))  # fmt: skip
        elif ln.kind == LinkKind.NEAR_DUPLICATE:
            if "video" in (q.kind.value, r.kind.value):
                sentences.append(f"{tag[q.id]} shows the same scene as {tag[r.id]} (key-frame "
                                 f"similarity {ln.score:.2f}): the same footage, possibly with the face "
                                 "or audio replaced.")  # fmt: skip
            else:
                sentences.append(f"{tag[q.id]} is the same picture as {tag[r.id]}, re-encoded or "
                                 f"resized (perceptual similarity {ln.score:.2f}).")  # fmt: skip
        elif ln.kind == LinkKind.SAME_DEVICE:
            sentences.append(f"{tag[q.id]} and {tag[r.id]} name the same capture device.")
        elif ln.kind == LinkKind.SAME_GENERATOR:
            sentences.append(f"{tag[q.id]} and {tag[r.id]} carry the same AI-generator signature.")
    if chain_ok is not None:
        sentences.append("The chain of custody verifies intact." if chain_ok
                         else "WARNING: the chain of custody does not verify.")  # fmt: skip
    pending = [e for e in evidence if e.verdict is None]
    if pending:
        sentences.append(f"{len(pending)} exhibit(s) not yet analysed.")
    return {"counts": counts, "sentences": sentences}
