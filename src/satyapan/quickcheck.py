"""One file or message in, a plain verdict out — the core of the consumer Scam Check page and
of the kit runner (`satya check`).

Every detector this laptop has runs on the bytes (text model + asks, voice-clone model,
face check on photos and videos, text inside images); the policy engine sets the band from
their signals (raise-only, as everywhere); the answer is the band, why it fired, what to do,
and what could NOT be checked here. Nothing is kept: no vault, no case store, the bytes are
dropped when the call returns (a video is decoded from a temp file that is deleted).
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from satyapan.contracts.case import Case
from satyapan.contracts.common import utcnow
from satyapan.contracts.enums import Band, CaseKind, Channel, Lang, ReasonCode
from satyapan.contracts.evidence import Evidence
from satyapan.explain.templates import reason_text
from satyapan.filetypes import channel_for
from satyapan.pipeline import PipelineContext, analyze_evidence, merge_output, recompute


@dataclass(frozen=True)
class QuickResult:
    band: Band
    channel: Channel
    reason_codes: list[ReasonCode]  # what set or raised the band (decision order)
    info_codes: list[ReasonCode]  # findings with no band effect (e.g. "no signs")
    why: list[str]  # one plain sentence per code above, in the requested language
    findings: dict[str, str]  # detector -> label, e.g. {"voice": "likely_synthetic"}
    not_checked: list[str] = field(default_factory=list)  # what this laptop could not check
    transcript: str | None = None  # what was said / written (for the person, not stored)
    seconds: float = 0.0
    sha256: str = ""


def _context(state: Any, channel: Channel) -> PipelineContext:
    transcriber = state.transcriber()
    if getattr(getattr(transcriber, "status", None), "engine", "") == "none":
        transcriber = None  # no speech engine installed: say so, don't fail the whole file
    return PipelineContext(
        master=state.master,
        settings=state.settings,
        thresholds=state.thresholds,
        transcriber=transcriber,
        live_phrasebook=True,
        text_model=state.text_model(),
        scorer=state.voice_scorer(),
        video=state.video() if channel == Channel.VIDEO else None,
        image=state.image_checker() if channel == Channel.IMAGE else None,
    )


def _findings(channel: Channel, out: Any, ctx: PipelineContext) -> tuple[dict[str, str], list[str]]:
    a = out.artifacts
    found: dict[str, str] = {}
    missing: list[str] = []
    spoken = (Channel.VOICE_NOTE, Channel.CALL_RECORDING, Channel.VIDEO)
    if channel in spoken and ctx.transcriber is None:
        missing.append("what was said (speech engine not installed: make asr)")
    if channel in (Channel.VOICE_NOTE, Channel.CALL_RECORDING):
        if ctx.scorer is None:
            missing.append("voice clone (voice model not installed)")
        else:
            found["voice"] = str(a.get("voice_label", "not_analysed"))
    if channel == Channel.VIDEO:
        found["face"] = str(a.get("video_label", "not_analysed"))
        if found["face"] == "not_analysed":
            missing.append("face (video check not installed)")
    if channel == Channel.IMAGE:
        found["face"] = str(a.get("face_label", "not_analysed"))
        if found["face"] == "not_analysed":
            missing.append("face (face model not installed)")
        if "ocr" in a:
            missing.append("text in the image (OCR not installed)")
    if "text_model" in a:
        found["text"] = "skipped_photo_of_a_person"
    elif "text_risk" in a:
        found["text"] = "reads_like_scam" if a["text_risk"]["flagged"] else "no_scam_pattern"
    elif ctx.text_model is None:
        missing.append("scam-text model (config/text_model.* missing)")
    asks = sorted({x["ask_type"] for x in a.get("asks", [])})
    if "asks" in a:
        found["asks"] = ",".join(asks) if asks else "none"
    if out.error:
        missing.append(f"{out.detector}: {out.error[:120]}")
    return found, missing


def quick_check(
    state: Any,
    data: bytes,
    filename: str | None,
    media_type: str = "",
    lang: Lang = Lang.EN,
    actor: str = "citizen",
) -> QuickResult:
    """Check one file (or one pasted message as text bytes); keep nothing."""
    t0 = time.perf_counter()
    channel = channel_for(filename, media_type)
    sha = hashlib.sha256(data).hexdigest()
    case = Case(
        id=f"case_qc_{uuid.uuid4().hex[:10]}",
        title=f"Quick check: {filename or 'message'}",
        kind=CaseKind.DATA_REQUEST,
        created_at=utcnow(),
        created_by=actor,
    )
    ev = Evidence(
        id=f"ev_qc_{uuid.uuid4().hex[:10]}",
        case_id=case.id,
        channel=channel,
        filename=filename,
        media_type=media_type or "application/octet-stream",
        sha256=sha,
        size_bytes=len(data),
        captured_at=utcnow(),
        submitted_by=actor,
        storage_uri="memory://not-stored",
    )
    ctx = _context(state, channel)
    out = analyze_evidence(data, ev, case, ctx)
    case = recompute(merge_output(case, ev, out), state.master)
    decision = case.decision
    assert decision is not None
    findings, missing = _findings(channel, out, ctx)
    # The payment floor is the business view; a consumer checking one file has no payment
    # here, so the floor line is left out of what they read (the band is unchanged).
    codes = [c for c in decision.reason_codes if not c.value.startswith("FLOOR_")]
    info = [c for c in decision.info_codes if c not in codes and not c.value.startswith("FLOOR_")]
    why = [reason_text(c, lang) for c in codes + info]
    transcript = out.artifacts.get("transcript") or out.artifacts.get("ocr_text")
    return QuickResult(
        band=decision.band,
        channel=channel,
        reason_codes=codes,
        info_codes=info,
        why=why,
        findings=findings,
        not_checked=missing,
        transcript=(str(transcript)[:1000] if transcript else None),
        seconds=round(time.perf_counter() - t0, 2),
        sha256=sha,
    )
