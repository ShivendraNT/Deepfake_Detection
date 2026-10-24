"""All enums shared across Satyapan. CONTRACT FILE: do not edit without leader approval.

Every value here is a stable string that appears in JSON, the console and the extension.
Renaming a value is a breaking change (see docs/DECISIONS.md, ADR-010).
"""

from __future__ import annotations

from enum import StrEnum


class Band(StrEnum):
    """Risk band. Ordered PASS < VERIFY < HOLD. Use satyapan.policy.bands to compare."""

    PASS = "PASS"
    VERIFY = "VERIFY"
    HOLD = "HOLD"


BAND_ORDER: dict[Band, int] = {Band.PASS: 0, Band.VERIFY: 1, Band.HOLD: 2}


class ActionType(StrEnum):
    """Floor action types from the vendor-master comparison (ARCHITECTURE.md, floor table)."""

    K1 = "K1"  # known beneficiary, unchanged details, in-pattern amount
    K2 = "K2"  # known beneficiary, out-of-pattern amount or dormant > 180 days
    N1 = "N1"  # new beneficiary, amount <= de-minimis
    N2 = "N2"  # new beneficiary, amount > de-minimis
    C1 = "C1"  # existing vendor, bank/UPI details differ from master
    T1 = "T1"  # change to a trust anchor (phone/email on file, approver list)
    D1 = "D1"  # non-payment data/credential request
    NONE = "NONE"  # no pending action yet (e.g. a live call before any payment)


class CaseKind(StrEnum):
    PAYMENT = "PAYMENT"
    MASTER_CHANGE = "MASTER_CHANGE"
    DATA_REQUEST = "DATA_REQUEST"
    LIVE_CALL = "LIVE_CALL"


class SignalGroup(StrEnum):
    SENDER_AUTH = "sender_auth"
    DOCUMENT = "document"
    MEDIA = "media"
    ASK = "ask"
    STYLE = "style"
    WATCHLIST = "watchlist"
    PROVENANCE = "provenance"  # Satyapan Seal: who produced the audio (C14, docs/SEAL.md)
    CROSS_CHANNEL = "cross_channel"  # X1: a call/message ask + a payment, in under 30 minutes


class SignalSource(StrEnum):
    DETERMINISTIC = "deterministic"
    ML = "ml"
    LLM = "llm"
    HUMAN = "human"


class Strength(StrEnum):
    WEAK = "weak"
    STRONG = "strong"


class TargetRule(StrEnum):
    """How a signal maps to a target band. Evaluated ONLY in satyapan.policy.targets."""

    NONE = "NONE"  # informational, never changes the band
    VERIFY = "VERIFY"
    HOLD = "HOLD"
    VERIFY_HOLD_IF_FLOOR_GE_VERIFY = "VERIFY_HOLD_IF_FLOOR_GE_VERIFY"
    PLUS_ONE = "PLUS_ONE"  # one band above the floor band
    HOLD_IF_MONEY_ELSE_VERIFY = "HOLD_IF_MONEY_ELSE_VERIFY"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    CLEARED = "CLEARED"
    SUSPECTED_FRAUD = "SUSPECTED_FRAUD"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    OVERRIDDEN = "OVERRIDDEN"


class Queue(StrEnum):
    MAKER = "MAKER"
    CHECKER_REVIEW = "CHECKER_REVIEW"


class Role(StrEnum):
    MAKER = "maker"
    CHECKER = "checker"
    SECURITY = "security"
    REQUESTER = "requester"  # the claimed requester, e.g. the CFO answering OOB-Confirm
    SYSTEM = "system"


class GreyReason(StrEnum):
    PARSE_FAILURE = "PARSE_FAILURE"
    DETECTOR_ERROR = "DETECTOR_ERROR"
    SPEECH_TOO_SHORT = "SPEECH_TOO_SHORT"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    CONFLICTING_TXN_DATA = "CONFLICTING_TXN_DATA"


class AskType(StrEnum):
    A1 = "A1"  # transfer to a new or "safe" account
    A2 = "A2"  # share OTP/PIN/password/CVV
    A3 = "A3"  # install remote-access / screen-share app
    A4 = "A4"  # secrecy or isolation
    A5 = "A5"  # bypass a process
    A6 = "A6"  # pay via gift card, crypto or UPI collect
    A7 = "A7"  # change of payee or bank details


class Channel(StrEnum):
    EMAIL = "email"
    PDF = "pdf"
    VOICE_NOTE = "voice_note"
    CALL_RECORDING = "call_recording"
    LIVE_CALL = "live_call"
    VIDEO = "video"  # a recorded video handed to Satya (call recording, forwarded clip)
    IMAGE = "image"  # a photo or screenshot handed to Satya (face check + text in the image)
    WHATSAPP_TEXT = "whatsapp_text"
    MANUAL = "manual"


class PaymentRail(StrEnum):
    NEFT = "NEFT"
    RTGS = "RTGS"
    IMPS = "IMPS"
    UPI = "UPI"


class OOBResult(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"


class CallbackOutcome(StrEnum):
    CONFIRMED = "CONFIRMED"
    DENIED = "DENIED"
    NO_ANSWER = "NO_ANSWER"


class ClearanceMethod(StrEnum):
    CALLBACK_MASTER_NUMBER = "CALLBACK_MASTER_NUMBER"
    OOB_CONFIRM = "OOB_CONFIRM"
    BANK_NAME_MATCH = "BANK_NAME_MATCH"
    CHECKER_CALLBACK = "CHECKER_CALLBACK"
    SECURITY_ACK = "SECURITY_ACK"
    SECOND_APPROVER = "SECOND_APPROVER"


class VoiceLabel(StrEnum):
    LIKELY_SYNTHETIC = "likely_synthetic"
    INCONCLUSIVE = "inconclusive"
    NO_SIGNS = "no_signs"


class VideoLabel(StrEnum):
    """Video deepfake check result (docs/VIDEO_DEEPFAKE.md). Mirrors VoiceLabel."""

    LIKELY_SYNTHETIC = "likely_synthetic"
    INCONCLUSIVE = "inconclusive"
    NO_SIGNS = "no_signs"


class CustodyEvent(StrEnum):
    INTAKE = "INTAKE"
    ANALYSIS = "ANALYSIS"
    DECISION = "DECISION"
    STATUS_CHANGE = "STATUS_CHANGE"
    EXPORT = "EXPORT"
    ANCHOR = "ANCHOR"


class SealSessionKind(StrEnum):
    """What a Voice Seal session is bound to (docs/SEAL.md)."""

    MEETING = "meeting"  # a live meeting (Meet/Teams URL)
    VOICE_NOTE = "voice_note"  # one recorded voice note (note id)


class SealEpochStatus(StrEnum):
    """Per-epoch result shown to every role (raw z is for checker/security only)."""

    SEALED = "sealed"  # z >= tau_epoch
    WEAK = "weak"  # some seal energy, below tau_epoch
    UNSEALED = "unsealed"  # speech present, no seal (a gap if the session is sealed)
    NO_SPEECH = "no_speech"  # too little speech to judge


class Lang(StrEnum):
    EN = "en"
    HI = "hi"


class ReasonCode(StrEnum):
    """Every reason the system can show. T14 must give each one EN + HI text."""

    # Floor (from transaction vs vendor master)
    FLOOR_K1_KNOWN_IN_PATTERN = "FLOOR_K1_KNOWN_IN_PATTERN"
    FLOOR_K2_OUT_OF_PATTERN = "FLOOR_K2_OUT_OF_PATTERN"
    FLOOR_N1_NEW_SMALL = "FLOOR_N1_NEW_SMALL"
    FLOOR_N2_NEW_LARGE = "FLOOR_N2_NEW_LARGE"
    FLOOR_C1_BANK_CHANGED = "FLOOR_C1_BANK_CHANGED"
    FLOOR_T1_TRUST_ANCHOR = "FLOOR_T1_TRUST_ANCHOR"
    FLOOR_D1_DATA_REQUEST = "FLOOR_D1_DATA_REQUEST"
    FLOOR_NONE = "FLOOR_NONE"
    # Email (C3)
    EMAIL_AUTH_PASS = "EMAIL_AUTH_PASS"
    EMAIL_DMARC_FAIL = "EMAIL_DMARC_FAIL"
    EMAIL_LOOKALIKE_DOMAIN = "EMAIL_LOOKALIKE_DOMAIN"
    EMAIL_BANK_NOT_BANK_IN = "EMAIL_BANK_NOT_BANK_IN"
    EMAIL_REPLYTO_MISMATCH = "EMAIL_REPLYTO_MISMATCH"
    EMAIL_FREEMAIL_CORPORATE = "EMAIL_FREEMAIL_CORPORATE"
    # Document (C4)
    DOC_NO_ISSUES = "DOC_NO_ISSUES"
    DOC_ACCOUNT_MISMATCH = "DOC_ACCOUNT_MISMATCH"
    DOC_PDF_EDITED = "DOC_PDF_EDITED"
    # Voice (C6)
    VOICE_NO_SIGNS = "VOICE_NO_SIGNS"
    VOICE_INCONCLUSIVE = "VOICE_INCONCLUSIVE"
    VOICE_LIKELY_SYNTHETIC = "VOICE_LIKELY_SYNTHETIC"
    # Video (C15, docs/VIDEO_DEEPFAKE.md): face blending, pulse, lighting, lip-sync cues
    VIDEO_NO_SIGNS = "VIDEO_NO_SIGNS"
    VIDEO_INCONCLUSIVE = "VIDEO_INCONCLUSIVE"  # also: no usable face (camera off, too small)
    VIDEO_LIKELY_SYNTHETIC = "VIDEO_LIKELY_SYNTHETIC"
    VIDEO_SUSPICIOUS = "VIDEO_SUSPICIOUS"  # usable face scored between tau_lo and tau_hi
    # Still image (photo / profile picture): the same face CNN on one face crop
    IMAGE_FACE_NO_SIGNS = "IMAGE_FACE_NO_SIGNS"
    IMAGE_FACE_INCONCLUSIVE = "IMAGE_FACE_INCONCLUSIVE"  # also: no usable face in the image
    IMAGE_FACE_LIKELY_SYNTHETIC = "IMAGE_FACE_LIKELY_SYNTHETIC"
    IMAGE_FACE_SUSPICIOUS = "IMAGE_FACE_SUSPICIOUS"  # scored between tau_lo and tau_hi
    # Asks (C5)
    ASK_NEW_ACCOUNT = "ASK_NEW_ACCOUNT"
    ASK_CREDENTIAL = "ASK_CREDENTIAL"
    ASK_REMOTE_ACCESS = "ASK_REMOTE_ACCESS"
    ASK_SECRECY = "ASK_SECRECY"
    ASK_BYPASS = "ASK_BYPASS"
    ASK_UNUSUAL_PAYMENT_METHOD = "ASK_UNUSUAL_PAYMENT_METHOD"
    ASK_PAYEE_CHANGE = "ASK_PAYEE_CHANGE"
    # Cross-channel (X1, deterministic): a call/message ask and a payment in the same case,
    # within 30 minutes. Evidence can only raise the band.
    CROSS_CHANNEL_SEQUENCE = "CROSS_CHANNEL_SEQUENCE"  # A1/A7 ask + new/changed beneficiary
    CROSS_CHANNEL_URGENT_BYPASS = "CROSS_CHANNEL_URGENT_BYPASS"  # plus A4 secrecy / A5 bypass
    # Style (C8 / LLM) — raise-only, capped at VERIFY
    STYLE_PRESSURE = "STYLE_PRESSURE"
    # Scam-text model (docs/TEXT_BENCHMARK.md): reads like known scam/phishing text. Style group,
    # so capped at VERIFY, never strong, never corroborates an ask.
    TEXT_SCAM_LIKELY = "TEXT_SCAM_LIKELY"
    # Watchlist (R4)
    WATCHLIST_HIT = "WATCHLIST_HIT"
    # Provenance: Satyapan Seal (C14, docs/SEAL.md). Raise-only like every other signal.
    VOICE_SEALED = "VOICE_SEALED"  # info only: never lowers a band, never clears anything
    VOICE_UNSEALED_CLAIMED_EXEC = "VOICE_UNSEALED_CLAIMED_EXEC"  # weak, at most VERIFY
    SEAL_PRESENCE_CONFLICT = "SEAL_PRESENCE_CONFLICT"  # claimed exec is sealing another meeting
    # Decision-level codes (added by the policy engine, never by detectors)
    MULTI_GROUP_STRONG = "MULTI_GROUP_STRONG"
    GREY_FLAG = "GREY_FLAG"
    OOB_DENIED = "OOB_DENIED"
    OOB_APPROVED = "OOB_APPROVED"


ASK_TO_REASON: dict[AskType, ReasonCode] = {
    AskType.A1: ReasonCode.ASK_NEW_ACCOUNT,
    AskType.A2: ReasonCode.ASK_CREDENTIAL,
    AskType.A3: ReasonCode.ASK_REMOTE_ACCESS,
    AskType.A4: ReasonCode.ASK_SECRECY,
    AskType.A5: ReasonCode.ASK_BYPASS,
    AskType.A6: ReasonCode.ASK_UNUSUAL_PAYMENT_METHOD,
    AskType.A7: ReasonCode.ASK_PAYEE_CHANGE,
}

FLOOR_REASON: dict[ActionType, ReasonCode] = {
    ActionType.K1: ReasonCode.FLOOR_K1_KNOWN_IN_PATTERN,
    ActionType.K2: ReasonCode.FLOOR_K2_OUT_OF_PATTERN,
    ActionType.N1: ReasonCode.FLOOR_N1_NEW_SMALL,
    ActionType.N2: ReasonCode.FLOOR_N2_NEW_LARGE,
    ActionType.C1: ReasonCode.FLOOR_C1_BANK_CHANGED,
    ActionType.T1: ReasonCode.FLOOR_T1_TRUST_ANCHOR,
    ActionType.D1: ReasonCode.FLOOR_D1_DATA_REQUEST,
    ActionType.NONE: ReasonCode.FLOOR_NONE,
}
