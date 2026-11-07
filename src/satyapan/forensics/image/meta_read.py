"""Readers for embedded image metadata: EXIF (with the IFD1 thumbnail and GPS), XMP and IPTC.

XMP is read with regular expressions, never an XML parser: the packet is attacker-controlled
and only a handful of well-known properties are needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from satyapan.forensics.image.containers import JpegInfo, PngInfo


@dataclass
class ImageMeta:
    exif: dict[str, Any] = field(default_factory=dict)
    gps: dict[str, Any] = field(default_factory=dict)
    gps_decimal: dict[str, float] | None = None
    thumbnail: bytes | None = None
    xmp: dict[str, str] = field(default_factory=dict)
    xmp_history: list[dict[str, str]] = field(default_factory=list)
    iptc: dict[str, str] = field(default_factory=dict)
    iptc_raw: bytes = b""
    png_text: dict[str, str] = field(default_factory=dict)
    comments: list[str] = field(default_factory=list)


def _clean(v: Any) -> Any:
    if isinstance(v, bytes):
        txt = v.decode("utf-8", "replace").strip("\x00 ")
        if txt.startswith(("ASCII\x00\x00\x00", "UNICODE\x00", "UNICODE")):
            txt = txt.split("\x00", 1)[-1].strip("\x00 ")
        return txt[:500]
    if isinstance(v, tuple):
        return [_clean(x) for x in v][:16]
    try:
        from PIL.TiffImagePlugin import IFDRational

        if isinstance(v, IFDRational):
            return float(v) if v.denominator else None
    except ImportError:  # pragma: no cover
        pass
    if isinstance(v, str):
        return v.strip("\x00 ")[:500]
    return v


def read_exif(pil_raw: Any) -> tuple[dict[str, Any], dict[str, Any], bytes | None]:
    """(EXIF tags by name, GPS tags by name, IFD1 thumbnail JPEG bytes or None)."""
    from PIL import ExifTags

    try:
        exif = pil_raw.getexif()
    except Exception:  # noqa: BLE001
        return {}, {}, None
    if not exif:
        return {}, {}, None
    out: dict[str, Any] = {}
    for tag, val in exif.items():
        out[ExifTags.TAGS.get(tag, f"0x{tag:04X}")] = _clean(val)
    for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.Interop):
        try:
            sub = exif.get_ifd(ifd_id)
        except Exception:  # noqa: BLE001
            sub = {}
        for tag, val in sub.items():
            if tag == 0x927C:  # MakerNote: proprietary binary, note only its presence
                out["MakerNote"] = f"<{len(val) if hasattr(val, '__len__') else '?'} bytes>"
                continue
            out[ExifTags.TAGS.get(tag, f"0x{tag:04X}")] = _clean(val)
    gps: dict[str, Any] = {}
    try:
        for tag, val in exif.get_ifd(ExifTags.IFD.GPSInfo).items():
            gps[ExifTags.GPSTAGS.get(tag, f"0x{tag:04X}")] = _clean(val)
    except Exception:  # noqa: BLE001
        gps = {}
    thumb = None
    try:
        ifd1 = exif.get_ifd(ExifTags.IFD.IFD1)
        raw = pil_raw.info.get("exif")
        off, ln = ifd1.get(0x0201), ifd1.get(0x0202)
        if raw and off and ln:
            tiff = raw[6:] if raw.startswith(b"Exif\x00\x00") else raw
            blob = tiff[int(off) : int(off) + int(ln)]
            if blob.startswith(b"\xff\xd8"):
                thumb = bytes(blob)
    except Exception:  # noqa: BLE001
        thumb = None
    return out, gps, thumb


def gps_to_decimal(gps: dict[str, Any]) -> dict[str, float] | None:
    def conv(vals: Any, ref: Any) -> float | None:
        try:
            d, m, s = (float(x) for x in vals)
        except (TypeError, ValueError):
            return None
        dec = d + m / 60.0 + s / 3600.0
        if str(ref).upper().startswith(("S", "W")):
            dec = -dec
        return round(dec, 6)

    lat = conv(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef", "N"))
    lon = conv(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef", "E"))
    if lat is None or lon is None or (lat == 0 and lon == 0):
        return None
    return {"lat": lat, "lon": lon}


_XMP_PROPS = (
    "xmp:CreatorTool", "xmp:CreateDate", "xmp:ModifyDate", "xmp:MetadataDate",
    "photoshop:DateCreated", "xmpMM:DocumentID", "xmpMM:OriginalDocumentID",
    "xmpMM:InstanceID", "Iptc4xmpExt:DigitalSourceType", "tiff:Make", "tiff:Model",
    "exif:DateTimeOriginal", "aux:Lens", "aux:SerialNumber", "dc:creator", "dc:description",
    "dc:title", "crs:Version", "crs:ProcessVersion", "photoshop:Credit", "plus:DataMining",
    "GCamera:MicroVideo", "Iptc4xmpCore:Location", "exifEX:LensModel", "tiff:Software",
    "xmpRights:UsageTerms", "Iptc4xmpExt:AIPromptInformation", "Iptc4xmpExt:AISystemUsed",
    "Iptc4xmpExt:AISystemVersionUsed",
)  # fmt: skip


def parse_xmp(packet: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    props: dict[str, str] = {}
    for name in _XMP_PROPS:
        esc = re.escape(name)
        m = re.search(rf'{esc}\s*=\s*"([^"]{{0,800}})"', packet)
        if not m:
            m = re.search(rf"<{esc}(?:\s[^>]*)?>\s*([^<]{{1,800}})\s*</{esc}>", packet)
        if not m:  # rdf:Alt / rdf:Seq / rdf:Bag with rdf:li items
            m = re.search(
                rf"<{esc}(?:\s[^>]*)?>.*?<rdf:li[^>]*>([^<]{{1,800}})</rdf:li>", packet, re.S
            )
        if not m:  # rdf:resource form (DigitalSourceType is usually a URI)
            m = re.search(rf'<{esc}\s+rdf:resource="([^"]{{1,800}})"', packet)
        if m:
            props[name] = m.group(1).strip()
    history: list[dict[str, str]] = []
    for li in re.finditer(r"<rdf:li[^>]*stEvt:action[^>]*?/?>", packet, re.S):
        chunk = li.group(0)
        ev = {k: v for k, v in re.findall(r'stEvt:(\w+)="([^"]*)"', chunk)}
        if ev:
            history.append(ev)
    if not history:  # element form: <stEvt:action>saved</stEvt:action>
        for li in re.finditer(r"<rdf:li[^>]*>(.*?)</rdf:li>", packet, re.S):
            ev = {
                k: v.strip() for k, v in re.findall(r"<stEvt:(\w+)>([^<]*)</stEvt:\1>", li.group(1))
            }
            if "action" in ev:
                history.append(ev)
    return props, history[:50]


def find_xmp(data: bytes) -> str | None:
    """The first XMP packet anywhere in the file (JPEG APP1, PNG iTXt, WebP, MP4 ...)."""
    start = data.find(b"<x:xmpmeta")
    if start < 0:
        start = data.find(b"<rdf:RDF")
    if start < 0:
        return None
    end = data.find(b"</x:xmpmeta>", start)
    if end < 0:
        end = data.find(b"</rdf:RDF>", start)
    if end < 0:
        end = min(len(data), start + 200_000)
    return data[start : end + 12].decode("utf-8", "replace")


_IPTC_NAMES = {
    5: "ObjectName", 25: "Keywords", 40: "SpecialInstructions", 55: "DateCreated",
    60: "TimeCreated", 80: "Byline", 90: "City", 101: "Country", 103: "TransmissionReference",
    105: "Headline", 110: "Credit", 115: "Source", 116: "Copyright", 120: "Caption",
}  # fmt: skip


def parse_iptc(data: bytes) -> tuple[dict[str, str], bytes]:
    """IPTC-IIM record 2 datasets from a Photoshop IRB (JPEG APP13)."""
    pos = data.find(b"Photoshop 3.0\x00")
    if pos < 0:
        return {}, b""
    blob = data[pos : pos + 65536]
    out: dict[str, str] = {}
    i = 0
    while True:
        i = blob.find(b"\x1c\x02", i)
        if i < 0 or i + 5 > len(blob):
            break
        ds = blob[i + 2]
        ln = int.from_bytes(blob[i + 3 : i + 5], "big")
        if ln > 8000:
            i += 2
            continue
        val = blob[i + 5 : i + 5 + ln].decode("utf-8", "replace").strip("\x00 ")
        name = _IPTC_NAMES.get(ds, f"2:{ds}")
        out[name] = (out[name] + "; " + val) if name in out else val
        i += 5 + ln
    return out, blob


def read_all(data: bytes, pil_raw: Any, jpeg: JpegInfo | None, png: PngInfo | None) -> ImageMeta:
    meta = ImageMeta()
    meta.exif, meta.gps, meta.thumbnail = read_exif(pil_raw)
    meta.gps_decimal = gps_to_decimal(meta.gps) if meta.gps else None
    packet = (jpeg.xmp if jpeg and jpeg.xmp else None) or find_xmp(data)
    if packet:
        meta.xmp, meta.xmp_history = parse_xmp(packet)
    if jpeg and jpeg.photoshop_irb:
        meta.iptc, meta.iptc_raw = parse_iptc(data)
    if png:
        meta.png_text = dict(png.text)
    if jpeg:
        meta.comments = list(jpeg.comments)
    return meta
