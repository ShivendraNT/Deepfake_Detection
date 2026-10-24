"""Which channel (and so which detectors) a dropped file goes to. One table for every surface:
the desktop drop zone, case uploads, the consumer Scam Check page and the kit runner."""

from __future__ import annotations

from pathlib import Path

from satyapan.contracts.enums import Channel

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log"}
EMAIL_SUFFIXES = {".eml", ".msg", ".mbox"}
VOICE_SUFFIXES = {".wav", ".m4a", ".ogg", ".opus", ".mp3", ".webm", ".aac", ".amr", ".flac"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".3gp"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def channel_for(filename: str | None, media_type: str) -> Channel:
    suffix = Path(filename or "").suffix.lower()
    if suffix in EMAIL_SUFFIXES or media_type == "message/rfc822":
        return Channel.EMAIL
    if suffix == ".pdf" or media_type == "application/pdf":
        return Channel.PDF
    if suffix in VIDEO_SUFFIXES or media_type.startswith("video/"):
        return Channel.VIDEO
    if suffix in VOICE_SUFFIXES or media_type.startswith("audio/"):
        return Channel.VOICE_NOTE
    if suffix in IMAGE_SUFFIXES or media_type.startswith("image/"):
        return Channel.IMAGE
    return Channel.MANUAL
