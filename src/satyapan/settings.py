"""Runtime settings from environment variables (see .env.example). No secrets in code.

AWS mode is OFF by default: every AWS adapter has a local fallback, and the demo never
depends on the cloud.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    aws_mode: bool = field(default_factory=lambda: _env("SATYAPAN_AWS_MODE", "off") == "on")
    aws_region: str = field(default_factory=lambda: _env("AWS_REGION", "ap-south-1"))
    s3_bucket: str = field(default_factory=lambda: _env("SATYAPAN_S3_BUCKET", ""))
    ses_sender: str = field(default_factory=lambda: _env("SATYAPAN_SES_SENDER", ""))
    aws_timeout_s: float = 5.0  # every AWS call times out fast and falls back
    # Local LLM (Ollama, free). T15 summaries; any error/timeout -> template fallback.
    llm_model: str = field(default_factory=lambda: _env("SATYAPAN_LLM_MODEL", "llama3.1:8b"))
    ollama_url: str = field(
        default_factory=lambda: _env("SATYAPAN_OLLAMA_URL", "http://127.0.0.1:11434")
    )
    llm_timeout_s: float = 30.0  # a local 8B model needs ~30 s for a summary
    data_dir: Path = field(
        default_factory=lambda: Path(_env("SATYAPAN_DATA_DIR", str(REPO_ROOT / "data" / "demo")))
    )
    vault_dir: Path = field(
        default_factory=lambda: Path(_env("SATYAPAN_VAULT_DIR", str(REPO_ROOT / "vault_data")))
    )
    custody_db: str = field(default_factory=lambda: _env("SATYAPAN_CUSTODY_DB", ":memory:"))
    trusted_authserv_id: str = field(
        default_factory=lambda: _env("SATYAPAN_TRUSTED_AUTHSERV_ID", "mx.demo-industries.example")
    )
    voice_thresholds_path: Path = field(
        default_factory=lambda: Path(
            _env("SATYAPAN_VOICE_THRESHOLDS", str(REPO_ROOT / "config" / "voice_thresholds.json"))
        )
    )


def get_settings() -> Settings:
    return Settings()
