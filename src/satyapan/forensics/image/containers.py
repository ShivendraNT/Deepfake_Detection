"""Byte-level parsers for JPEG and PNG structure (no third-party code; every field is read
straight from the file so the report can quote offsets).

JPEG: segments (APPn identifiers, COM text), quantisation tables (natural order), frame type
and chroma subsampling, whether the Huffman tables are the standard Annex K ones, trailing
bytes after the final EOI. PNG: chunk list, text chunks (where Stable Diffusion front-ends
write their prompt and settings), trailing bytes after IEND.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

ZIGZAG = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27,
    20, 13, 6, 7, 14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58,
    59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
]  # fmt: skip

STD_LUMA = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69,
    56, 14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104,
    113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
]  # fmt: skip
STD_CHROMA = [
    17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99, 24, 26, 56, 99, 99, 99, 99,
    99, 47, 66, 99, 99, 99, 99, 99, 99,
] + [99] * 32  # fmt: skip

# Annex K Huffman code-length counts (BITS) for the four standard tables.
STD_BITS = {
    (0, 0): [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # DC luminance
    (0, 1): [0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # DC chrominance
    (1, 0): [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7D],  # AC luminance
    (1, 1): [0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 0x77],  # AC chrominance
}

SOF_NAMES = {
    0xC0: "baseline", 0xC1: "extended sequential", 0xC2: "progressive", 0xC3: "lossless",
    0xC5: "differential sequential", 0xC6: "differential progressive", 0xC9: "arithmetic",
    0xCA: "arithmetic progressive",
}  # fmt: skip


@dataclass
class JpegInfo:
    segments: list[dict[str, object]] = field(default_factory=list)
    app_ids: list[str] = field(default_factory=list)  # e.g. "APP0:JFIF", "APP1:Exif"
    comments: list[str] = field(default_factory=list)
    qtables: dict[int, list[int]] = field(default_factory=dict)  # natural order
    frame: str = ""
    width: int = 0
    height: int = 0
    subsampling: str = ""
    huffman_standard: bool | None = None
    restart_interval: int = 0
    scans: int = 0
    eoi_offset: int | None = None
    trailing_bytes: int = 0
    trailing_head: bytes = b""
    has_mpf: bool = False
    xmp: str | None = None
    xmp_extended: bool = False
    photoshop_irb: bool = False
    adobe_app14: bool = False
    jumbf: bool = False
    errors: list[str] = field(default_factory=list)


def parse_jpeg(data: bytes) -> JpegInfo:
    info = JpegInfo()
    if not data.startswith(b"\xff\xd8"):
        info.errors.append("no SOI marker")
        return info
    i, n = 2, len(data)
    bits_seen: list[tuple[int, int, list[int]]] = []
    while i < n - 1:
        if data[i] != 0xFF:
            info.errors.append(f"expected marker at offset {i}")
            break
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker == 0xD9:  # EOI
            info.eoi_offset = i
            break
        if marker in (0x01,) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > n:
            info.errors.append("truncated segment header")
            break
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        payload = data[i + 4 : i + 2 + length]
        seg = {"marker": f"FF{marker:02X}", "offset": i, "length": length}
        if 0xE0 <= marker <= 0xEF:
            ident = payload[:32].split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
            app = f"APP{marker - 0xE0}:{ident[:24]}"
            info.app_ids.append(app)
            seg["id"] = app
            if marker == 0xE1 and payload.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
                info.xmp = payload[29:].decode("utf-8", "replace")
            elif marker == 0xE1 and payload.startswith(b"http://ns.adobe.com/xmp/extension/"):
                info.xmp_extended = True
            elif marker == 0xE2 and payload.startswith(b"MPF\x00"):
                info.has_mpf = True
            elif marker == 0xED and payload.startswith(b"Photoshop 3.0"):
                info.photoshop_irb = True
            elif marker == 0xEE and payload.startswith(b"Adobe"):
                info.adobe_app14 = True
            elif marker == 0xEB and (b"jumb" in payload[:64] or b"JP" in payload[:4]):
                info.jumbf = True
        elif marker == 0xFE:
            info.comments.append(payload.decode("utf-8", "replace").strip("\x00 ")[:500])
        elif marker == 0xDB:
            _parse_dqt(payload, info)
        elif marker in SOF_NAMES:
            _parse_sof(marker, payload, info)
        elif marker == 0xC4:
            j = 0
            while j + 17 <= len(payload):
                tc_th = payload[j]
                bits = list(payload[j + 1 : j + 17])
                total = sum(bits)
                bits_seen.append((tc_th >> 4, tc_th & 0x0F, bits))
                j += 17 + total
        elif marker == 0xDD and len(payload) >= 2:
            info.restart_interval = struct.unpack(">H", payload[:2])[0]
        info.segments.append(seg)
        i += 2 + length
        if marker == 0xDA:  # SOS: skip entropy-coded data up to the next real marker
            info.scans += 1
            while i < n - 1:
                if data[i] == 0xFF and data[i + 1] != 0x00 and not (0xD0 <= data[i + 1] <= 0xD7):
                    break
                i += 1
    if bits_seen:
        std = True
        for tc, th, bits in bits_seen:
            key = (tc, 0 if th == 0 else 1)
            if STD_BITS.get(key) != bits:
                std = False
        info.huffman_standard = std
    if info.eoi_offset is not None:
        tail = data[info.eoi_offset + 2 :]
        info.trailing_bytes = len(tail)
        info.trailing_head = tail[:16]
    else:
        info.errors.append("no EOI marker (file truncated or damaged)")
    return info


def _parse_dqt(payload: bytes, info: JpegInfo) -> None:
    j = 0
    while j < len(payload):
        pq_tq = payload[j]
        precision, tid = pq_tq >> 4, pq_tq & 0x0F
        j += 1
        size = 128 if precision else 64
        raw = payload[j : j + size]
        if len(raw) < size:
            info.errors.append("truncated DQT")
            return
        vals = list(struct.unpack(">64H", raw)) if precision else list(raw)
        natural = [0] * 64
        for k, v in enumerate(vals):
            natural[ZIGZAG[k]] = v
        info.qtables[tid] = natural
        j += size


def _parse_sof(marker: int, payload: bytes, info: JpegInfo) -> None:
    if len(payload) < 6:
        return
    info.frame = SOF_NAMES.get(marker, f"SOF{marker - 0xC0}")
    info.height, info.width = struct.unpack(">HH", payload[1:5])
    ncomp = payload[5]
    factors = []
    for c in range(ncomp):
        off = 6 + c * 3
        if off + 2 < len(payload):
            hv = payload[off + 1]
            factors.append((hv >> 4, hv & 0x0F))
    if len(factors) == 1:
        info.subsampling = "grayscale"
    elif len(factors) >= 3:
        (h0, v0), (h1, v1) = factors[0], factors[1]
        if (h0, v0) == (h1, v1):
            info.subsampling = "4:4:4"
        elif h0 == 2 * h1 and v0 == 2 * v1:
            info.subsampling = "4:2:0"
        elif h0 == 2 * h1 and v0 == v1:
            info.subsampling = "4:2:2"
        elif h0 == 4 * h1 and v0 == v1:
            info.subsampling = "4:1:1"
        else:
            info.subsampling = f"{h0}x{v0}/{h1}x{v1}"


def ijg_table(base: list[int], quality: int) -> list[int]:
    q = max(1, min(100, quality))
    scale = 5000 // q if q < 50 else 200 - 2 * q
    return [max(1, min(255, (b * scale + 50) // 100)) for b in base]


def estimate_quality(info: JpegInfo) -> tuple[int | None, bool, float]:
    """(closest IJG quality, exact standard-table match, mean abs error) from table 0
    (and table 1 when present)."""
    if 0 not in info.qtables:
        return None, False, 0.0
    best_q, best_err = None, float("inf")
    for q in range(1, 101):
        err = sum(abs(a - b) for a, b in zip(info.qtables[0], ijg_table(STD_LUMA, q), strict=True))
        if 1 in info.qtables:
            err += sum(
                abs(a - b) for a, b in zip(info.qtables[1], ijg_table(STD_CHROMA, q), strict=True)
            )
        if err < best_err:
            best_q, best_err = q, err
    count = 128 if 1 in info.qtables else 64
    return best_q, best_err == 0, best_err / count


@dataclass
class PngInfo:
    width: int = 0
    height: int = 0
    bit_depth: int = 0
    color_type: int = 0
    chunks: list[str] = field(default_factory=list)
    text: dict[str, str] = field(default_factory=dict)
    trailing_bytes: int = 0
    trailing_head: bytes = b""
    has_exif: bool = False
    has_c2pa: bool = False
    has_icc: bool = False
    errors: list[str] = field(default_factory=list)


def parse_png(data: bytes) -> PngInfo:
    info = PngInfo()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        info.errors.append("no PNG signature")
        return info
    i, n = 8, len(data)
    while i + 8 <= n:
        length = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8].decode("latin-1", "replace")
        body = data[i + 8 : i + 8 + length]
        info.chunks.append(ctype)
        if ctype == "IHDR" and len(body) >= 13:
            info.width, info.height = struct.unpack(">II", body[:8])
            info.bit_depth, info.color_type = body[8], body[9]
        elif ctype == "tEXt":
            k, _, v = body.partition(b"\x00")
            info.text[k.decode("latin-1", "replace")] = v.decode("latin-1", "replace")[:20000]
        elif ctype == "zTXt":
            k, _, rest = body.partition(b"\x00")
            try:
                v = zlib.decompress(rest[1:]).decode("latin-1", "replace")
            except zlib.error:
                v = "<undecodable zTXt>"
            info.text[k.decode("latin-1", "replace")] = v[:20000]
        elif ctype == "iTXt":
            k, _, rest = body.partition(b"\x00")
            comp_flag = rest[0] if rest else 0
            parts = rest[2:].split(b"\x00", 2)
            text = parts[2] if len(parts) == 3 else b""
            if comp_flag:
                try:
                    text = zlib.decompress(text)
                except zlib.error:
                    text = b"<undecodable iTXt>"
            info.text[k.decode("latin-1", "replace")] = text.decode("utf-8", "replace")[:20000]
        elif ctype == "eXIf":
            info.has_exif = True
        elif ctype == "caBX":
            info.has_c2pa = True
        elif ctype == "iCCP":
            info.has_icc = True
        i += 12 + length
        if ctype == "IEND":
            info.trailing_bytes = n - i
            info.trailing_head = data[i : i + 16]
            break
    else:
        if "IEND" not in info.chunks:
            info.errors.append("no IEND chunk (file truncated or damaged)")
    return info


def describe_trailing(head: bytes) -> str:
    """Name the format of data hidden after the end-of-image marker, if recognisable."""
    sigs = {
        b"PK\x03\x04": "ZIP archive",
        b"Rar!": "RAR archive",
        b"7z\xbc\xaf": "7-Zip archive",
        b"%PDF": "PDF document",
        b"\xff\xd8\xff": "another JPEG image",
        b"\x89PNG": "PNG image",
        b"MZ": "Windows executable",
        b"\x7fELF": "Linux executable",
        b"ftyp": "MP4 video",
    }
    for sig, name in sigs.items():
        if head.startswith(sig) or (sig == b"ftyp" and head[4:8] == sig):
            return name
    if head.strip(b"\x00") == b"":
        return "zero padding"
    return "unrecognised data"
