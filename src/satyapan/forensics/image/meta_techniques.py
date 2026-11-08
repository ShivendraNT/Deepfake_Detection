"""Image techniques that read the file rather than the pixels: structure, metadata,
provenance signatures (AI generators, editors, platforms) and the EXIF thumbnail check."""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

import numpy as np

from satyapan.forensics.base import Technique, finding, info, make_result
from satyapan.forensics.context import AnalysisContext, colormap
from satyapan.forensics.image.containers import (
    JpegInfo,
    PngInfo,
    describe_trailing,
    estimate_quality,
    parse_jpeg,
    parse_png,
)
from satyapan.forensics.image.meta_read import ImageMeta, read_all
from satyapan.forensics.models import (
    Category,
    Finding,
    Hypothesis,
    MediaKind,
    Status,
    Strength,
    TechniqueResult,
)

IMG = (MediaKind.IMAGE,)


def jpeg_info(ctx: AnalysisContext) -> JpegInfo | None:
    if ctx.sniffed.format != "jpeg":
        return None
    if "jpeg_info" not in ctx.cache:
        ctx.cache["jpeg_info"] = parse_jpeg(ctx.data)
    return ctx.cache["jpeg_info"]  # type: ignore[no-any-return]


def png_info(ctx: AnalysisContext) -> PngInfo | None:
    if ctx.sniffed.format != "png":
        return None
    if "png_info" not in ctx.cache:
        ctx.cache["png_info"] = parse_png(ctx.data)
    return ctx.cache["png_info"]  # type: ignore[no-any-return]


def image_meta(ctx: AnalysisContext) -> ImageMeta:
    if "image_meta" not in ctx.cache:
        ctx.cache["image_meta"] = read_all(ctx.data, ctx.pil_raw(), jpeg_info(ctx), png_info(ctx))
    return ctx.cache["image_meta"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------------------------
# 1. File structure
# ---------------------------------------------------------------------------------------------


def run_structure(ctx: AnalysisContext) -> TechniqueResult:
    t = STRUCTURE
    findings: list[Finding] = []
    data: dict[str, Any] = {"format": ctx.sniffed.format, "mime": ctx.sniffed.mime}
    if ctx.media.extension_mismatch:
        findings.append(
            finding(
                "FILE_EXTENSION_MISMATCH",
                f"File is {ctx.sniffed.format.upper()} but named .{ctx.media.extension}",
                "The bytes identify a different format from the file name. Renaming is common "
                "when files are forwarded, but it can also be used to hide a file's origin.",
                Hypothesis.NEUTRAL,
                Strength.NONE,
                Category.INTEGRITY,
                detected=ctx.sniffed.format,
                extension=ctx.media.extension,
            )  # fmt: skip
        )
    jp, pn = jpeg_info(ctx), png_info(ctx)
    if jp is not None:
        q, exact, err = estimate_quality(jp)
        data.update(
            {
                "frame": jp.frame,
                "subsampling": jp.subsampling,
                "app_segments": jp.app_ids,
                "quantization_tables": len(jp.qtables),
                "estimated_quality": q,
                "standard_tables": exact,
                "table_error": round(err, 2),
                "huffman": (
                    "standard (Annex K)" if jp.huffman_standard
                    else "optimised / custom" if jp.huffman_standard is False else "n/a"
                ),
                "progressive": jp.frame == "progressive",
                "comments": jp.comments,
                "trailing_bytes": jp.trailing_bytes,
                "qtable0": jp.qtables.get(0),
                "qtable1": jp.qtables.get(1),
                "errors": jp.errors,
            }
        )  # fmt: skip
        if q is not None:
            table_kind = (
                f"standard IJG tables at quality {q}" if exact
                else f"non-standard tables (closest IJG quality ≈ {q})"
            )  # fmt: skip
            findings.append(
                info(
                    "JPEG_QUANTIZATION",
                    f"JPEG compressed with {table_kind}",
                    "Quantisation tables record how the last encoder compressed the image. "
                    "Standard IJG tables are written by libjpeg-based software (editors, "
                    "messaging apps, web services); many cameras use their own tables.",
                    Category.PROVENANCE,
                    quality=q,
                    standard=exact,
                )  # fmt: skip
            )
        for c in jp.comments:
            if c:
                findings.append(
                    info("JPEG_COMMENT", "Encoder comment in file",
                         f"JPEG COM segment: “{c[:160]}”.", Category.METADATA, comment=c[:500])
                )  # fmt: skip
        if jp.trailing_bytes > 32 and not jp.has_mpf:
            kind = describe_trailing(jp.trailing_head)
            strong = kind not in ("zero padding", "unrecognised data")
            findings.append(
                finding(
                    "TRAILING_DATA",
                    f"{jp.trailing_bytes:,} bytes after the end of the image ({kind})",
                    "Data after the JPEG end-of-image marker is ignored by viewers. Cameras "
                    "declare extra images in an MPF segment; this file does not, so the extra "
                    "bytes were appended by other software. Appended archives or executables "
                    "are a known way to hide data inside an innocent-looking picture.",
                    Hypothesis.MANIPULATED,
                    Strength.MODERATE if strong else Strength.WEAK,
                    Category.INTEGRITY,
                    bytes=jp.trailing_bytes,
                    kind=kind,
                )  # fmt: skip
            )
        if jp.errors:
            findings.append(
                finding(
                    "JPEG_STRUCTURE_ERROR",
                    "JPEG structure is damaged",
                    "The parser found: " + "; ".join(jp.errors[:3]) + ". Damage can come from "
                    "an interrupted transfer or from hand-editing the bytes.",
                    Hypothesis.NEUTRAL,
                    Strength.NONE,
                    Category.INTEGRITY,
                    errors=jp.errors,
                )  # fmt: skip
            )
    elif pn is not None:
        data.update(
            {
                "chunks": pn.chunks[:60],
                "bit_depth": pn.bit_depth,
                "color_type": pn.color_type,
                "text_keys": list(pn.text)[:30],
                "trailing_bytes": pn.trailing_bytes,
                "errors": pn.errors,
            }
        )
        if pn.trailing_bytes > 32:
            kind = describe_trailing(pn.trailing_head)
            findings.append(
                finding(
                    "TRAILING_DATA",
                    f"{pn.trailing_bytes:,} bytes after the PNG end chunk ({kind})",
                    "Data after IEND is ignored by viewers and is not written by normal "
                    "software; it was appended afterwards.",
                    Hypothesis.MANIPULATED,
                    Strength.MODERATE
                    if kind not in ("zero padding", "unrecognised data")
                    else Strength.WEAK,
                    Category.INTEGRITY,
                    bytes=pn.trailing_bytes,
                    kind=kind,
                )  # fmt: skip
            )
    img = ctx.pil()
    data.update({"width": img.size[0], "height": img.size[1], "mode": ctx.pil_raw().mode})
    summary = f"{ctx.sniffed.format.upper()} {img.size[0]}×{img.size[1]}"
    if jp is not None and data.get("estimated_quality"):
        summary += f", quality ≈ {data['estimated_quality']}, {jp.subsampling or '?'}"
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# 2. Metadata (EXIF / XMP / IPTC)
# ---------------------------------------------------------------------------------------------

EDITORS = [
    (r"photoshop", "Adobe Photoshop"),
    (r"lightroom|camera raw", "Adobe Lightroom / Camera Raw"),
    (r"\bgimp\b", "GIMP"),
    (r"snapseed", "Snapseed"),
    (r"picsart", "PicsArt"),
    (r"\bcanva\b", "Canva"),
    (r"pixlr", "Pixlr"),
    (r"affinity", "Affinity Photo"),
    (r"paint\.net", "Paint.NET"),
    (r"\bfotor\b", "Fotor"),
    (r"faceapp", "FaceApp"),
    (r"facetune", "Facetune"),
    (r"remini", "Remini"),
    (r"meitu|beautyplus", "Meitu / BeautyPlus"),
    (r"photodirector", "PhotoDirector"),
    (r"polarr", "Polarr"),
    (r"imagemagick|graphicsmagick", "ImageMagick / GraphicsMagick (scripted processing)"),
    (r"inshot", "InShot"),
    (r"pixelmator", "Pixelmator"),
    (r"photopea", "Photopea"),
]

_DT_RE = re.compile(r"(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    m = _DT_RE.search(str(v))
    if not m:
        return None
    try:
        return datetime(*(int(x) for x in m.groups()))  # noqa: DTZ001 - EXIF has no zone
    except ValueError:
        return None


def editor_in(text: str) -> str | None:
    low = text.lower()
    for pat, name in EDITORS:
        if re.search(pat, low):
            return name
    return None


def run_metadata(ctx: AnalysisContext) -> TechniqueResult:
    t = METADATA
    meta = image_meta(ctx)
    ex = meta.exif
    findings: list[Finding] = []
    make, model = str(ex.get("Make", "") or "").strip(), str(ex.get("Model", "") or "").strip()
    software = str(ex.get("Software", "") or meta.xmp.get("xmp:CreatorTool", "") or "").strip()
    camera_tags = [k for k in ("Make", "Model", "ExposureTime", "FNumber", "ISOSpeedRatings",
                               "FocalLength", "LensModel", "DateTimeOriginal") if k in ex]  # fmt: skip
    if make or model:
        device = f"{make} {model}".strip()
        if model.lower().startswith(make.lower()) and make:
            device = model
        findings.append(
            info(
                "CAMERA_IDENTIFIED",
                f"Camera metadata: {device}",
                f"EXIF names the capturing device as “{device}”"
                + (f" (lens {ex['LensModel']})" if ex.get("LensModel") else "")
                + ". EXIF can be edited, so this is a claim to test, not proof of origin.",
                Category.PROVENANCE,
                make=make,
                model=model,
                serial=ex.get("BodySerialNumber") or ex.get("SerialNumber"),
            )  # fmt: skip
        )
    elif not ex and not meta.xmp:
        findings.append(
            info(
                "NO_METADATA",
                "No EXIF or XMP metadata",
                "The file carries no camera or software metadata. Messaging apps, social "
                "networks, screenshots and many editors strip it, so its absence is not by "
                "itself evidence of manipulation, but the file is not a camera original.",
                Category.METADATA,
            )  # fmt: skip
        )
    ed = editor_in(software) if software else None
    hist_agents = [h.get("softwareAgent", "") for h in meta.xmp_history if h.get("softwareAgent")]
    hist_editor = next((editor_in(a) for a in hist_agents if editor_in(a)), None)
    if "crs:Version" in meta.xmp or "crs:ProcessVersion" in meta.xmp:
        hist_editor = hist_editor or "Adobe Lightroom / Camera Raw"
    if ed or hist_editor:
        name = ed or hist_editor
        findings.append(
            finding(
                "EDITING_SOFTWARE",
                f"Processed with editing software: {name}",
                f"The metadata records {name} ("
                + (f"Software/CreatorTool “{software[:80]}”" if ed else "XMP edit history")
                + "). Saving through an editor does not prove the content was altered, but the "
                "file is not a camera original and edits are possible.",
                Hypothesis.MANIPULATED,
                Strength.WEAK,
                Category.METADATA,
                software=software[:200],
                editor=name,
            )  # fmt: skip
        )
    if meta.xmp_history:
        actions = [h.get("action", "?") for h in meta.xmp_history]
        findings.append(
            info(
                "XMP_HISTORY",
                f"XMP edit history: {len(actions)} recorded step(s)",
                "XMP history: "
                + "; ".join(
                    f"{h.get('action', '?')} by {h.get('softwareAgent', '?')} at "
                    f"{h.get('when', '?')}"
                    for h in meta.xmp_history[:6]
                ),
                Category.PROVENANCE,
                history=meta.xmp_history[:20],
            )  # fmt: skip
        )
    dto = _parse_dt(ex.get("DateTimeOriginal") or meta.xmp.get("exif:DateTimeOriginal"))
    dmod = _parse_dt(ex.get("DateTime") or meta.xmp.get("xmp:ModifyDate"))
    if dto and dmod and (dmod - dto).total_seconds() > 2:
        delta = dmod - dto
        findings.append(
            finding(
                "MODIFIED_AFTER_CAPTURE",
                "Saved again after capture",
                f"Capture time {dto:%Y-%m-%d %H:%M:%S}, last modification "
                f"{dmod:%Y-%m-%d %H:%M:%S} ({_human_delta(delta.total_seconds())} later). "
                "The image was re-saved after it was taken; check what changed.",
                Hypothesis.MANIPULATED,
                Strength.WEAK,
                Category.METADATA,
                captured=str(dto),
                modified=str(dmod),
            )  # fmt: skip
        )
    if dto and (dto.year < 1995 or dto > datetime.now()):  # noqa: DTZ005
        findings.append(
            finding(
                "IMPLAUSIBLE_DATE",
                f"Implausible capture date {dto:%Y-%m-%d}",
                "The recorded capture date is before digital cameras were common or in "
                "the future, which indicates a wrong clock or edited metadata.",
                Hypothesis.MANIPULATED,
                Strength.WEAK,
                Category.METADATA,
                captured=str(dto),
            )  # fmt: skip
        )
    pxw, pxh = ex.get("ExifImageWidth"), ex.get("ExifImageHeight")
    w, h = ctx.pil_raw().size
    if isinstance(pxw, int) and isinstance(pxh, int) and pxw > 0 and pxh > 0:
        same = {(pxw, pxh), (pxh, pxw)}
        if (w, h) not in same:
            ratio_ex, ratio_im = max(pxw, pxh) / min(pxw, pxh), max(w, h) / max(1, min(w, h))
            cropped = abs(ratio_ex - ratio_im) > 0.02
            findings.append(
                finding(
                    "EXIF_DIMENSION_MISMATCH",
                    "Pixel size differs from the size recorded in EXIF",
                    f"EXIF says {pxw}×{pxh} but the image is {w}×{h}"
                    + (
                        " with a different aspect ratio: it was cropped"
                        if cropped
                        else ": it was resized"
                    )
                    + " after the metadata was written.",
                    Hypothesis.MANIPULATED,
                    Strength.MODERATE if cropped else Strength.WEAK,
                    Category.METADATA,
                    exif_size=[pxw, pxh],
                    actual=[w, h],
                )  # fmt: skip
            )
    if meta.gps_decimal:
        g = meta.gps_decimal
        findings.append(
            info(
                "GPS_LOCATION",
                f"GPS position recorded: {g['lat']:.5f}, {g['lon']:.5f}",
                "The file records where it was taken. Verify against the case timeline; "
                "GPS tags can also be edited.",
                Category.PROVENANCE,
                **g,
            )  # fmt: skip
        )
    if str(ex.get("UserComment", "")).strip().lower() == "screenshot":
        findings.append(
            info(
                "SCREENSHOT_TAG",
                "Marked as a screenshot by the device",
                "iOS writes “Screenshot” in EXIF UserComment for screen captures.",
                Category.PROVENANCE,
            )  # fmt: skip
        )
    table = {k: v for k, v in ex.items() if not isinstance(v, bytes | bytearray)}
    data = {
        "exif": {k: (v if isinstance(v, str | int | float | list) or v is None else str(v))
                 for k, v in list(table.items())[:120]},
        "gps": meta.gps_decimal,
        "xmp": meta.xmp,
        "xmp_history": meta.xmp_history,
        "iptc": meta.iptc,
        "png_text_keys": list(meta.png_text)[:30],
        "camera_tags": camera_tags,
    }  # fmt: skip
    n = len(ex) + len(meta.xmp) + len(meta.iptc)
    summary = f"{len(ex)} EXIF, {len(meta.xmp)} XMP, {len(meta.iptc)} IPTC fields"
    if make or model:
        summary += f"; device {make} {model}".rstrip()
    if n == 0:
        summary = "no embedded metadata"
    return make_result(t, summary=summary, findings=findings, data=data)


def _human_delta(seconds: float) -> str:
    if seconds < 120:
        return f"{seconds:.0f} s"
    if seconds < 7200:
        return f"{seconds / 60:.0f} min"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86400:.0f} days"


# ---------------------------------------------------------------------------------------------
# 3. Provenance signatures: AI generators, platforms
# ---------------------------------------------------------------------------------------------

GENERATOR_PATTERNS = [
    (r"\bnovelai\b", "NovelAI"),
    (r"\binvokeai\b", "InvokeAI"),
    (r"\bfooocus\b", "Fooocus"),
    (r"\bmidjourney\b", "Midjourney"),
    (r"\bdall[·\-\s]?e(\s?[23])?\b", "OpenAI DALL·E"),
    (r"\bgpt-?4o\b|\bopenai\b", "OpenAI image generation"),
    (r"\badobe firefly\b|\bfirefly\b", "Adobe Firefly"),
    (r"\bmade with google ai\b|\bimagen\s?\d\b|\bgemini\b", "Google Imagen / Gemini"),
    (r"\bimagined with ai\b|\bmeta ai\b", "Meta AI"),
    (r"\bbing image creator\b|\bmicrosoft designer\b", "Microsoft Designer / Bing Image Creator"),
    (r"\bleonardo\.ai\b", "Leonardo.Ai"),
    (r"\bblack-forest-labs\b|\bflux\.1\b", "FLUX (Black Forest Labs)"),
    (r"\bideogram\b", "Ideogram"),
    (r"\brunway(ml)?\b", "Runway"),
    (r"\bstable diffusion\b|\bstability\.ai\b|\bsdxl\b", "Stable Diffusion"),
    (r"\bdiffusers\b", "Hugging Face diffusers"),
    (r"\bcomfyui\b", "ComfyUI"),
]

DIGITAL_SOURCE_TYPES = {
    "trainedalgorithmicmedia": ("AI-generated (declared)", Strength.STRONG),
    "compositewithtrainedalgorithmicmedia": ("Composite with AI-generated elements (declared)",
                                             Strength.STRONG),
    "algorithmicallyenhanced": ("Algorithmically enhanced (declared)", Strength.WEAK),
    "compositesynthetic": ("Synthetic composite (declared)", Strength.STRONG),
    "algorithmicmedia": ("Algorithmic / synthetic media (declared)", Strength.STRONG),
    "digitalcapture": ("Digital capture (declared)", Strength.NONE),
    "screencapture": ("Screen capture (declared)", Strength.NONE),
}  # fmt: skip

PLATFORM_FILENAMES = [
    (r"^(IMG|VID|AUD|PTT|STK|DOC)-\d{8}-WA\d{3,5}", "WhatsApp (mobile)"),
    (r"^WhatsApp (Image|Video|Audio|Ptt) \d{4}-\d{2}-\d{2} at", "WhatsApp (desktop / web)"),
    (r"^(photo|video|file)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", "Telegram"),
    (r"^signal-\d{4}-\d{2}-\d{2}", "Signal"),
    (r"(?i)screenshot|screen shot|screen_recording|scr_\d{8}", "Screenshot / screen recording"),
    (r"^PXL_\d{8}_\d{6}", "Google Pixel camera"),
    (r"^IMG_\d{8}_\d{6}", "Android camera"),
    (r"^IMG_\d{4}\.(JPG|HEIC|PNG|MOV)$", "iPhone / Canon camera naming"),
    (r"^(DSC|DSCN|DSCF|_DSC)\d{4,5}", "Digital camera (Nikon / Sony / Fujifilm naming)"),
    (r"^\d{8}_\d{6}(\(\d+\))?\.", "Samsung camera naming"),
    (r"^(GOPR|GH\d{2}|GX\d{2})\d{4}", "GoPro"),
    (r"^(FB_IMG|received_)\d+", "Facebook / Messenger download"),
    (r"^(snapchat|snap)-\d+", "Snapchat"),
]


def generator_hits(ctx: AnalysisContext, meta: ImageMeta) -> list[tuple[str, str, Strength]]:
    """(generator, evidence, strength) from what the file says about the tool that wrote it.

    Structured blocks that generator front-ends write (prompt + sampler + seed, ComfyUI node
    graphs) are strong support. A generator name in a *tool* field (EXIF Software, XMP
    CreatorTool, the XMP history's softwareAgent, PNG Software/Source) is moderate support.
    Mentions anywhere else (descriptions, captions, artist, file names) are only context: the
    caller reports them without weight, because any word can be typed there."""
    hits: list[tuple[str, str, Strength]] = []
    png = meta.png_text
    if "parameters" in png and re.search(r"steps:\s*\d+", png["parameters"], re.I) and re.search(
            r"sampler:|seed:", png["parameters"], re.I):  # fmt: skip
        hits.append(("Stable Diffusion (AUTOMATIC1111 / Forge web UI)",
                     "PNG text chunk 'parameters' holds prompt, sampler, seed and model hash",
                     Strength.STRONG))  # fmt: skip
    if ("prompt" in png and "class_type" in png.get("prompt", "")) or (
            "workflow" in png and "nodes" in png.get("workflow", "")):  # fmt: skip
        hits.append(("ComfyUI (Stable Diffusion / FLUX workflow)",
                     "PNG text chunks 'prompt'/'workflow' hold a ComfyUI node graph",
                     Strength.STRONG))  # fmt: skip
    if "invokeai_metadata" in png or "sd-metadata" in png:
        hits.append(("InvokeAI", "PNG text chunk written by InvokeAI", Strength.STRONG))
    tool_fields = [
        str(meta.exif.get("Software", "")), meta.xmp.get("xmp:CreatorTool", ""),
        meta.xmp.get("tiff:Software", ""), png.get("Software", ""), png.get("Source", ""),
        *(h.get("softwareAgent", "") for h in meta.xmp_history),
    ]  # fmt: skip
    blob = " | ".join(t for t in tool_fields if t)[:20_000]
    seen = {h[0].split(" (")[0] for h in hits}
    for pat, name in GENERATOR_PATTERNS:
        m = re.search(pat, blob, re.I)
        if m and name.split(" (")[0] not in seen:
            snippet = blob[max(0, m.start() - 30) : m.end() + 30].replace("\n", " ")
            hits.append((name, f"the tool field that names the writing software says “…{snippet}…”",
                         Strength.MODERATE))  # fmt: skip
            seen.add(name.split(" (")[0])
    return hits


def generator_mentions(ctx: AnalysisContext, meta: ImageMeta) -> list[tuple[str, str]]:
    """Generator names in free text (descriptions, captions, file name): context only."""
    texts = [
        str(meta.exif.get(k, ""))
        for k in ("ImageDescription", "UserComment", "Artist", "XPComment")
    ]
    texts += [meta.xmp.get(k, "") for k in ("dc:description", "dc:title")] + list(
        meta.iptc.values()
    )
    texts += [v for k, v in meta.png_text.items()
              if k.lower() in ("description", "comment", "title", "author", "caption")]  # fmt: skip
    texts += [re.sub(r"[_\-.]+", " ", ctx.filename or "")]  # "midjourney_v6.png" → words
    blob = " | ".join(str(t) for t in texts if t)[:20_000]
    out = []
    for pat, name in GENERATOR_PATTERNS:
        m = re.search(pat, blob, re.I)
        if m:
            out.append((name, blob[max(0, m.start() - 30) : m.end() + 30].replace("\n", " ")))
    return out[:3]


def run_provenance(ctx: AnalysisContext) -> TechniqueResult:
    t = PROVENANCE
    meta = image_meta(ctx)
    findings: list[Finding] = []
    data: dict[str, Any] = {}
    for gen, evidence, strength in generator_hits(ctx, meta):
        findings.append(
            finding(
                "GENERATOR_SIGNATURE",
                f"AI generator signature: {gen}",
                f"{evidence}. Generator front-ends write these fields automatically; a camera "
                "or phone never does. They can be removed, so their absence proves nothing.",
                Hypothesis.SYNTHETIC,
                strength,
                Category.PROVENANCE,
                generator=gen,
                evidence=evidence[:300],
            )  # fmt: skip
        )
        data.setdefault("generators", []).append(gen)
    for gen, snippet in generator_mentions(ctx, meta):
        if gen in data.get("generators", []):
            continue
        findings.append(
            info(
                "GENERATOR_MENTION",
                f"Free text mentions {gen}",
                f"A description, caption or the file name contains “…{snippet}…”. Anyone can "
                "type this, so it is noted as context only.",
                Category.PROVENANCE,
                generator=gen,
            )  # fmt: skip
        )
    dst = meta.xmp.get("Iptc4xmpExt:DigitalSourceType", "")
    if dst:
        key = dst.rstrip("/").rsplit("/", 1)[-1].lower()
        label, strength = DIGITAL_SOURCE_TYPES.get(
            key, (f"declared source type {key}", Strength.NONE)
        )
        hyp = Hypothesis.SYNTHETIC if strength > Strength.NONE else Hypothesis.NEUTRAL
        findings.append(
            finding(
                "DIGITAL_SOURCE_TYPE",
                f"IPTC Digital Source Type: {label}",
                f"The file declares IPTC DigitalSourceType “{dst}”. Major generators "
                "(Adobe, Google, Meta, OpenAI, Microsoft) write this field for AI images.",
                hyp,
                strength,
                Category.PROVENANCE,
                value=dst,
            )  # fmt: skip
        )
        data["digital_source_type"] = dst
    for key in ("Iptc4xmpExt:AISystemUsed", "Iptc4xmpExt:AIPromptInformation"):
        if meta.xmp.get(key):
            findings.append(
                finding(
                    "AI_SYSTEM_DECLARED",
                    f"Declares the AI system used: {meta.xmp[key][:60]}",
                    f"XMP {key} = “{meta.xmp[key][:200]}”. A declared field: strong support, "
                    "though metadata can be edited.",
                    Hypothesis.SYNTHETIC,
                    Strength.STRONG,
                    Category.PROVENANCE,
                    value=meta.xmp[key][:300],
                )  # fmt: skip
            )
    platforms: list[tuple[str, str, Strength]] = []
    base = (ctx.filename or "").rsplit("/", 1)[-1]
    for pat, name in PLATFORM_FILENAMES:
        if re.search(pat, base):
            platforms.append(
                (name, f"file name “{base}” follows its naming pattern", Strength.WEAK)
            )
            break
    iptc_blob = meta.iptc_raw or b""
    if b"FBMD" in iptc_blob or "FBMD" in " ".join(meta.iptc.values()):
        platforms.append(("Facebook / Instagram (Meta)",
                          "IPTC block carries Meta's 'FBMD' transmission marker", Strength.STRONG))  # fmt: skip
    jp = jpeg_info(ctx)
    if jp is not None and not meta.exif and not meta.xmp:
        q, exact, _ = estimate_quality(jp)
        w, h = ctx.pil_raw().size
        long_side = max(w, h)
        if exact and q is not None and long_side in (1280, 1600, 2048, 2560, 4096):
            platforms.append(
                (
                    "messaging-app recompression (WhatsApp-like)",
                    f"metadata stripped, standard tables q≈{q}, long side {long_side}px",
                    Strength.WEAK,
                )  # fmt: skip
            )
    for name, evidence, strength in platforms:
        findings.append(
            info(
                "PLATFORM_TRACE",
                f"Platform trace: {name}",
                f"{evidence[:1].upper()}{evidence[1:]}. This indicates the file passed "
                "through (or was named by) that platform; it does not show who made it.",
                Category.PROVENANCE,
                platform=name,
                evidence=evidence,
                weight=int(strength),
            )  # fmt: skip
        )
        data.setdefault("platforms", []).append(name)
    summary_parts = []
    if data.get("generators"):
        summary_parts.append("generator: " + ", ".join(data["generators"][:2]))
    if dst:
        summary_parts.append("declared " + dst.rsplit("/", 1)[-1])
    if data.get("platforms"):
        summary_parts.append("platform: " + data["platforms"][0])
    summary = "; ".join(summary_parts) or "no generator, platform or source declaration found"
    return make_result(t, summary=summary, findings=findings, data=data)


# ---------------------------------------------------------------------------------------------
# 4. EXIF thumbnail vs main image
# ---------------------------------------------------------------------------------------------


def _strip_bars(a: np.ndarray, thr: float = 12.0) -> np.ndarray:
    """Remove black letterbox / pillarbox bars that cameras add to 4:3 thumbnails."""
    g = a.mean(axis=2) if a.ndim == 3 else a
    rows = np.where(g.mean(axis=1) > thr)[0]
    cols = np.where(g.mean(axis=0) > thr)[0]
    if len(rows) < 8 or len(cols) < 8:
        return a
    return a[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]


def run_thumbnail(ctx: AnalysisContext) -> TechniqueResult:
    t = THUMBNAIL
    meta = image_meta(ctx)
    if not meta.thumbnail:
        return make_result(t, summary="no embedded EXIF thumbnail", status=Status.SKIPPED)
    from PIL import Image

    try:
        th = Image.open(io.BytesIO(meta.thumbnail)).convert("RGB")
    except Exception:  # noqa: BLE001
        return make_result(t, summary="embedded thumbnail does not decode",
                           status=Status.SKIPPED)  # fmt: skip
    tha = _strip_bars(np.asarray(th, dtype=np.float32))
    main = ctx.pil_raw().convert("RGB")  # stored orientation, like the thumbnail
    ma = np.asarray(main.resize((tha.shape[1], tha.shape[0]), Image.BILINEAR), dtype=np.float32)
    r_th = tha.shape[1] / max(1, tha.shape[0])
    r_main = main.size[0] / max(1, main.size[1])
    aspect_diff = abs(r_th - r_main) / max(r_th, r_main)
    g1, g2 = tha.mean(axis=2), ma.mean(axis=2)
    a, b = g1 - g1.mean(), g2 - g2.mean()
    ncc = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
    diff = np.abs(tha - ma).mean(axis=2)
    mad = float(diff.mean())
    heat = colormap(np.clip(diff / 60.0, 0, 1), "inferno")
    side = np.concatenate(
        [tha.astype(np.uint8), np.full((tha.shape[0], 4, 3), 255, np.uint8),
         ma.astype(np.uint8), np.full((tha.shape[0], 4, 3), 255, np.uint8), heat], axis=1
    )  # fmt: skip
    scale = max(1, 360 // max(1, side.shape[0]))
    big = np.kron(side, np.ones((scale, scale, 1), dtype=np.uint8)) if scale > 1 else side
    art = ctx.save_png("thumbnail_compare", big, "figure", "EXIF thumbnail vs main image",
                       "Left: thumbnail stored in EXIF. Middle: main image at the same size. "
                       "Right: difference (brighter = more different).")  # fmt: skip
    findings: list[Finding] = []
    data = {"ncc": round(ncc, 4), "mean_abs_diff": round(mad, 2),
            "aspect_thumbnail": round(r_th, 3), "aspect_main": round(r_main, 3)}  # fmt: skip
    if aspect_diff > 0.04:
        findings.append(
            finding(
                "THUMBNAIL_ASPECT_MISMATCH",
                "Thumbnail has a different shape from the image",
                f"The camera's thumbnail has aspect ratio {r_th:.2f} but the image "
                f"{r_main:.2f}: the picture was cropped after the thumbnail was written, "
                "and the old thumbnail was left in place.",
                Hypothesis.MANIPULATED,
                Strength.MODERATE,
                Category.TAMPERING,
                artifacts=[art.name],
                **data,
            )  # fmt: skip
        )
    elif ncc < 0.80 or mad > 28:
        findings.append(
            finding(
                "THUMBNAIL_CONTENT_MISMATCH",
                "Thumbnail shows different content",
                f"The embedded thumbnail and the main image disagree (correlation "
                f"{ncc:.2f}, mean difference {mad:.0f}/255). Editors that rewrite the "
                "pixels but copy the old EXIF block leave the original thumbnail behind; "
                "the thumbnail shows the picture before it was changed.",
                Hypothesis.MANIPULATED,
                Strength.STRONG if ncc < 0.6 else Strength.MODERATE,
                Category.TAMPERING,
                artifacts=[art.name],
                **data,
            )  # fmt: skip
        )
    else:
        findings.append(
            finding(
                "THUMBNAIL_CONSISTENT",
                "Thumbnail matches the image",
                f"The embedded thumbnail agrees with the main image (correlation {ncc:.2f}).",
                Hypothesis.AUTHENTIC,
                Strength.WEAK,
                Category.TAMPERING,
                artifacts=[art.name],
                **data,
            )  # fmt: skip
        )
    return make_result(t, summary=f"thumbnail correlation {ncc:.2f}", findings=findings,
                       data=data, artifacts=[art])  # fmt: skip


STRUCTURE = Technique(
    "image.structure", "File structure & compression", Category.INTEGRITY, IMG, run_structure,
    "The file is parsed byte by byte: format signature, JPEG segments (APP markers, comments, "
    "quantisation and Huffman tables, frame type, chroma subsampling) or PNG chunks, and any "
    "data after the end-of-image marker. JPEG quality is estimated by matching the "
    "quantisation tables against the IJG standard tables scaled for qualities 1-100.",
    "ITU-T T.81 (JPEG) Annex K; ISO/IEC 15948 (PNG)", order=1,
)  # fmt: skip
METADATA = Technique(
    "image.metadata", "Metadata (EXIF / XMP / IPTC)", Category.METADATA, IMG, run_metadata,
    "EXIF, XMP and IPTC fields are extracted and checked for internal consistency: capture vs "
    "modification time, recorded vs actual pixel size, editing software in Software, "
    "CreatorTool or the XMP edit history, and GPS position.",
    "JEITA CP-3451 (Exif 2.32); ISO 16684-1 (XMP); IPTC Photo Metadata Standard",
    "Metadata is easy to edit or strip; it can support a conclusion but never proves one alone.",
    order=2,
)  # fmt: skip
PROVENANCE = Technique(
    "image.provenance", "Generator & platform signatures", Category.PROVENANCE, IMG,
    run_provenance,
    "Text the file carries about itself is matched against known signatures: prompt/seed "
    "blocks written by Stable Diffusion front-ends (AUTOMATIC1111, ComfyUI, InvokeAI, "
    "NovelAI), IPTC DigitalSourceType declarations (trainedAlgorithmicMedia), AI-system "
    "fields, Meta's FBMD marker, and file-naming conventions of messaging apps and cameras.",
    "IPTC NewsCodes digitalsourcetype; generator documentation",
    "Signatures are removed by re-saving or screenshots: absence of a signature is not "
    "evidence of authenticity.", order=3,
)  # fmt: skip
THUMBNAIL = Technique(
    "image.thumbnail", "EXIF thumbnail consistency", Category.TAMPERING, IMG, run_thumbnail,
    "Cameras store a small preview of the photo in EXIF. Many editors rewrite the pixels but "
    "copy the EXIF block unchanged, so the preview keeps showing the original. The preview is "
    "compared with the main image (normalised cross-correlation, mean difference, aspect "
    "ratio) after removing letterbox bars.",
    "Kee & Farid, 'Digital image authentication from thumbnails' (SPIE 2010)",
    "Only applies when a thumbnail is present; editors that regenerate it defeat the test.",
    order=4,
)  # fmt: skip
