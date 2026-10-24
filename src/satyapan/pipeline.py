"""Evidence -> detectors -> signals -> decision. PRE-IMPLEMENTED orchestration.

Safe by default: if a detector is not implemented yet or crashes, the evidence gets
GreyReason.DETECTOR_ERROR, which forces at least VERIFY and the checker queue. A missing
detector can therefore never make a case look safer than it is.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from satyapan.adapters.base import Transcriber
from satyapan.contracts.case import Case
from satyapan.contracts.enums import ActionType, Channel, GreyReason, ReasonCode, SignalSource
from satyapan.contracts.evidence import AnalysisRun, DetectorOutput, Evidence, Signal
from satyapan.master.store import MasterData
from satyapan.policy.config import DEFAULT_CONFIG, PolicyConfig
from satyapan.policy.engine import apply_decision, decide
from satyapan.settings import Settings
from satyapan.voice.detector import WindowScorer
from satyapan.voice.rules import VoiceThresholds

log = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    master: MasterData
    settings: Settings
    thresholds: VoiceThresholds
    scorer: WindowScorer | None = None
    transcriber: Transcriber | None = None
    # ADR-021: strip footers / quoted bank notifications / protective warnings before the
    # (frozen) ask extractor. False reproduces the pre-ADR-021 pipeline for before/after runs.
    context_filter: bool = True
    # ADR-024: product surfaces (files handed to Satya) add the live phrasebook on top of the
    # frozen lexicon. Research runs keep the default (False) so measured numbers reproduce.
    live_phrasebook: bool = False
    # Finale video check (docs/VIDEO_DEEPFAKE.md): a VideoAnalyzer, or None if unavailable.
    video: Any = None
    # Scam-text model (docs/TEXT_BENCHMARK.md): a TextRiskModel, or None. Research runs keep
    # None so the frozen-lexicon numbers reproduce.
    text_model: Any = None
    # Still images: an ImageFaceChecker (face CNN on one crop), or None if unavailable.
    image: Any = None


def _asks(text: str, ev_id: str, ctx: PipelineContext, out: DetectorOutput) -> DetectorOutput:
    """Run the frozen ask extractor on the context-filtered text; record what was ignored
    in out.artifacts['context'] so the checker can see it (nothing is silently dropped)."""
    from satyapan.asks.extractor import ask_signals, extract_asks
    from satyapan.context import strip_context

    if ctx.text_model is not None:
        from satyapan.textrisk.rules import text_signal

        sig = text_signal(ctx.text_model, text, [ev_id])
        out.artifacts["text_risk"] = {"flagged": sig is not None,
                                      "model": ctx.text_model.version}  # fmt: skip
        if sig is not None:
            out.signals.append(sig)
    if ctx.context_filter:
        res = strip_context(text)
        text = res.cleaned
        out.artifacts["context"] = {
            **res.summary(),
            "removed": [
                {"kind": r.kind, "rule": r.rule, "text": r.text[:200]} for r in res.removed
            ],
        }
    if ctx.live_phrasebook:
        from satyapan.asks.phrasebook import PHRASEBOOK_VERSION, extract_live_asks

        spans = extract_live_asks(text)
        out.artifacts["phrasebook"] = PHRASEBOOK_VERSION
    else:
        spans = extract_asks(text)
    out.artifacts["asks"] = [{"ask_type": s.ask_type.value, "text": s.text[:200]} for s in spans]
    out.signals += ask_signals(spans, ev_id)
    return out


def _run(name: str, evidence_id: str, fn: Callable[[], DetectorOutput]) -> DetectorOutput:
    t0 = time.perf_counter()
    try:
        out = fn()
    except NotImplementedError as e:
        log.warning("detector %s not implemented yet: %s", name, e)
        return DetectorOutput(
            detector=name,
            version="stub",
            evidence_id=evidence_id,
            grey_reasons=[GreyReason.DETECTOR_ERROR],
            error=f"not implemented: {e}",
        )
    except ValueError as e:  # parse failures
        return DetectorOutput(
            detector=name,
            version="error",
            evidence_id=evidence_id,
            grey_reasons=[GreyReason.PARSE_FAILURE],
            error=str(e),
        )
    except Exception as e:  # noqa: BLE001 - any detector crash must become GREY, never PASS
        log.exception("detector %s crashed", name)
        return DetectorOutput(
            detector=name,
            version="error",
            evidence_id=evidence_id,
            grey_reasons=[GreyReason.DETECTOR_ERROR],
            error=repr(e),
        )
    out.duration_ms = (time.perf_counter() - t0) * 1000
    return out


def _email(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    from satyapan.email.parser import parse_eml
    from satyapan.email.signals import email_signals

    parsed = parse_eml(data, trusted_authserv_id=ctx.settings.trusted_authserv_id)
    out = email_signals(parsed, ctx.master, ev.id)
    return _asks(parsed.subject + "\n" + parsed.body_text, ev.id, ctx, out)


def _pdf(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    from satyapan.document.checker import document_signals
    from satyapan.document.extract import extract_invoice_fields
    from satyapan.document.pdf import extract_pdf_text, read_pdf_metadata

    text = extract_pdf_text(data)
    out = document_signals(
        extract_invoice_fields(text), read_pdf_metadata(data), ctx.master, case.txn, ev.id
    )
    return _asks(text, ev.id, ctx, out)


def _voice(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    from satyapan.voice.upload import analyze_voice_upload

    if ctx.scorer is None and ctx.transcriber is not None:
        return _voice_transcript_only(data, ev, ctx)
    if ctx.scorer is None:  # neither model on this laptop: an abstention, not a finding
        return DetectorOutput(detector="voice", version="0.1.0", evidence_id=ev.id,
                              artifacts={"voice_label": "not_analysed"})  # fmt: skip
    return analyze_voice_upload(
        data, ev.media_type, ev.id, ctx.scorer, ctx.transcriber, ctx.thresholds
    )


def _voice_transcript_only(data: bytes, ev: Evidence, ctx: PipelineContext) -> DetectorOutput:
    """No voice-deepfake model on this laptop: still check WHAT was asked in the voice note.

    The voice itself is not judged (no voice signal, label "not_analysed"). Missing a model is
    an abstention, not a finding, so it adds no grey reason; the floor still applies."""
    assert ctx.transcriber is not None
    result = ctx.transcriber.transcribe(data, ev.media_type)
    out = DetectorOutput(
        detector="voice_transcript",
        version="0.1.0",
        evidence_id=ev.id,
        artifacts={
            "transcript": result.text,
            "language": result.language,
            "voice_label": "not_analysed",
            "engine": result.engine,
        },
    )
    return _asks(result.text, ev.id, ctx, out)


def _video(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    """A recorded video (call recording, forwarded clip): face check + what was asked.

    No analyzer on this laptop -> the face is "not_analysed" (an abstention, not a finding,
    so no grey reason); the speech is still checked for asks when a transcriber exists."""
    out = DetectorOutput(detector="video", version="0.1.0", evidence_id=ev.id)
    if ctx.video is not None:
        from satyapan.video.io import TempVideo, iter_frames, read_audio
        from satyapan.video.rules import video_signal

        suffix = Path(ev.filename or "clip.mp4").suffix or ".mp4"
        with TempVideo(data, suffix) as path:
            audio = read_audio(path)
            windows = ctx.video.analyze_frames(iter_frames(path), audio)
        verdict = ctx.video.verdict(windows)
        cues = sorted({c for w in windows for c in w.cues})
        out.signals.append(video_signal(verdict, ctx.video.thresholds, [ev.id], cues))
        out.version = ctx.video.thresholds.model_version
        out.artifacts.update(
            {
                "video_label": verdict.label.value,
                "windows": verdict.windows,
                "usable_windows": verdict.usable_windows,
                "cues": cues,
                "problem": verdict.problem,
            }
        )
    else:
        out.artifacts["video_label"] = "not_analysed"
    if ctx.transcriber is not None:
        try:
            result = ctx.transcriber.transcribe(data, ev.media_type)
        except (RuntimeError, ValueError):
            return out  # no speech engine or no decodable audio: the face check still stands
        out.artifacts["transcript"] = result.text
        return _asks(result.text, ev.id, ctx, out)
    return out


def _image(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    """A photo or screenshot: is the face swapped/generated, and what does the text in it ask?

    Either half may be unavailable on a laptop (no face model, no OCR); that is reported in
    the artifacts as "not_analysed", an abstention and never a pass. ValueError (not an
    image) becomes a grey PARSE_FAILURE in _run."""
    from satyapan.imagecheck.face import decode_image

    rgb = decode_image(data)
    out = DetectorOutput(detector="image", version="0.1.0", evidence_id=ev.id)
    out.artifacts["size"] = [int(rgb.shape[1]), int(rgb.shape[0])]
    photo_of_a_person = False
    if ctx.image is not None:
        from satyapan.imagecheck.face import image_face_signal

        verdict = ctx.image.check(rgb)
        out.signals.append(image_face_signal(verdict, ctx.image, ev.id))
        out.artifacts["face_label"] = verdict.code.value
        out.artifacts["face_problem"] = verdict.problem
        photo_of_a_person = verdict.problem is None
    else:
        out.artifacts["face_label"] = "not_analysed"
    from satyapan.imagecheck.ocr import OcrUnavailable, read_text

    try:
        text = read_text(rgb)
    except OcrUnavailable as exc:
        out.artifacts["ocr"] = str(exc)
        return out
    out.artifacts["ocr_text"] = text[:2000]
    if not text.strip():
        return out
    if photo_of_a_person:
        # A photo of a person is judged by its face. Captions, tickers and signs in it are
        # not messages: only explicit asks count there, not the message-trained text model.
        from dataclasses import replace

        out.artifacts["text_model"] = "skipped: photo of a person (captions are not messages)"
        return _asks(text, ev.id, replace(ctx, text_model=None), out)
    return _asks(text, ev.id, ctx, out)


def _text(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    text = data.decode("utf-8", errors="replace")
    out = DetectorOutput(detector="ask_extractor", version="see lexicon", evidence_id=ev.id)
    return _asks(text, ev.id, ctx, out)


_DISPATCH: dict[Channel, Callable[[bytes, Evidence, Case, PipelineContext], DetectorOutput]] = {
    Channel.EMAIL: _email,
    Channel.PDF: _pdf,
    Channel.VOICE_NOTE: _voice,
    Channel.CALL_RECORDING: _voice,
    Channel.VIDEO: _video,
    Channel.IMAGE: _image,
    Channel.WHATSAPP_TEXT: _text,
    Channel.MANUAL: _text,
}


def analyze_evidence(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    fn = _DISPATCH.get(ev.channel)
    if fn is None:
        return DetectorOutput(
            detector="none",
            version="0",
            evidence_id=ev.id,
            grey_reasons=[GreyReason.UNSUPPORTED_LANGUAGE],
            error=f"no detector for channel {ev.channel}",
        )
    return _run(f"{ev.channel.value}_pipeline", ev.id, lambda: fn(data, ev, case, ctx))


def merge_output(case: Case, ev: Evidence, out: DetectorOutput) -> Case:
    """Add the detector's signals/grey reasons to the case. Duplicates (same code + same
    evidence) are dropped. Signals are only ever ADDED here, never removed."""
    seen = {(s.code, tuple(s.evidence_ids)) for s in case.signals}
    signals = list(case.signals)
    for s in out.signals:
        key = (s.code, tuple(s.evidence_ids))
        if key not in seen:
            signals.append(s)
            seen.add(key)
    grey = list(dict.fromkeys([*case.grey_reasons, *out.grey_reasons]))
    evidence = [
        e.model_copy(
            update={
                "analysis_runs": [
                    *e.analysis_runs,
                    AnalysisRun(detector=out.detector, version=out.version),
                ]
            }
        )
        if e.id == ev.id
        else e
        for e in case.evidence
    ]
    return case.model_copy(update={"signals": signals, "grey_reasons": grey, "evidence": evidence})


# --------------------------------------------------------------------- X1 cross-channel
# ARCHITECTURE §7: within 30 minutes in one case, a call/message ask for A1 (new account) or
# A7 (payee change) next to a payment to a new/changed beneficiary raises to VERIFY; an A4
# (secrecy) or A5 (bypass) ask in the same window raises to HOLD. Fully deterministic and
# explainable. Evidence can only raise the band: derive() never removes or lowers anything.
CROSS_CHANNEL_WINDOW_SECONDS = 30 * 60

_ACCOUNT_ASKS: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.ASK_NEW_ACCOUNT,  # A1
        ReasonCode.ASK_PAYEE_CHANGE,  # A7
        ReasonCode.ASK_UNUSUAL_PAYMENT_METHOD,  # A6: an unusual rail plus a new payee
    }
)
_URGENCY_ASKS: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.ASK_SECRECY,  # A4
        ReasonCode.ASK_BYPASS,  # A5
    }
)
_CROSS_CHANNEL_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.CROSS_CHANNEL_SEQUENCE,
        ReasonCode.CROSS_CHANNEL_URGENT_BYPASS,
    }
)


def _aware(when: datetime) -> datetime:
    """Treat a missing timezone as UTC so comparisons never raise on fixture data."""
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


def _within_window(when: datetime, anchor: datetime) -> bool:
    return abs((_aware(when) - _aware(anchor)).total_seconds()) <= CROSS_CHANNEL_WINDOW_SECONDS


def _beneficiary_is_new_or_changed(case: Case, master: MasterData | None) -> bool:
    """Trusted-only check: is this payment to a new payee, or to changed bank details?

    Reads the maker-entered txn (trusted) and the vendor master only. When no master is
    passed, it falls back to the contract marker (`vendor_id is None` = maker says new) and
    to a floor action already recorded on the case. Evidence is never consulted here.
    """
    txn = case.txn
    if txn is None:
        return False
    if master is None:
        if txn.vendor_id is None:
            return True
        decision = case.decision
        return decision is not None and decision.action_type in {
            ActionType.N1,
            ActionType.N2,
            ActionType.C1,
        }
    vendor = (
        master.vendor(txn.vendor_id)
        if txn.vendor_id is not None
        else master.vendor_by_payee(txn.account_number, txn.ifsc, txn.upi_id)
    )
    if vendor is None:
        return True  # new beneficiary
    return not vendor.has_account(txn.account_number, txn.ifsc, txn.upi_id)  # changed details


def _window_evidence_ids(
    signal: Signal, captured: dict[str, datetime], anchor: datetime
) -> list[str]:
    """Evidence ids on this signal that fall inside the X1 window around the payment."""
    return [
        ev_id
        for ev_id in signal.evidence_ids
        if ev_id in captured and _within_window(captured[ev_id], anchor)
    ]


def derive_cross_channel_signals(case: Case, master: MasterData | None = None) -> list[Signal]:
    """X1: return the cross-channel signal for this case (empty when the sequence is absent).

    The sequence is: within 30 minutes of `txn.created_at`, a call/message ask for a new
    account or payee change (A1/A6/A7) AND a payment to a new or changed beneficiary. A4
    (secrecy) or A5 (bypass) in the same window escalates the signal to HOLD. Raise-only:
    the result is built with `Signal.make(..., source=DETERMINISTIC)` and can never lower
    a band. Idempotent: a code already on the case is not added twice.
    """
    txn = case.txn
    if txn is None or not _beneficiary_is_new_or_changed(case, master):
        return []

    anchor = txn.created_at
    captured = {ev.id: ev.captured_at for ev in case.evidence}
    account_ids: list[str] = []
    urgency_ids: list[str] = []
    for signal in case.signals:
        if signal.code in _CROSS_CHANNEL_CODES:
            continue
        ids = _window_evidence_ids(signal, captured, anchor)
        if not ids:
            continue
        if signal.code in _ACCOUNT_ASKS:
            account_ids.extend(ids)
        elif signal.code in _URGENCY_ASKS:
            urgency_ids.extend(ids)

    if not account_ids:
        return []

    existing = {s.code for s in case.signals}
    code = (
        ReasonCode.CROSS_CHANNEL_URGENT_BYPASS if urgency_ids else ReasonCode.CROSS_CHANNEL_SEQUENCE
    )
    if code in existing or (
        code == ReasonCode.CROSS_CHANNEL_SEQUENCE
        and ReasonCode.CROSS_CHANNEL_URGENT_BYPASS in existing
    ):
        return []

    evidence_ids = list(dict.fromkeys([*account_ids, *urgency_ids]))
    return [
        Signal.make(
            code,
            source=SignalSource.DETERMINISTIC,
            evidence_ids=evidence_ids,
            detector="cross_channel",
            detail={
                "window_seconds": CROSS_CHANNEL_WINDOW_SECONDS,
                "account_asks": len(set(account_ids)),
                "urgency_asks": len(set(urgency_ids)),
            },
        )
    ]


def recompute(case: Case, master: MasterData, cfg: PolicyConfig = DEFAULT_CONFIG) -> Case:
    derived = derive_cross_channel_signals(case, master)
    if derived:
        seen = {(s.code, tuple(s.evidence_ids)) for s in case.signals}
        extra = [s for s in derived if (s.code, tuple(s.evidence_ids)) not in seen]
        if extra:
            case = case.model_copy(update={"signals": [*case.signals, *extra]})
    return apply_decision(case, decide(case, master, cfg))
