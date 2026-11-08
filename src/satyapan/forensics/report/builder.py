"""Automated multimedia forensic examination report (PDF, ReportLab).

Sections: cover, summary of conclusions, exhibits and hash values, methodology and tools,
one examination section per exhibit (verdict, findings, figures, provenance, what could not
be checked), cross-exhibit links, chain of custody with hash-chain verification, error rates
and limitations, a draft certificate under Section 63(4)(c) of the Bharatiya Sakshya
Adhiniyam, 2023 (Part B, for the examiner to verify and sign by hand), and a glossary.

The report is a draft for the examiner: it never signs on anyone's behalf and nothing is
submitted anywhere. Its SHA-256 is recorded in the custody log when it is generated.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import secrets
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from satyapan.contracts.enums import CustodyEvent
from satyapan.forensics import catalogue
from satyapan.forensics.models import (
    ENGINE_VERSION,
    STRENGTH_WORDS,
    EvidenceAnalysis,
    Hypothesis,
    LabCase,
    LabEvidence,
    Status,
    Strength,
    utcnow,
)

FONT_DIR = Path(__file__).resolve().parent / "fonts"
IST = timezone(timedelta(hours=5, minutes=30))

VERDICT_COLOURS = {
    "SYNTHETIC": "#b4232a", "MANIPULATED": "#c2410c", "SUSPICIOUS": "#b7791f",
    "NO_INDICATORS": "#15803d", "INCONCLUSIVE": "#475569",
}  # fmt: skip
VERDICT_WORDS = {
    "SYNTHETIC": "SYNTHETIC / DEEPFAKE", "MANIPULATED": "MANIPULATED",
    "SUSPICIOUS": "SUSPICIOUS", "NO_INDICATORS": "NO INDICATIONS FOUND",
    "INCONCLUSIVE": "INCONCLUSIVE",
}  # fmt: skip


def ist(dt: datetime | str | None) -> str:
    if dt is None:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST).strftime("%d/%m/%Y %H:%M:%S IST")


def _fonts() -> None:
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "DejaVu" in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Italic", str(FONT_DIR / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono", str(FONT_DIR / "DejaVuSansMono.ttf")))
    addMapping("DejaVu", 0, 0, "DejaVu")
    addMapping("DejaVu", 1, 0, "DejaVu-Bold")
    addMapping("DejaVu", 0, 1, "DejaVu-Italic")
    addMapping("DejaVu", 1, 1, "DejaVu-Bold")


def _styles() -> dict[str, Any]:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle

    base = ParagraphStyle("base", fontName="DejaVu", fontSize=9.2, leading=12.4,
                          textColor=colors.HexColor("#1e293b"))  # fmt: skip
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=7.8, leading=10),
        "tiny": ParagraphStyle("tiny", parent=base, fontSize=6.8, leading=8.6,
                               textColor=colors.HexColor("#475569")),
        "mono": ParagraphStyle("mono", parent=base, fontName="DejaVuMono", fontSize=7.2, leading=9.2),
        "h1": ParagraphStyle("h1", parent=base, fontName="DejaVu-Bold", fontSize=15, leading=19,
                             spaceBefore=6, spaceAfter=8, textColor=colors.HexColor("#0f172a")),
        "h2": ParagraphStyle("h2", parent=base, fontName="DejaVu-Bold", fontSize=11.5, leading=15,
                             spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#0b3b5c")),
        "h3": ParagraphStyle("h3", parent=base, fontName="DejaVu-Bold", fontSize=9.8, leading=13,
                             spaceBefore=6, spaceAfter=3, textColor=colors.HexColor("#0f172a")),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=10.2),
        "cellb": ParagraphStyle("cellb", parent=base, fontName="DejaVu-Bold", fontSize=8, leading=10.2),
        "cellh": ParagraphStyle("cellh", parent=base, fontName="DejaVu-Bold", fontSize=8, leading=10.2,
                                textColor=colors.white),
        "title": ParagraphStyle("title", parent=base, fontName="DejaVu-Bold", fontSize=22, leading=28,
                                textColor=colors.HexColor("#0f172a")),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=11, leading=15,
                                   textColor=colors.HexColor("#334155")),
    }  # fmt: skip


def esc(s: Any) -> str:
    return (str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))  # fmt: skip


def _table(rows: list[list[Any]], widths: list[float], header: bool = True,
           zebra: bool = True, extra: list[Any] | None = None) -> Any:  # fmt: skip
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]  # fmt: skip
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3b5c")),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]  # fmt: skip
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f1f5f9")))
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def _image(path: Path, max_w: float, max_h: float) -> Any:
    from PIL import Image as PILImage
    from reportlab.platypus import Image

    with PILImage.open(path) as im:
        w, h = im.size
    k = min(max_w / w, max_h / h, 1.0 * max_w / w)
    return Image(str(path), width=w * k, height=h * k)


def _thumb(svc: Any, ev: LabEvidence, analysis: EvidenceAnalysis | None) -> Path | None:
    """A preview image for the exhibit (the image itself, a key frame, or the spectrogram)."""
    art = svc.store.artifact_dir(ev.id)
    if ev.kind.value == "image":
        out = art / "_report_preview.jpg"
        if not out.exists():
            from PIL import Image, ImageOps

            try:
                img = ImageOps.exif_transpose(
                    Image.open(svc.store.evidence_path(ev.case_id, ev.sha256))
                )
                img = img.convert("RGB")
                img.thumbnail((900, 900))
                img.save(out, quality=85)
            except Exception:  # noqa: BLE001
                return None
        return out
    for name in ("contact_sheet.jpg", "spectrogram.png"):
        if (art / name).exists():
            return art / name
    return None


def _kv(rows: list[tuple[str, Any]], st: dict[str, Any], w: tuple[float, float]) -> Any:
    from reportlab.platypus import Paragraph

    data = [[Paragraph(f"<b>{esc(k)}</b>", st["cell"]), Paragraph(esc(v), st["cell"])]
            for k, v in rows]  # fmt: skip
    return _table(data, list(w), header=False)


def build_pdf(svc: Any, case: LabCase, items: list[tuple[LabEvidence, EvidenceAnalysis | None]],
              report_id: str, examiner: str, designation: str, notes: str) -> bytes:  # fmt: skip
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        CondPageBreak,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    _fonts()
    st = _styles()
    W, H = A4
    margin = 16 * mm
    usable = W - 2 * margin
    generated = utcnow()
    custody = svc.custody_view(case.id)
    links = svc.store.links(case.id)
    ids = {e.id for e, _ in items}
    exhibit_of = {e.id: e.exhibit for e in svc.store.case_evidence(case.id)}

    def on_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(
            margin, H - 10 * mm, f"{case.lab_name} — Multimedia Forensic Examination Report"
        )
        canvas.drawRightString(
            W - margin, H - 10 * mm, f"Report {report_id} · Case {case.fir_number or case.id}"
        )
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.line(margin, H - 11.5 * mm, W - margin, H - 11.5 * mm)
        canvas.drawString(
            margin,
            9 * mm,
            "CONFIDENTIAL — prepared for the investigating agency / court. "
            "Draft for the examiner's verification and signature.",
        )
        canvas.restoreState()

    from reportlab.pdfgen.canvas import Canvas

    class NumberedCanvas(Canvas):
        """Defers each page so the footer can say 'Page x of y'."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._pages: list[dict[str, Any]] = []

        def showPage(self) -> None:  # noqa: N802 - ReportLab API
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.setFont("DejaVu", 7)
                self.setFillColor(colors.HexColor("#64748b"))
                self.drawRightString(W - margin, 9 * mm, f"Page {self._pageNumber} of {total}")
                super().showPage()
            super().save()

    story: list[Any] = []
    # ------------------------------------------------------------------ cover
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph(esc(case.lab_name), st["subtitle"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Multimedia Forensic Examination Report", st["title"]))
    story.append(Paragraph("Authentication · Deepfake / synthetic-media detection · Tampering · "
                           "Provenance & source attribution", st["subtitle"]))  # fmt: skip
    story.append(Spacer(1, 10 * mm))
    cover = [
        ("Report number", report_id), ("Case", case.title),
        ("FIR / Case no.", case.fir_number or "—"),
        ("Police station / District / State",
         " / ".join(x for x in (case.police_station, case.district, case.state) if x) or "—"),
        ("Offence sections", case.offence_sections or "—"),
        ("Investigating officer", case.investigating_officer or "—"),
        ("Examiner", f"{examiner}{', ' + designation if designation else ''}"),
        ("Exhibits examined", ", ".join(f"{e.exhibit} ({e.filename})" for e, _ in items)),
        ("Report generated", ist(generated)),
        ("Engine", f"Satyapan Forensic Engine {ENGINE_VERSION} (offline workstation, {platform.system()})"),
        ("Custody chain head", custody["head"]),
    ]  # fmt: skip
    story.append(_kv(cover, st, (48 * mm, usable - 48 * mm)))
    story.append(Spacer(1, 8 * mm))
    qr_payload = json.dumps({"report": report_id, "case": case.id, "custody_head": custody["head"],
                             "exhibits": {e.exhibit: e.sha256 for e, _ in items}},
                            separators=(",", ":"))  # fmt: skip
    qr = QrCodeWidget(qr_payload)
    b = qr.getBounds()
    size = 34 * mm
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(qr)
    story.append(_table([[d, Paragraph(
        "<b>Verification code.</b> The QR code carries the report number, the case, the custody "
        "chain head at the time of reporting and the SHA-256 of every exhibit. Re-hash the "
        "exhibits and compare. The SHA-256 of this PDF is written to the case's custody log "
        "when it is generated.", st["small"])]], [size + 6 * mm, usable - size - 6 * mm],
        header=False, zebra=False,
        extra=[("GRID", (0, 0), (-1, -1), 0, colors.white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))  # fmt: skip
    story.append(PageBreak())

    # ------------------------------------------------------------------ 1. summary
    story.append(Paragraph("1. Summary of conclusions", st["h1"]))
    story.append(Paragraph(
        "Each exhibit was examined with every applicable technique listed in Section 3 and "
        "compared with the other exhibits of the case. The verdict for an exhibit follows a "
        "fixed rule table from the individual findings and is phrased on the ENFSI verbal scale "
        "of support. A single classifier score is at most moderate support; a firm conclusion "
        "needs a strong finding or two independent ones. Techniques that could not be applied "
        "are stated for each exhibit.", st["base"]))  # fmt: skip
    story.append(Spacer(1, 3 * mm))
    from satyapan.forensics.narrative import case_findings

    cf = case_findings([e for e, _ in items], {e.id: a for e, a in items},
                       [ln for ln in links if ln.source in ids and ln.target in ids],
                       custody["chain"]["ok"])  # fmt: skip
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("<b>Findings across the case</b>", st["h3"]))
    for sent in cf["sentences"]:
        story.append(Paragraph(f"• {esc(sent)}", st["base"]))
    story.append(Spacer(1, 3 * mm))
    rows: list[list[Any]] = [[Paragraph(h, st["cellh"]) for h in
                              ("Exhibit", "File", "Type", "Conclusion", "Statement")]]  # fmt: skip
    extra = []
    for i, (e, a) in enumerate(items, start=1):
        v = a.verdict if a else None
        label = v.label.value if v else "NOT ANALYSED"
        rows.append([Paragraph(f"<b>{esc(e.exhibit)}</b>", st["cell"]), Paragraph(esc(e.filename), st["cell"]),
                     Paragraph(esc(e.kind.value), st["cell"]),
                     Paragraph(f"<b>{esc(VERDICT_WORDS.get(label, label))}</b>", st["cell"]),
                     Paragraph(esc(v.statement if v else "Analysis not completed."), st["cell"])])  # fmt: skip
        col = colors.HexColor(VERDICT_COLOURS.get(label, "#475569"))
        extra += [("TEXTCOLOR", (3, i), (3, i), col)]
    story.append(_table(rows, [16 * mm, 34 * mm, 14 * mm, 28 * mm, usable - 92 * mm], extra=extra))
    if notes:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"<b>Examiner's notes.</b> {esc(notes)}", st["base"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<b>Scope.</b> The examination addresses whether the exhibits are synthetic (AI-generated "
        "or deepfaked), whether they were manipulated after capture, and what can be inferred "
        "about their origin. It does not establish who created or sent them; that is for the "
        "investigation. A finding of 'no indications' is not proof of authenticity.", st["small"]))  # fmt: skip

    # ------------------------------------------------------------------ 2. exhibits & hashes
    story.append(Paragraph("2. Exhibits received and hash values", st["h1"]))
    story.append(Paragraph(
        "Hash values were computed on the raw bytes at intake, before any parsing, and the "
        "stored copy was re-hashed and matched before each analysis. The originals are held "
        "write-once (read-only, named by their SHA-256) on the examination workstation.", st["base"]))  # fmt: skip
    story.append(Spacer(1, 2 * mm))
    for e, a in items:
        rows = [("Exhibit", f"{e.exhibit} — {e.role.value}"), ("File name", e.filename),
                ("Detected format", f"{a.media.format.upper() if a else e.mime} ({e.mime})"),
                ("Size", f"{e.size_bytes:,} bytes"), ("Received", ist(e.received_at)),
                ("Received from", e.received_from or "—"), ("Description", e.description or "—"),
                ("MD5", e.md5), ("SHA-1", e.sha1), ("SHA-256", e.sha256),
                ("Integrity re-verified", "Yes — SHA-256 matched intake before analysis"
                 if a and a.integrity_verified else "Not analysed")]  # fmt: skip
        story.append(KeepTogether([Paragraph(f"Exhibit {esc(e.exhibit)}", st["h3"]),
                                   _kv(rows, st, (40 * mm, usable - 40 * mm))]))  # fmt: skip

    # ------------------------------------------------------------------ 3. methodology
    story.append(PageBreak())
    story.append(Paragraph("3. Methodology, tools and standards", st["h1"]))
    story.append(Paragraph(
        "All processing ran offline on the examination workstation; no exhibit left it. "
        "Evidence handling follows ISO/IEC 27037 (identification, collection, acquisition and "
        "preservation of digital evidence) and the SWGDE best practices for image and audio "
        "authentication; reporting follows the ENFSI guideline for evaluative reporting. "
        "Statistical detectors were selected and their thresholds fixed on validation data "
        "before measuring them once on held-out test data (Section 7).", st["base"]))  # fmt: skip
    used = sorted({r.id for _, a in items if a for r in a.techniques},
                  key=lambda tid: catalogue.BY_ID[tid].order if tid in catalogue.BY_ID else 99)  # fmt: skip
    rows = [[Paragraph(h, st["cellh"]) for h in ("Technique", "Method", "Reference")]]
    for tid in used:
        t: Any = catalogue.BY_ID.get(tid)
        if t is None:  # case-level techniques describe themselves in the result
            t = next((r for _, a in items if a for r in a.techniques if r.id == tid), None)
        if t is None or not t.method:
            continue
        rows.append([Paragraph(f"<b>{esc(t.name)}</b><br/><font size=6.5 color='#64748b'>{esc(t.id)}</font>",
                               st["cell"]), Paragraph(esc(t.method), st["cell"]),
                     Paragraph(esc(t.reference or "—"), st["cell"])])  # fmt: skip
    story.append(_table(rows, [34 * mm, usable - 34 * mm - 42 * mm, 42 * mm]))
    models = svc.models.status()
    story.append(Paragraph("Models available on this workstation", st["h3"]))
    rows = [[Paragraph(h, st["cellh"]) for h in ("Component", "Purpose", "Status")]]
    for k, v in models.items():
        rows.append([Paragraph(esc(v.get("model") or k), st["cell"]),
                     Paragraph(esc(v.get("purpose", "")), st["cell"]),
                     Paragraph("available" if v.get("available") else
                               f"not installed {esc(v.get('detail', ''))[:80]}", st["cell"])])  # fmt: skip
    story.append(_table(rows, [50 * mm, usable - 50 * mm - 40 * mm, 40 * mm]))

    # ------------------------------------------------------------------ 4. per exhibit
    for n_ex, (e, a) in enumerate(items, start=1):
        story.append(PageBreak())
        story.append(Paragraph(f"4.{n_ex} Examination of exhibit {esc(e.exhibit)}: {esc(e.filename)}",
                               st["h1"]))  # fmt: skip
        if a is None or a.verdict is None:
            story.append(Paragraph("This exhibit has not been analysed.", st["base"]))
            continue
        v = a.verdict
        col = colors.HexColor(VERDICT_COLOURS.get(v.label.value, "#475569"))
        box = _table([[Paragraph(f"<font color='white'><b>{esc(VERDICT_WORDS[v.label.value])}</b></font>",
                                 st["cellb"]),
                       Paragraph(f"<b>{esc(v.headline)}</b><br/>{esc(v.statement)}", st["cell"])]],
                     [38 * mm, usable - 38 * mm], header=False, zebra=False,
                     extra=[("BACKGROUND", (0, 0), (0, 0), col), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("BOX", (0, 0), (-1, -1), 1.2, col)])  # fmt: skip
        story.append(box)
        story.append(Spacer(1, 3 * mm))
        m = a.media
        media_rows = [
            (
                "Format",
                f"{m.format.upper()} ({m.mime})"
                + (" — extension does not match content" if m.extension_mismatch else ""),
            )
        ]
        if m.width:
            media_rows.append(("Dimensions", f"{m.width} × {m.height} px"))
        if m.duration_s:
            media_rows.append(("Duration", f"{m.duration_s:.2f} s"))
        if m.fps:
            media_rows.append(("Frame rate", f"{m.fps:.2f} fps"))
        if m.sample_rate:
            media_rows.append(
                ("Audio", f"{m.audio_codec or m.codec} {m.sample_rate} Hz, {m.channels} ch")
            )
        if m.codec and m.kind.value == "video":
            media_rows.append(("Video codec", m.codec))
        media_rows.append(("Examination", f"{ist(a.started_at)} → {ist(a.finished_at)}; "
                           f"{len(a.techniques)} techniques"))  # fmt: skip
        thumb = _thumb(svc, e, a)
        left = _kv(media_rows, st, (26 * mm, 70 * mm))
        if thumb is not None:
            story.append(_table([[left, _image(thumb, usable - 104 * mm, 62 * mm)]],
                                [98 * mm, usable - 98 * mm], header=False, zebra=False,
                                extra=[("GRID", (0, 0), (-1, -1), 0, colors.white)]))  # fmt: skip
        else:
            story.append(left)
        story.append(Paragraph("Findings", st["h2"]))
        rows = [
            [Paragraph(h, st["cellh"]) for h in ("Technique", "Finding", "Supports", "Strength")]
        ]
        extra = []
        ri = 0
        for r in a.techniques:
            for f in r.findings:
                if f.hypothesis == Hypothesis.NEUTRAL and f.code not in (
                        "CAMERA_IDENTIFIED", "DEVICE_METADATA", "PLATFORM_TRACE", "FRAUD_LANGUAGE",
                        "BANDWIDTH_LIMIT", "ENCODER_TAG", "XMP_HISTORY", "C2PA_EDIT_HISTORY",
                        "GPS_LOCATION", "PRIOR_JPEG_COMPRESSION", "SHOT_BOUNDARIES"):  # fmt: skip
                    continue
                ri += 1
                rows.append([Paragraph(esc(r.name), st["cell"]),
                             Paragraph(f"<b>{esc(f.title)}</b><br/>{esc(f.detail)}", st["cell"]),
                             Paragraph(esc(f.hypothesis.value if f.hypothesis != Hypothesis.NEUTRAL
                                           else "context"), st["cell"]),
                             Paragraph(esc(STRENGTH_WORDS[f.strength] if f.strength else "—"), st["cell"])])  # fmt: skip
                if f.strength >= Strength.STRONG and f.hypothesis in (
                    Hypothesis.SYNTHETIC,
                    Hypothesis.MANIPULATED,
                ):
                    extra.append(("BACKGROUND", (0, ri), (-1, ri), colors.HexColor("#fee2e2")))
        if ri == 0:
            rows.append([Paragraph("—", st["cell"]), Paragraph("No positive findings.", st["cell"]),
                         Paragraph("", st["cell"]), Paragraph("", st["cell"])])  # fmt: skip
        story.append(
            _table(rows, [30 * mm, usable - 30 * mm - 44 * mm, 20 * mm, 24 * mm], extra=extra)
        )
        figs = []
        for r in a.techniques:
            for art in r.artifacts:
                if art.kind in ("overlay", "heatmap", "spectrogram", "crop", "figure"):
                    p = svc.store.artifact_dir(e.id) / art.name
                    if p.exists() and art.name not in ("ela.jpg", "noise_map.jpg", "spectrum.png"):
                        figs.append((art, p, r))
        diff = [ln for ln in links if ln.source == e.id and ln.artifacts]
        for ln in diff[:2]:
            p = svc.store.artifact_dir(e.id) / ln.artifacts[0]
            if p.exists():
                from satyapan.forensics.models import Artifact

                figs.append((Artifact(name=ln.artifacts[0], kind="figure",
                                      title=f"Comparison with {exhibit_of.get(ln.target, ln.target)}",
                                      caption="Left: the other exhibit with changed regions boxed. "
                                      "Middle: this exhibit aligned onto it. Right: difference."), p, None))  # fmt: skip
        if figs:
            story.append(CondPageBreak(70 * mm))
            story.append(Paragraph("Figures", st["h2"]))
            for art, p, r in figs[:6]:
                story.append(KeepTogether([
                    _image(p, usable, 78 * mm),
                    Paragraph(f"<b>Figure — {esc(art.title)}</b>"
                              + (f" ({esc(r.name)})" if r else "") + f". {esc(art.caption)}", st["small"]),
                    Spacer(1, 3 * mm)]))  # fmt: skip
        pv = a.provenance
        prov_rows = [(k, v) for k, v in (
            ("Device", pv.device), ("Software", pv.software), ("Platform", pv.platform),
            ("Generator", pv.generator), ("Capture time", pv.capture_time),
            ("GPS", f"{pv.gps['lat']:.5f}, {pv.gps['lon']:.5f}" if pv.gps else None),
            ("Content Credentials", pv.content_credentials)) if v]  # fmt: skip
        story.append(Paragraph("Provenance and source attribution", st["h2"]))
        if prov_rows:
            story.append(_kv(prov_rows, st, (36 * mm, usable - 36 * mm)))
        if pv.chain:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("<b>Reconstructed history:</b> " + " → ".join(esc(c) for c in pv.chain),
                                   st["base"]))  # fmt: skip
        if not prov_rows and not pv.chain:
            story.append(Paragraph("No device, software, platform or generator could be attributed "
                                   "from the file itself.", st["base"]))  # fmt: skip
        story.append(Paragraph("Technique log", st["h2"]))
        rows = [[Paragraph(h, st["cellh"]) for h in ("Technique", "Status", "Result", "Time")]]
        for r in a.techniques:
            rows.append([Paragraph(esc(r.name), st["cell"]), Paragraph(esc(r.status.value), st["cell"]),
                         Paragraph(esc(r.summary), st["cell"]), Paragraph(f"{r.duration_ms / 1000:.2f} s", st["cell"])])  # fmt: skip
        story.append(
            _table(rows, [42 * mm, 20 * mm, usable - 42 * mm - 20 * mm - 16 * mm, 16 * mm])
        )
        if v.not_checked:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph("<b>Could not be checked:</b> " + "; ".join(esc(x) for x in v.not_checked),
                                   st["small"]))  # fmt: skip
        lims = [catalogue.BY_ID[r.id].limitations for r in a.techniques
                if r.status == Status.OK and r.id in catalogue.BY_ID and catalogue.BY_ID[r.id].limitations]  # fmt: skip
        if lims:
            story.append(Paragraph("<b>Known limits of the techniques applied:</b> "
                                   + " ".join(esc(x) for x in dict.fromkeys(lims)), st["small"]))  # fmt: skip

    # ------------------------------------------------------------------ 5. links
    story.append(PageBreak())
    story.append(Paragraph("5. Relationships between exhibits", st["h1"]))
    rel = [ln for ln in links if ln.source in ids or ln.target in ids]
    seen: set[tuple[str, str, str]] = set()
    rows = [[Paragraph(h, st["cellh"]) for h in ("Exhibits", "Relationship", "Score", "Detail")]]
    for ln in rel:
        key = tuple(sorted((ln.source, ln.target))) + (ln.kind.value,)
        if key in seen:
            continue
        seen.add(key)  # type: ignore[arg-type]
        rows.append([Paragraph(f"{esc(exhibit_of.get(ln.source, ln.source))} ↔ "
                               f"{esc(exhibit_of.get(ln.target, ln.target))}", st["cell"]),
                     Paragraph(esc(ln.kind.value.replace('_', ' ')), st["cell"]),
                     Paragraph(f"{ln.score:.2f}", st["cell"]), Paragraph(esc(ln.detail), st["cell"])])  # fmt: skip
    if len(rows) == 1:
        story.append(Paragraph("No relationships (shared content, device, voice, face or "
                               "generator) were found between the exhibits.", st["base"]))  # fmt: skip
    else:
        story.append(_table(rows, [24 * mm, 28 * mm, 14 * mm, usable - 66 * mm]))

    # ------------------------------------------------------------------ 6. custody
    story.append(Paragraph("6. Chain of custody", st["h1"]))
    chain = custody["chain"]
    story.append(Paragraph(
        "Every action on the case is a row in an append-only log; each row's hash covers the "
        "previous row's hash (SHA-256), so any later edit, deletion or re-ordering breaks the "
        f"chain. Verification at report time: <b>{'INTACT' if chain['ok'] else 'BROKEN'}</b> "
        f"({chain['rows_checked']} rows checked across the workstation log).", st["base"]))  # fmt: skip
    rows = [
        [Paragraph(h, st["cellh"]) for h in ("#", "Time", "Event", "By", "Details", "Row hash")]
    ]
    for r in custody["rows"]:
        pl = r["payload"]
        detail = ", ".join(f"{k}: {v}" for k, v in pl.items() if k in (
            "action", "exhibit", "filename", "verdict", "risk_index", "report_id", "pdf_sha256",
            "analysis_sha256", "sha256", "title"))  # fmt: skip
        rows.append([Paragraph(str(r["seq"]), st["cell"]), Paragraph(esc(ist(r["at"])), st["cell"]),
                     Paragraph(esc(r["event"]), st["cell"]), Paragraph(esc(r["actor"]), st["cell"]),
                     Paragraph(esc(detail)[:400], st["small"]),
                     Paragraph(esc(r["row_hash"][:16]) + "…", st["mono"])])  # fmt: skip
    story.append(_table(rows, [8 * mm, 30 * mm, 20 * mm, 20 * mm, usable - 108 * mm, 30 * mm]))

    # ------------------------------------------------------------------ 7. error rates
    story.append(PageBreak())
    story.append(Paragraph("7. Known error rates and limitations", st["h1"]))
    story.append(Paragraph(
        "Statistical techniques were evaluated on public data with thresholds fixed beforehand. "
        "Rates below are from held-out test sets; real casework can differ (compression, new "
        "generators), which is why every conclusion rests on several independent techniques.",
        st["base"]))  # fmt: skip
    story.append(Spacer(1, 2 * mm))
    story.append(_table([[Paragraph(h, st["cellh"]) for h in ("Technique", "Test data", "Measured performance")]]
                        + [[Paragraph(esc(a_), st["cell"]), Paragraph(esc(b_), st["cell"]),
                            Paragraph(esc(c_), st["cell"])] for a_, b_, c_ in error_rate_rows()],
                        [40 * mm, 50 * mm, usable - 90 * mm]))  # fmt: skip
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "General limitations: a negative result is not proof of authenticity; metadata and "
        "signatures can be removed or forged; heavy compression, resizing and screenshots "
        "weaken pixel-level traces; detectors trained on known generators may miss new ones; "
        "voice detection is weakened by background noise. Conclusions should be read together "
        "with the investigation's other evidence.", st["base"]))  # fmt: skip

    # ------------------------------------------------------------------ 8. certificate
    story.append(PageBreak())
    story.append(
        Paragraph(
            "8. Certificate under Section 63(4)(c), Bharatiya Sakshya Adhiniyam, 2023", st["h1"]
        )
    )
    story.append(Paragraph(
        "<i>Draft prepared by the Satyapan Forensic Lab for the examiner's verification. It "
        "must be checked, completed and signed by hand by the person giving it; the software "
        "does not sign on anyone's behalf. Part A is completed by the party producing the "
        "record.</i>", st["small"]))  # fmt: skip
    story.append(Paragraph(
        "<i>Legal basis.</i> The examiner's opinion on information stored in electronic form is a "
        "relevant fact under Section 39(2) BSA 2023 when given by an Examiner of Electronic "
        "Evidence notified under Section 79A of the Information Technology Act, 2000, and under "
        "Section 39(1) as the opinion of an expert otherwise; where the examiner is a Government "
        "scientific expert to whom Section 329 BNSS 2023 applies, the report may be used in "
        "evidence under that section. This certificate accompanies the electronic records "
        "themselves (Section 63).", st["small"]))  # fmt: skip
    story.append(Paragraph("PART B (to be filled by the Expert)", st["h2"]))
    story.append(Paragraph(
        "I, ____________________ (name), son / daughter / spouse of ____________________, "
        f"residing / employed at {esc(case.lab_name)} as "
        f"{esc(designation) or '____________________'} (designation), do hereby solemnly affirm "
        "and sincerely state and submit as follows:", st["base"]))  # fmt: skip
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "The produced electronic record / output of the digital record listed below was "
        "obtained from the following device / digital record source (tick): "
        "☐ Computer / Storage media  ☐ DVR  ☐ Mobile  ☐ Flash drive  ☐ CD/DVD  ☐ Server  "
        "☐ Cloud  ☐ Other: ____________. Make &amp; model: ____________  Colour: ________  "
        "Serial number: ____________  IMEI / UIN / UID / MAC / Cloud ID (as applicable): "
        "____________, and any other relevant information about the device / digital record: "
        "____________.", st["base"]))  # fmt: skip
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("I state that the hash values of the electronic / digital records are as "
                           "follows, obtained through the algorithms ☑ SHA-256 ☑ SHA-1 ☑ MD5 "
                           "(hash report enclosed as Section 2 of this report):", st["base"]))  # fmt: skip
    rows = [[Paragraph(h, st["cellh"]) for h in ("Exhibit", "SHA-256", "SHA-1 / MD5")]]
    for e, _ in items:
        rows.append([Paragraph(esc(e.exhibit), st["cell"]), Paragraph(esc(e.sha256), st["mono"]),
                     Paragraph(f"{esc(e.sha1)}<br/>{esc(e.md5)}", st["mono"])])  # fmt: skip
    story.append(_table(rows, [16 * mm, 86 * mm, usable - 102 * mm]))
    story.append(Spacer(1, 8 * mm))
    story.append(_kv([("Name, designation and signature", ""), ("Date (DD/MM/YYYY)", ""),
                      ("Time (IST, hh:mm, 24 h)", ""), ("Place", "")], st, (60 * mm, usable - 60 * mm)))  # fmt: skip
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("PART A (to be filled by the Party) — attach separately as per the Schedule.",
                           st["small"]))  # fmt: skip

    # ------------------------------------------------------------------ 9. glossary
    story.append(Paragraph("9. Glossary", st["h1"]))
    gl = [("Hash value (SHA-256)", "A fingerprint of the exact bytes; any change produces a different value."),
          ("Deepfake", "Video or image in which a face is swapped, re-enacted or generated by AI."),
          ("Synthetic voice / voice clone", "Speech produced by text-to-speech or voice conversion imitating a person."),
          ("ELA", "Error Level Analysis: how much each area changes when the image is re-compressed."),
          ("ENF", "Electrical Network Frequency: the mains hum (50 Hz in India) whose drift time-stamps recordings."),
          ("C2PA / Content Credentials", "A signed record, embedded in a file, of how it was created and edited."),
          ("Copy-move", "Part of an image copied to another place in the same image."),
          ("Verbal scale", "ENFSI wording (weak / moderate / strong / very strong support) for the strength of findings."),
          ("Custody chain", "Append-only log in which each entry's hash includes the previous entry's hash.")]  # fmt: skip
    story.append(_table([[Paragraph(f"<b>{esc(a_)}</b>", st["cell"]), Paragraph(esc(b_), st["cell"])] for a_, b_ in gl],
                        [44 * mm, usable - 44 * mm], header=False))  # fmt: skip

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=16 * mm, bottomMargin=15 * mm,
                            title=f"Forensic report {report_id}", author=case.lab_name,
                            subject=case.title, creator="Satyapan Forensic Lab")  # fmt: skip
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page, canvasmaker=NumberedCanvas)
    return buf.getvalue()


def error_rate_rows() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[4]
    rows: list[tuple[str, str, str]] = []
    try:
        spec = json.loads((root / "config" / "aigen_model.json").read_text())
        m = spec.get("metrics", {})
        rows.append(("AI-generated image classifier", m.get("dataset", "Defactify test"),
                     f"AUC {m.get('test_auc_native', 0):.3f}; at the strict threshold "
                     f"{m.get('test_tpr_at_tau_hi', 0):.0%} of AI images flagged, "
                     f"{m.get('test_fpr_at_tau_hi', 0):.1%} of real photos flagged"))  # fmt: skip
    except (OSError, ValueError):
        pass
    rows += [
        ("Face-swap detector (GenD)", "FaceForensics++ c23 test; DFDC (unseen)",
         "Video AUC 0.946 (FF++), 0.778 (DFDC); 0 of 563 real videos called synthetic; "
         "photo crops AUC 0.923 / 0.747"),
        ("Synthetic voice detector", "In-the-Wild deepfake speech (unseen speakers)",
         "AUC 0.921 clean, 0.909 after Opus compression; 0.6% of genuine voices flagged; "
         "10 dB background noise reduces detection sharply"),
    ]  # fmt: skip
    try:
        res = json.loads((root / "results" / "forensics_classical.json").read_text())
        tpr = res["test_tpr"]
        fpr = res["test_fpr"]
        rows.append(("Classical tampering detectors", f"{res['n_test_reals']} genuine COCO photos + synthetic forgeries",
                     f"genuine flagged (moderate) {fpr.get('any_moderate', 0):.1%}; copy-move detected "
                     f"{tpr['copy_move']['copymove']['moderate']:.0%}; splices flagged by any detector "
                     f"{tpr['splice']['any_moderate']:.0%}; crop-recompress {tpr['crop_recompress']['any_moderate']:.0%}"))  # fmt: skip
    except (OSError, ValueError, KeyError):
        pass
    return rows


def generate_report(svc: Any, case_id: str, evidence_ids: list[str], examiner: str,
                    designation: str, notes: str, actor: str) -> dict[str, Any]:  # fmt: skip
    case = svc.store.case(case_id)
    if case is None:
        raise ValueError("case not found")
    evs = svc.store.case_evidence(case_id)
    if evidence_ids:
        evs = [e for e in evs if e.id in set(evidence_ids)]
    if not evs:
        raise ValueError("no exhibits to report on")
    items = [(e, svc.store.analysis(e.id)) for e in evs]
    report_id = f"SFL-{utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"
    pdf = build_pdf(svc, case, items, report_id, examiner, designation, notes)
    path = svc.store.report_path(case_id, report_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf)
    digest = hashlib.sha256(pdf).hexdigest()
    rec = {"id": report_id, "case_id": case_id, "created_at": utcnow().isoformat(),
           "examiner": examiner, "designation": designation, "sha256": digest,
           "size_bytes": len(pdf), "exhibits": [e.exhibit for e in evs],
           "url": f"/lab/api/reports/{report_id}.pdf"}  # fmt: skip
    svc.store.put_report(case_id, report_id, rec)
    svc.store.log(case_id=case_id, event=CustodyEvent.EXPORT, actor=actor,
                             payload={"action": "report_generated", "report_id": report_id,
                                      "pdf_sha256": digest, "exhibits": rec["exhibits"]})  # fmt: skip
    return rec
