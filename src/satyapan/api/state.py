"""Application state shared by all routes. PRE-IMPLEMENTED (T01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from satyapan.adapters.base import InAppMailer, Mailer, Transcriber
from satyapan.master.store import MasterData, load_master
from satyapan.repository import CaseRepository
from satyapan.settings import Settings
from satyapan.vault.custody import CustodyLog
from satyapan.voice.rules import VoiceThresholds, load_thresholds


@dataclass
class AppState:
    settings: Settings
    master: MasterData
    repo: CaseRepository
    custody: CustodyLog
    thresholds: VoiceThresholds
    in_app_mailer: InAppMailer = field(default_factory=InAppMailer)
    # Created lazily by the task that owns them (so a missing task -> HTTP 501, not a crash):
    _oob: Any = None  # T12: OOBService
    _live: Any = None  # T11: LiveService
    _watchlist: Any = None  # T13: Watchlist
    _store: Any = None  # T09: BlobStore
    _seal: Any = None  # C14 Satyapan Seal: SealServices (needs the `seal` extra)
    _companion: Any = None  # T25: CompanionService
    _transcriber: Any = None  # finale: the shared local speech engine (see transcriber())
    transcriber_override: Transcriber | None = None  # tests inject FakeTranscriber here
    _video: Any = None  # finale: VideoAnalyzer, or False when unavailable on this machine
    _video_error: str | None = None
    video_override: Any = None  # tests inject a fake analyzer here

    @classmethod
    def build(cls, settings: Settings) -> AppState:
        master = load_master(settings.data_dir)
        return cls(
            settings=settings,
            master=master,
            repo=CaseRepository.from_fixtures(master, settings.data_dir / "cases"),
            custody=CustodyLog(settings.custody_db),
            thresholds=load_thresholds(settings.voice_thresholds_path),
        )

    def mailer(self) -> Mailer:
        """SES in AWS mode (T12), else the in-app mailer. Falls back on any SES error."""
        if self.settings.aws_mode and self.settings.ses_sender:
            try:
                from satyapan.adapters.ses_mailer import SesMailer

                return SesMailer(self.settings)
            except Exception:  # noqa: BLE001 - fallback by design
                return self.in_app_mailer
        return self.in_app_mailer

    def oob(self) -> Any:
        if self._oob is None:
            from satyapan.workflows.oob import OOBService

            self._oob = OOBService(mailer=self.mailer())
        return self._oob

    def store(self) -> Any:
        if self._store is None:
            from satyapan.vault.storage import get_storage

            self._store = get_storage(self.settings)
        return self._store

    def watchlist(self) -> Any:
        if self._watchlist is None:
            from satyapan.workflows.watchlist import Watchlist

            self._watchlist = Watchlist()
        return self._watchlist

    def seal(self) -> Any:
        if self._seal is None:
            from satyapan.seal.service import SealServices

            self._seal = SealServices.build()
        return self._seal

    def transcriber(self) -> Any:
        """The one speech engine for live calls and voice notes.

        Tests inject `transcriber_override`. Otherwise a local Whisper engine (mlx-whisper on
        Apple Silicon, faster-whisper elsewhere), or an UnavailableTranscriber that explains
        what to install. Never a silent fake: a deaf Satya must say so.
        """
        if self.transcriber_override is not None:
            return self.transcriber_override
        if self._transcriber is None:
            from satyapan.adapters.transcribe_local import build_transcriber

            self._transcriber = build_transcriber()
        return self._transcriber

    def asr_status(self) -> dict[str, Any]:
        """Readiness of the speech engine, for /companion/health and the Notebook."""
        engine = self.transcriber()
        status = getattr(engine, "status", None)
        if status is None:
            return {"engine": "override", "model": "", "ready": True, "error": None}
        result: dict[str, Any] = status.as_dict()
        return result

    def video(self) -> Any:
        """The video deepfake check (docs/VIDEO_DEEPFAKE.md), or None when this laptop lacks
        the `video` extra or the model files. Never a silent fake: video_status() says why."""
        if self.video_override is not None:
            return self.video_override
        if self._video is None:
            try:
                from satyapan.video.analyzer import VideoAnalyzer

                self._video = VideoAnalyzer.load()
            except Exception as exc:  # noqa: BLE001 - VideoUnavailable or a broken install
                self._video = False
                self._video_error = str(exc)[:300]
        return self._video or None

    def video_status(self) -> dict[str, Any]:
        analyzer = self.video()
        if analyzer is None:
            return {"ready": False, "error": self._video_error, "model": None}
        thr = getattr(analyzer, "thresholds", None)
        return {
            "ready": True,
            "error": None,
            "model": getattr(thr, "model_version", "fake"),
            "calibrated": bool(getattr(thr, "calibrated", False)),
        }

    def live(self) -> Any:
        if self._live is None:
            from satyapan.live.service import LiveService

            self._live = LiveService(
                master=self.master,
                transcriber=self.transcriber(),
                thresholds=self.thresholds,
                video_factory=self.video,
            )
        return self._live

    def companion(self) -> Any:
        """T25: the desktop companion service (in-memory consent state + SSE bus)."""
        if self._companion is None:
            from satyapan.api.companion.service import CompanionService

            self._companion = CompanionService(master=self.master, repo=self.repo)
        return self._companion
