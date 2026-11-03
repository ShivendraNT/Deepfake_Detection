"""M6 — Automated Multimedia Forensic Report Generator (`src/satyapan/forensics/report.py`).

Generates reproducible one-click forensic reports per case in:
- `forensic_report.pdf` (native PDF 1.4 with vector text + embedded JPEG heatmaps/spectrograms);
- `forensic_report.html` (self-contained offline HTML report with inline base64 evidence images);
- `forensic_report.md` (structured Markdown report + Section 63 BSA 2023 Parts A & B);
- `forensic_report.json` (deterministic machine-readable report + Section 63 certificate).

Reproducibility guarantee: Given the same stored case data (`analysis.json` / `evidence.json` /
`custody.jsonl`) and timestamp, `generate_forensic_report` produces byte-identical outputs.
"""

from __future__ import annotations

import base64
import html
import io
import json
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image

from satyapan.forensics.locker import ForensicLocker
from satyapan.forensics.pipeline import load_case_analysis
from satyapan.forensics.section63 import (
    build_section63_certificate,
    render_section63_markdown,
)


def _pdf_escape(text: str) -> str:
    """Escape a string for a PDF literal string `(...)`, replacing non-ASCII with ASCII equivalents."""
    clean = (
        text.replace("×", "x")
        .replace("—", "--")
        .replace("–", "-")
        .replace("·", "-")
        .replace("≥", ">=")
        .replace("≤", "<=")
        .replace("±", "+/-")
        .replace("…", "...")
        .encode("ascii", errors="replace")
        .decode("ascii")
    )
    return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_forensic_pdf(
    md_text: str,
    image_blocks: list[tuple[str, Path]],
    out_pdf: Path,
) -> None:
    """Build a valid, multi-page PDF 1.4 document with searchable vector text (Helvetica /
    Helvetica-Bold / Courier) AND embedded forensic evidence images (`XObject /Image /DCTDecode`).
    Zero external library dependencies beyond Pillow.
    """
    page_w, page_h = 595, 842  # A4 in points (72 dpi)
    margin_l, margin_t, margin_b = 42, 46, 46
    usable_h = page_h - margin_t - margin_b

    # Convert markdown into styled text lines for the text pages
    styled_lines: list[tuple[str, int, str]] = []  # (font_key, size_pt, text)
    for raw_ln in md_text.splitlines():
        ln = raw_ln.rstrip()
        if not ln:
            styled_lines.append(("F1", 9, ""))
            continue
        if ln.startswith("# "):
            for w in textwrap.wrap(ln[2:], width=62):
                styled_lines.append(("F2", 15, w))
        elif ln.startswith("## "):
            styled_lines.append(("F1", 6, ""))
            for w in textwrap.wrap(ln[3:], width=70):
                styled_lines.append(("F2", 12, w))
        elif ln.startswith("### "):
            for w in textwrap.wrap(ln[4:], width=76):
                styled_lines.append(("F2", 10, w))
        elif ln.startswith("|"):
            for w in textwrap.wrap(ln, width=96):
                styled_lines.append(("F3", 7, w))
        elif ln.startswith(">"):
            for w in textwrap.wrap(ln.lstrip("> ").strip("*"), width=82):
                styled_lines.append(("F2", 9, w))
        else:
            clean_ln = ln.replace("**", "").replace("`", "")
            for w in textwrap.wrap(clean_ln, width=88):
                styled_lines.append(("F1", 9, w))

    # Paginate text lines
    text_pages: list[list[tuple[str, int, str]]] = []
    cur_page: list[tuple[str, int, str]] = []
    cur_y = 0
    for fkey, fsize, txt in styled_lines:
        step = fsize + 4
        if cur_y + step > usable_h and cur_page:
            text_pages.append(cur_page)
            cur_page = []
            cur_y = 0
        cur_page.append((fkey, fsize, txt))
        cur_y += step
    if cur_page:
        text_pages.append(cur_page)

    # Prepare JPEG bytes for embedded evidence images (up to 2 images per visual appendix page)
    prepared_imgs: list[tuple[str, bytes, int, int]] = []
    for caption, img_path in image_blocks:
        if not img_path.exists():
            continue
        try:
            with Image.open(img_path) as im:
                rgb = im.convert("RGB")
                img_w, img_h = rgb.size
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=88)
                prepared_imgs.append((caption, buf.getvalue(), int(img_w), int(img_h)))
        except Exception:  # noqa: BLE001
            continue

    # Assemble PDF objects
    # Obj 1: Catalog, Obj 2: Pages, Obj 3: Helvetica (F1), Obj 4: Helvetica-Bold (F2), Obj 5: Courier (F3)
    objects: dict[int, bytes] = {}
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"
    objects[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"

    next_id = 6
    page_ids: list[int] = []

    # 1. Build text pages
    for p_idx, p_lines in enumerate(text_pages, 1):
        stream_cmds: list[str] = ["BT"]
        y = page_h - margin_t
        for fkey, fsize, txt in p_lines:
            y -= fsize + 4
            if txt:
                stream_cmds.append(
                    f"/{fkey} {fsize} Tf 1 0 0 1 {margin_l} {y} Tm ({_pdf_escape(txt)}) Tj"
                )
        # Footer
        stream_cmds.append(
            f"/F1 8 Tf 1 0 0 1 {margin_l} 24 Tm "
            f"(Satyapan x Pramaan Forensic Report -- Page {p_idx}) Tj"
        )
        stream_cmds.append("ET")
        stream_bytes = "\n".join(stream_cmds).encode("ascii")

        content_id = next_id
        page_id = next_id + 1
        next_id += 2

        objects[content_id] = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")
        page_ids.append(page_id)

    # 2. Build visual evidence pages (2 images per page)
    for chunk_start in range(0, len(prepared_imgs), 2):
        pair = prepared_imgs[chunk_start : chunk_start + 2]
        xobj_refs: list[str] = []
        stream_cmds = [
            "BT",
            f"/F2 13 Tf 1 0 0 1 {margin_l} {page_h - margin_t} Tm "
            "(Visual Forensic Evidence Appendix \\(Heatmaps & Spectrograms\\)) Tj",
            "ET",
        ]
        y_cursor = page_h - margin_t - 28

        for local_i, (caption, jpg_bytes, iw, ih) in enumerate(pair):
            img_obj_id = next_id
            next_id += 1
            im_name = f"Im{local_i}"
            objects[img_obj_id] = (
                f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpg_bytes)} >>\nstream\n".encode("ascii")
                + jpg_bytes
                + b"\nendstream"
            )
            xobj_refs.append(f"/{im_name} {img_obj_id} 0 R")

            # Draw caption
            stream_cmds.extend(
                [
                    "BT",
                    f"/F2 10 Tf 1 0 0 1 {margin_l} {y_cursor} Tm ({_pdf_escape(caption)}) Tj",
                    "ET",
                ]
            )
            y_cursor -= 14

            # Scale image to fit width <= 500 and height <= 290
            disp_w = min(500.0, float(iw))
            disp_h = disp_w * (float(ih) / max(1.0, float(iw)))
            if disp_h > 290.0:
                disp_h = 290.0
                disp_w = disp_h * (float(iw) / max(1.0, float(ih)))

            y_img_bottom = int(y_cursor - disp_h)
            stream_cmds.append(
                f"q {disp_w:.1f} 0 0 {disp_h:.1f} {margin_l} {y_img_bottom} cm /{im_name} Do Q"
            )
            y_cursor = y_img_bottom - 26

        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        stream_bytes = "\n".join(stream_cmds).encode("ascii")
        objects[content_id] = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        xobj_dict = " ".join(xobj_refs)
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> "
            f"/XObject << {xobj_dict} >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")
        page_ids.append(page_id)

    kids_str = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_ids)} >>".encode("ascii")

    # Serialize PDF with xref table
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    max_obj_id = max(objects.keys())
    for oid in range(1, max_obj_id + 1):
        offsets[oid] = len(out)
        out.extend(f"{oid} 0 obj\n".encode("ascii"))
        out.extend(objects[oid])
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {max_obj_id + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for oid in range(1, max_obj_id + 1):
        out.extend(f"{offsets[oid]:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {max_obj_id + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    out_pdf.write_bytes(bytes(out))


def generate_forensic_report(
    locker: ForensicLocker,
    *,
    declarant: dict[str, str] | None = None,
    examiner: dict[str, Any] | None = None,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    """Generate reproducible `forensic_report.{md,json,html,pdf}` inside `<case_dir>/report/`
    from the stored case data."""
    case_analysis = load_case_analysis(locker)
    meta = case_analysis.get("case_meta") or locker.case_meta()
    integ = case_analysis.get("integrity") or locker.integrity_info()
    items = case_analysis.get("items") or []
    custody_log = case_analysis.get("custody_log") or []
    timeline = case_analysis.get("timeline") or []
    limitations = case_analysis.get("limitations_of_analysis") or []

    # Use fixed_timestamp or the stored analysis timestamp so reports are byte-reproducible
    report_ts = fixed_timestamp or str(case_analysis.get("generated_at_utc") or "")

    decl = declarant or {
        "name": str(meta.get("examiner") or locker.collector),
        "role": "Evidence Custodian / Submitting Officer",
    }
    exam = examiner or {
        "name": str(meta.get("examiner") or locker.collector),
        "designation": "Senior Digital Forensic Examiner",
        "organisation": str(meta.get("agency") or "Digital Forensics Laboratory"),
    }

    cert = build_section63_certificate(
        locker.items(),
        decl,
        examiner=exam,
        integrity=integ,
        generated_at_utc=report_ts,
    )
    cert_md = render_section63_markdown(cert)

    md: list[str] = []
    if not integ.get("ok", False):
        md.append(
            "> **CRITICAL LOCKER INTEGRITY WARNING: TAMPERED / FAILED** - At least one sealed "
            "record, custody link, or signature failed verification. Treat all conclusions "
            "with caution."
        )
        md.append("")

    md.extend(
        [
            f"# Multimedia Forensic Examination Report — Case `{locker.case_id}`",
            "",
            f"**Case Title**: {meta.get('title', locker.case_id)}  ",
            f"**Submitting Agency / Lab**: {meta.get('agency', 'Digital Forensics Laboratory')}  ",
            f"**FIR / Reference**: {meta.get('fir_reference', 'N/A')}  ",
            f"**Lead Examiner**: {exam['name']} ({exam['designation']})  ",
            f"**Report Generated (UTC)**: {report_ts}  ",
            f"**Locker Integrity Status**: {integ.get('status', 'UNKNOWN')}  ",
            f"**Custody Chain Head**: `{integ.get('chain_head', '')}`  ",
            f"**RFC 6962 Merkle Root**: `{integ.get('merkle_root', '')}`  ",
            "",
            "## 1. Executive Summary & Decision Boundary",
            "",
            "This report presents the results of an offline, multi-modal forensic examination "
            f"conducted on {len(items)} sealed electronic multimedia record(s). Every analysis "
            "was executed on an isolated working copy verified against the intake SHA-256 hash, "
            "while original exhibits remained read-only (`0o444`). All findings are stated as "
            "*consistent with* or *inconsistent with* manipulation/synthetic generation and are "
            "accompanied by calibrated confidence scores and methodological limitations. "
            "**This system assists a human forensic examiner; it never decides guilt or legal "
            "admissibility.**",
            "",
            "## 2. Schedule of Sealed Multimedia Evidence & SHA-256 Hashes",
            "",
            "| Evidence ID | File Name | Modality | Size (Bytes) | Intake SHA-256 | Read-Only (`0o444`) | Merkle Proof | Assessment | Confidence |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )

    merkle_proofs = case_analysis.get("merkle_proofs") or {}
    for it in items:
        eid = it["evidence_id"]
        mp = merkle_proofs.get(eid) or {}
        ro_txt = "YES" if mp.get("readonly_intact", True) else "NO"
        mk_txt = "VERIFIED" if mp.get("verified", False) else "FAILED"
        md.append(
            f"| {eid} | {it['original_name']} | {it['source_type']} | {it['size_bytes']} | "
            f"`{it['sha256']}` | {ro_txt} | {mk_txt} | **{it['overall_finding']}** | "
            f"{it['overall_confidence']:.2f} |"
        )
    md.append("")

    md.extend(
        [
            "## 3. Cryptographic Chain of Custody (`custody.jsonl`)",
            "",
            "| Seq | Timestamp (UTC) | Evidence ID | Action | Actor / Signer | File SHA-256 (Prefix) | Chain Link (Prefix) | Ed25519 Signature (Prefix) |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for ce in custody_log:
        md.append(
            f"| {ce['seq']} | {ce['time_utc']} | {ce['evidence_id']} | {ce['action']} | "
            f"{ce['actor']} | `{ce['file_sha256'][:16]}...` | `{ce['link'][:16]}...` | "
            f"`{ce['signature'][:16]}...` |"
        )
    md.append("")

    md.extend(
        [
            "## 4. Forensic Methodology",
            "",
            "1. **Evidence Sealing & Working-Copy Isolation (M1)**: Raw bytes are hashed with "
            "SHA-256 (FIPS 180-4) prior to parsing, sealed in `originals/` with `0o444` read-only "
            "permissions, signed with Ed25519 (RFC 8032), and anchored in an RFC 6962 Merkle tree.",
            "2. **Deepfake & Synthetic Media Engine (M2)**: Combines `GenD` CLIP ViT-L/14 ONNX "
            "face-swap detection, whole-image diffusion/GAN spectral checkerboard & photon-transfer "
            "noise checks, frame-level + 6s window video fusion, and `Gustking` XLS-R ONNX "
            "voice-clone detection.",
            "3. **Tampering & Manipulation Detection (M3)**: Executes edge-normalized Error Level "
            "Analysis (ELA), Lukas-Fridrich 8x8 DCT double-JPEG comb & block-grid analysis, "
            "lexicographic block-descriptor + Laplacian high-pass copy-move forgery detection, "
            "noise-residual variance outlier mapping, video duplicated/dropped frame detection, "
            "and audio splice transient + room noise-floor step analysis.",
            "4. **Provenance & Source Attribution (M4)**: Verifies EXIF/XMP/PNG timestamp "
            "chronology, editing/AI software tags, GPS plausibility, embedded APP1 thumbnail vs "
            "main image consistency, C2PA JUMBF Content Credentials, and 3-class compression "
            "fingerprint attribution (`camera_original`, `social_messaging_reencode`, "
            "`editing_software_resave`).",
            "",
            "## 5. Detailed Per-Exhibit Forensic Findings",
            "",
        ]
    )

    image_blocks: list[tuple[str, Path]] = []
    for it in items:
        eid = it["evidence_id"]
        df = it.get("deepfake") or {}
        tm = it.get("tampering") or {}
        pr = it.get("provenance") or {}
        md.extend(
            [
                f"### Exhibit {eid} — `{it['original_name']}` ({it['source_type'].upper()})",
                "",
                f"- **SHA-256**: `{it['sha256']}`",
                f"- **Source Device**: `{it['device']}`",
                f"- **Overall Assessment**: **{it['overall_finding']}** "
                f"(Calibrated Confidence: **{it['overall_confidence']:.2f}**)",
                f"- **Conclusion**: {it['overall_statement']}",
                "",
                "**Technical Indicators ('Why'):**",
            ]
        )
        for w in it.get("why") or []:
            md.append(f"- {w}")
        if df:
            md.append(
                f"- **Deepfake / Synthetic Sub-Engine**: `{df.get('finding')}` "
                f"(synthetic likelihood `{df.get('synthetic_probability')}`, "
                f"models: `{', '.join(df.get('models_used') or [])}`)"
            )
        if tm:
            md.append(
                f"- **Tampering Sub-Engine**: `{tm.get('finding')}` "
                f"(tamper likelihood `{tm.get('tamper_probability')}`)"
            )
        if pr:
            md.append(
                f"- **Provenance & Attribution Sub-Engine**: `{pr.get('finding')}` "
                f"(attributed source: `{pr.get('source_attribution')}`, "
                f"C2PA status: `{(pr.get('c2pa') or {}).get('status', 'none')}`)"
            )

        art_files = it.get("artifact_files") or {}
        if art_files:
            md.append(f"- **Visual Evidence Artifacts**: `{', '.join(sorted(art_files.values()))}`")
            for label, fname in sorted(art_files.items()):
                p_art = locker.artifacts_dir / eid / fname
                if p_art.exists():
                    image_blocks.append((f"{eid} ({it['original_name']}) - {label}", p_art))
        md.append("")

    md.extend(
        [
            "## 6. Chronological Case & Metadata Timeline",
            "",
            "| Timestamp (UTC) | Category | Evidence ID | Actor / Source | Event Description |",
            "|---|---|---|---|---|",
        ]
    )
    for ev in timeline:
        md.append(
            f"| {ev.get('time_utc', '')} | {ev.get('kind', '')} | {ev.get('evidence_id', '')} | "
            f"{ev.get('actor', '')} | {ev.get('description', '')} |"
        )
    md.append("")

    md.extend(
        [
            "## 7. Known Limitations of This Analysis",
            "",
        ]
    )
    for lim in limitations:
        md.append(f"- {lim}")
    md.append("")

    md.extend(
        [
            "## 8. Draft Section 63 (Bharatiya Sakshya Adhiniyam, 2023) Certificate",
            "",
            cert_md,
            "",
            "## 9. Examiner Sign-Off & Peer Review Block",
            "",
            "I hereby record that I have independently reviewed the sealed multimedia exhibits, "
            "working-copy analysis logs, visual heatmaps/spectrograms, and limitations stated in "
            "this report.",
            "",
            f"- **Lead Forensic Examiner**: {exam['name']} ({exam['designation']})",
            "- **Examiner Signature**: ___________________________    **Date**: _______________",
            "- **Peer Reviewer Name & Designation**: _________________________________________",
            "- **Reviewer Signature**: ___________________________    **Date**: _______________",
            "",
        ]
    )

    report_dir = locker.case_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    md_path = report_dir / "forensic_report.md"
    json_path = report_dir / "forensic_report.json"
    html_path = report_dir / "forensic_report.html"
    pdf_path = report_dir / "forensic_report.pdf"

    md_content = "\n".join(md)
    md_path.write_text(md_content, encoding="utf-8")

    report_json_data = {
        "case_id": locker.case_id,
        "case_meta": meta,
        "generated_at_utc": report_ts,
        "integrity": integ,
        "items": items,
        "timeline": timeline,
        "custody_log": custody_log,
        "limitations_of_analysis": limitations,
        "section63_certificate": cert,
    }
    json_path.write_text(
        json.dumps(report_json_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Build self-contained offline HTML report with inline base64 images
    img_html_cards: list[str] = []
    for caption, img_p in image_blocks:
        b64 = base64.b64encode(img_p.read_bytes()).decode("ascii")
        img_html_cards.append(
            f'<div style="border:1px solid #cbd5e1;border-radius:6px;padding:10px;margin:8px 0;">'
            f'<div style="font-weight:600;margin-bottom:6px;">{html.escape(caption)}</div>'
            f'<img src="data:image/png;base64,{b64}" style="max-width:100%;height:auto;"/>'
            f"</div>"
        )
    html_doc = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'/>"
        f"<title>Forensic Report - {html.escape(locker.case_id)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:24px auto;"
        "padding:0 16px;color:#0f172a;line-height:1.5;}pre{white-space:pre-wrap;"
        "background:#f8fafc;padding:14px;border:1px solid #e2e8f0;border-radius:6px;}</style>"
        "</head><body>"
        f"<h1>Multimedia Forensic Examination Report — {html.escape(locker.case_id)}</h1>"
        f"<pre>{html.escape(md_content)}</pre>"
        "<h2>Embedded Visual Evidence (Heatmaps & Spectrograms)</h2>"
        + "".join(img_html_cards)
        + "</body></html>"
    )
    html_path.write_text(html_doc, encoding="utf-8")

    # Build multi-page PDF with vector text + embedded JPEG heatmaps
    _build_forensic_pdf(md_content, image_blocks, pdf_path)

    return {
        "case_id": locker.case_id,
        "generated_at_utc": report_ts,
        "md_path": str(md_path),
        "json_path": str(json_path),
        "html_path": str(html_path),
        "pdf_path": str(pdf_path),
        "certificate": cert,
    }
