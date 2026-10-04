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

from satyapan.adapters.base import Transcriber
from satyapan.contracts.case import Case
from satyapan.contracts.enums import Channel, GreyReason
from satyapan.contracts.evidence import AnalysisRun, DetectorOutput, Evidence
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
    from satyapan.asks.extractor import ask_signals, extract_asks
    from satyapan.email.parser import parse_eml
    from satyapan.email.signals import email_signals

    parsed = parse_eml(data, trusted_authserv_id=ctx.settings.trusted_authserv_id)
    out = email_signals(parsed, ctx.master, ev.id)
    out.signals += ask_signals(extract_asks(parsed.subject + "\n" + parsed.body_text), ev.id)
    return out


def _pdf(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    from satyapan.asks.extractor import ask_signals, extract_asks
    from satyapan.document.checker import document_signals
    from satyapan.document.extract import extract_invoice_fields
    from satyapan.document.pdf import extract_pdf_text, read_pdf_metadata

    text = extract_pdf_text(data)
    out = document_signals(
        extract_invoice_fields(text), read_pdf_metadata(data), ctx.master, case.txn, ev.id
    )
    out.signals += ask_signals(extract_asks(text), ev.id)
    return out


def _voice(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    from satyapan.voice.upload import analyze_voice_upload

    if ctx.scorer is None or ctx.transcriber is None:
        raise NotImplementedError("voice scorer/transcriber not configured (T17)")
    return analyze_voice_upload(
        data, ev.media_type, ev.id, ctx.scorer, ctx.transcriber, ctx.thresholds
    )


def _text(data: bytes, ev: Evidence, case: Case, ctx: PipelineContext) -> DetectorOutput:
    from satyapan.asks.extractor import ask_signals, extract_asks

    text = data.decode("utf-8", errors="replace")
    return DetectorOutput(
        detector="ask_extractor",
        version="see lexicon",
        evidence_id=ev.id,
        signals=ask_signals(extract_asks(text), ev.id),
    )


_DISPATCH: dict[Channel, Callable[[bytes, Evidence, Case, PipelineContext], DetectorOutput]] = {
    Channel.EMAIL: _email,
    Channel.PDF: _pdf,
    Channel.VOICE_NOTE: _voice,
    Channel.CALL_RECORDING: _voice,
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


def recompute(case: Case, master: MasterData, cfg: PolicyConfig = DEFAULT_CONFIG) -> Case:
    return apply_decision(case, decide(case, master, cfg))
