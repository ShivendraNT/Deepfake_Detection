"""Every technique the lab runs, per media kind, in execution order."""

from __future__ import annotations

from satyapan.forensics.audio import techniques as A
from satyapan.forensics.base import Technique
from satyapan.forensics.c2pa_check import C2PA
from satyapan.forensics.image import meta_techniques as M
from satyapan.forensics.image import model_techniques as ML
from satyapan.forensics.image import pixel_techniques as P
from satyapan.forensics.models import MediaKind
from satyapan.forensics.video import techniques as V

ALL: tuple[Technique, ...] = (
    M.STRUCTURE, M.METADATA, M.PROVENANCE, M.THUMBNAIL, C2PA, ML.WATERMARK,
    P.ELA, P.NOISE, P.COPY_MOVE, P.JPEG_GRID, ML.AIGEN, ML.FACES, P.SPECTRUM,
    A.AUDIO_CONTAINER, A.SPECTRAL, A.ENF, A.SPLICE, A.VOICE, A.TRANSCRIPT,
    V.VIDEO_CONTAINER, V.FRAMES, V.VIDEO_DEEPFAKE,
)  # fmt: skip
BY_ID = {t.id: t for t in ALL}


def for_kind(kind: MediaKind) -> list[Technique]:
    return sorted((t for t in ALL if kind in t.kinds), key=lambda t: (t.order, t.id))
