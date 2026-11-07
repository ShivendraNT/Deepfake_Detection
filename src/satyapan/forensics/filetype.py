"""What a file really is, from its bytes (magic numbers), never from its name.

A mismatch between the two (a WhatsApp video renamed .jpg, an executable renamed .mp3) is
itself a finding: examiners record the true format, not the claimed one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from satyapan.forensics.models import Hashes, MediaKind


@dataclass(frozen=True)
class Sniffed:
    format: str  # short name: jpeg, png, mp4, wav ...
    mime: str
    kind: MediaKind
    extensions: tuple[str, ...]  # extensions that agree with the format


_FTYP_AUDIO = {b"M4A ", b"M4B ", b"M4P ", b"F4A ", b"F4B "}
_FTYP_HEIF = {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"}
_FTYP_AVIF = {b"avif", b"avis"}
_FTYP_QT = {b"qt  "}
_FTYP_3GP = {b"3gp4", b"3gp5", b"3gp6", b"3gp7", b"3ge6", b"3ge7", b"3gg6", b"3g2a"}


def sniff(data: bytes) -> Sniffed:
    head = data[:64]
    if head.startswith(b"\xff\xd8\xff"):
        return Sniffed("jpeg", "image/jpeg", MediaKind.IMAGE, ("jpg", "jpeg", "jpe", "jfif"))
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return Sniffed("png", "image/png", MediaKind.IMAGE, ("png",))
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return Sniffed("gif", "image/gif", MediaKind.IMAGE, ("gif",))
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return Sniffed("webp", "image/webp", MediaKind.IMAGE, ("webp",))
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return Sniffed("wav", "audio/wav", MediaKind.AUDIO, ("wav", "wave"))
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return Sniffed("avi", "video/x-msvideo", MediaKind.VIDEO, ("avi",))
    if head[:2] == b"BM" and len(data) > 26:
        return Sniffed("bmp", "image/bmp", MediaKind.IMAGE, ("bmp", "dib"))
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return Sniffed("tiff", "image/tiff", MediaKind.IMAGE, ("tif", "tiff", "dng"))
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _FTYP_HEIF:
            return Sniffed("heic", "image/heic", MediaKind.IMAGE, ("heic", "heif"))
        if brand in _FTYP_AVIF:
            return Sniffed("avif", "image/avif", MediaKind.IMAGE, ("avif",))
        if brand in _FTYP_AUDIO:
            return Sniffed("m4a", "audio/mp4", MediaKind.AUDIO, ("m4a", "m4b", "aac", "mp4"))
        if brand in _FTYP_QT:
            return Sniffed("mov", "video/quicktime", MediaKind.VIDEO, ("mov", "qt", "mp4"))
        if brand in _FTYP_3GP:
            return Sniffed("3gp", "video/3gpp", MediaKind.VIDEO, ("3gp", "3g2", "mp4"))
        return Sniffed("mp4", "video/mp4", MediaKind.VIDEO, ("mp4", "m4v", "mov", "3gp"))
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        fmt = "webm" if b"webm" in data[:4096] else "mkv"
        return Sniffed(fmt, f"video/{'webm' if fmt == 'webm' else 'x-matroska'}",
                       MediaKind.VIDEO, ("webm", "mkv", "mka"))  # fmt: skip
    if head.startswith(b"OggS"):
        if b"OpusHead" in data[:512]:
            return Sniffed("opus", "audio/ogg", MediaKind.AUDIO, ("opus", "ogg", "oga"))
        if b"theora" in data[:512]:
            return Sniffed("ogv", "video/ogg", MediaKind.VIDEO, ("ogv", "ogg"))
        return Sniffed("ogg", "audio/ogg", MediaKind.AUDIO, ("ogg", "oga"))
    if head.startswith(b"fLaC"):
        return Sniffed("flac", "audio/flac", MediaKind.AUDIO, ("flac",))
    if head.startswith(b"#!AMR"):
        return Sniffed("amr", "audio/amr", MediaKind.AUDIO, ("amr",))
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE6 == 0xE2):
        return Sniffed("mp3", "audio/mpeg", MediaKind.AUDIO, ("mp3",))
    if len(head) > 1 and head[0] == 0xFF and head[1] & 0xF6 == 0xF0:
        return Sniffed("aac", "audio/aac", MediaKind.AUDIO, ("aac", "adts"))
    if head.startswith(b"%PDF"):
        return Sniffed("pdf", "application/pdf", MediaKind.DOCUMENT, ("pdf",))
    if head.startswith(b"PK\x03\x04"):
        return Sniffed("zip", "application/zip", MediaKind.OTHER, ("zip", "docx", "xlsx", "apk"))
    if head[:2] == b"MZ":
        return Sniffed("exe", "application/x-msdownload", MediaKind.OTHER, ("exe", "dll"))
    if head[:4] == b"\x7fELF":
        return Sniffed("elf", "application/x-elf", MediaKind.OTHER, ("so", "bin"))
    return Sniffed("unknown", "application/octet-stream", MediaKind.OTHER, ())


def extension_of(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].strip().lower()[:12]


def extension_mismatch(sniffed: Sniffed, filename: str | None) -> bool:
    ext = extension_of(filename)
    if not ext or sniffed.format == "unknown":
        return False
    return ext not in sniffed.extensions


def hashes(data: bytes) -> Hashes:
    """MD5 + SHA-1 + SHA-256 of the raw bytes, computed before anything parses them.
    MD5/SHA-1 are recorded because Indian FSL worksheets and seizure memos still quote them;
    SHA-256 is the identity the lab uses."""
    return Hashes(
        md5=hashlib.md5(data, usedforsecurity=False).hexdigest(),
        sha1=hashlib.sha1(data, usedforsecurity=False).hexdigest(),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )
