"""Amazon Transcribe batch adapter (hi-IN / en-IN) for uploaded voice notes. TASK T17.

See docs/tasks/T17-voice-uploads.md. Fallback: WhisperTranscriber (local).
"""

from __future__ import annotations

import json
import time
import urllib.request
import uuid

from satyapan.adapters.base import TranscriptResult
from satyapan.settings import Settings

_MIME_TO_FORMAT = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/m4a": "mp4",
    "audio/flac": "flac",
    "audio/webm": "webm",
}


def _norm_language(code: str | None) -> str:
    if not code:
        return "unknown"
    c = code.lower()
    if c.startswith("hi"):
        return "hi"
    if c.startswith("en"):
        return "en"
    return c.split("-")[0]


class AwsTranscriber:
    """Uploads audio to the evidence bucket, starts a batch job with
    IdentifyLanguage over ["hi-IN", "en-IN"], polls with a deadline, returns the transcript."""

    def __init__(self, settings: Settings) -> None:
        import boto3  # type: ignore[import-not-found]  # noqa: PLC0415
        from botocore.config import Config  # type: ignore[import-not-found]  # noqa: PLC0415

        self.settings = settings
        self.bucket = settings.s3_bucket
        self.region = settings.aws_region
        self.timeout_s = settings.aws_timeout_s

        config = Config(
            connect_timeout=self.timeout_s,
            read_timeout=self.timeout_s,
            retries={"max_attempts": 1},
        )
        self.s3_client = boto3.client("s3", region_name=self.region, config=config)
        self.transcribe_client = boto3.client("transcribe", region_name=self.region, config=config)

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        media_format = _MIME_TO_FORMAT.get(mime, "wav")
        key = f"transcribe_uploads/{uuid.uuid4().hex}.{media_format}"
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=audio,
            ContentType=mime,
        )
        media_uri = f"s3://{self.bucket}/{key}"
        job_name = f"satyapan_{uuid.uuid4().hex[:16]}"

        job_kwargs: dict[str, object] = {
            "TranscriptionJobName": job_name,
            "Media": {"MediaFileUri": media_uri},
            "MediaFormat": media_format,
        }
        if language_hint:
            job_kwargs["LanguageCode"] = language_hint
        else:
            job_kwargs["IdentifyLanguage"] = True
            job_kwargs["LanguageOptions"] = ["hi-IN", "en-IN"]

        self.transcribe_client.start_transcription_job(**job_kwargs)

        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            res = self.transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            job = res.get("TranscriptionJob", {})
            status = job.get("TranscriptionJobStatus")
            if status == "COMPLETED":
                transcript_uri = job.get("Transcript", {}).get("TranscriptFileUri")
                if not transcript_uri:
                    return TranscriptResult(text="", language="unknown", engine="aws_transcribe")
                req = urllib.request.Request(transcript_uri, headers={"User-Agent": "Satyapan/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                    body = json.loads(resp.read().decode("utf-8"))
                transcripts = body.get("results", {}).get("transcripts", [])
                text = transcripts[0].get("transcript", "") if transcripts else ""
                lang = _norm_language(job.get("LanguageCode"))
                return TranscriptResult(
                    text=text,
                    language=lang,
                    engine="aws_transcribe",
                )
            if status == "FAILED":
                reason = job.get("FailureReason", "unknown failure")
                raise RuntimeError(f"Transcribe job failed: {reason}")
            time.sleep(0.5)

        raise TimeoutError(f"Transcribe job timed out after {self.timeout_s} s")
