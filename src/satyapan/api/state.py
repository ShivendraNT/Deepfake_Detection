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
    transcriber_override: Transcriber | None = None  # tests inject FakeTranscriber here

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

    def live(self) -> Any:
        if self._live is None:
            from satyapan.live.service import LiveService

            transcriber = self.transcriber_override
            if transcriber is None:
                from satyapan.adapters.transcribe_whisper import WhisperTranscriber

                transcriber = WhisperTranscriber()
            self._live = LiveService(
                master=self.master, transcriber=transcriber, thresholds=self.thresholds
            )
        return self._live
