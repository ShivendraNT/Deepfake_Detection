"""F12 acceptance: the golden-hour demo media manifest, generator and linked fixtures.

The manifest keeps the finale-plan scenario labels (``A1_NEW_BENEFICIARY`` etc.). The frozen
repository contract is different: :class:`AskType` is ``A1``-``A7``, where A1 means a new/safe
account and A4 means secrecy/isolation. Urgency is a style signal and the amount is transaction
data, neither is an AskType. The extractor test therefore asserts the real contract members that
the supplied English and Hinglish scripts actually trigger, rather than inventing enum values.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from satyapan.asks.extractor import extract_asks
from satyapan.contracts.enums import AskType

ROOT = Path(__file__).resolve().parents[2]
FINALE_DIR = ROOT / "data" / "demo" / "finale"
MANIFEST_PATH = FINALE_DIR / "manifest.json"
GENERATOR_PATH = FINALE_DIR / "generate_media.py"

_spec = importlib.util.spec_from_file_location("f12_generate_media", GENERATOR_PATH)
assert _spec is not None and _spec.loader is not None
_generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_generator)
generate_demo_wav = _generator.generate_demo_wav
validate_wav = _generator.validate_wav

# Scenario concept -> the AskType members the frozen lexicon can actually emit.
CONCEPT_TO_ASK_TYPES: dict[str, set[AskType]] = {
    "A1_NEW_BENEFICIARY": {AskType.A1},
    # Urgency is a style signal (STYLE_PRESSURE), not an ask.
    "A2_URGENT_DEADLINE": set(),
    # The script asks for secrecy ("don't loop in" / "mat batana"), which is A4.
    "A3_SECRECY_BYPASS": {AskType.A4},
    # The amount is transaction data, not an ask.
    "A5_LARGE_AMOUNT": set(),
}


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_schema() -> None:
    manifest = _manifest()

    required = {
        "scenario_id",
        "target",
        "impersonated_caller",
        "checker",
        "takes",
        "linked_evidence",
        "provenance",
    }
    assert required <= manifest.keys()
    assert manifest["scenario_id"] == "cfo_deepfake_rajesh"
    assert manifest["target"] == {"name": "Priya", "role": "Accounts Executive (Maker)"}
    assert manifest["impersonated_caller"] == {"name": "Rajesh", "role": "CFO"}
    assert manifest["checker"] == {"name": "Arjun", "role": "Accounts Manager"}

    takes = manifest["takes"]
    assert isinstance(takes, list) and len(takes) == 2
    assert {take["id"] for take in takes} == {"en", "hi"}

    expected_format = {
        "sample_rate": 16000,
        "channels": 1,
        "bit_depth": 16,
        "codec": "PCM16",
    }
    expected_asks = [
        "A1_NEW_BENEFICIARY",
        "A2_URGENT_DEADLINE",
        "A3_SECRECY_BYPASS",
        "A5_LARGE_AMOUNT",
    ]
    for take in takes:
        assert take["filename"] in {"rajesh_cfo_call_en.wav", "rajesh_cfo_call_hi.wav"}
        assert take["text"]
        assert "₹48.5 lakh" in take["text"]
        assert take["format"] == expected_format
        assert take["expected_asks"] == expected_asks
        assert set(take["expected_asks"]) <= CONCEPT_TO_ASK_TYPES.keys()

    assert manifest["linked_evidence"] == {
        "email": "data/demo/emails/02_bec_bank_change_narmada.eml",
        "invoice": "data/demo/invoices/inv_narmada_changed_bank.pdf",
        "case": "data/demo/cases/case_s07.json",
    }
    assert manifest["provenance"] == {
        "source_voice": "Consented teammate voice",
        "consent_form": "docs/consent/signed/consent_rajesh_voice.pdf",
        "model": "F5-TTS / XTTS-v2",
    }


def test_ask_extractor_detects_all_cfo_asks() -> None:
    manifest = _manifest()

    for take in manifest["takes"]:
        spans = extract_asks(take["text"])
        detected = {span.ask_type for span in spans}

        # Both scripts explicitly ask for a new/escrow account and secrecy.
        assert AskType.A1 in detected, f"{take['id']}: new beneficiary ask missing"
        assert AskType.A4 in detected, f"{take['id']}: secrecy ask missing"

        expected = set().union(*(CONCEPT_TO_ASK_TYPES[label] for label in take["expected_asks"]))
        assert expected <= detected, f"{take['id']}: expected {expected}, got {detected}"


def test_wav_generation_and_validation(tmp_path: Path) -> None:
    target = tmp_path / "rajesh_cfo_call_en.wav"
    generated = generate_demo_wav(target)

    assert generated == target
    assert target.is_file()

    info = validate_wav(target)
    assert info["valid"] is True
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert info["duration_s"] >= 4.0

    # The CLI helper must create both named takes when they are missing.
    cli_dir = tmp_path / "cli"
    generated_files = _generator.ensure_demo_wavs(cli_dir)
    assert {path.name for path in generated_files} == {
        "rajesh_cfo_call_en.wav",
        "rajesh_cfo_call_hi.wav",
    }
    assert all(validate_wav(path)["valid"] for path in generated_files)


def test_linked_fixtures_exist() -> None:
    linked = _manifest()["linked_evidence"]

    for relative_path in linked.values():
        assert (ROOT / relative_path).is_file(), relative_path

    # The three values are the exact Narmada/case_s07 fixtures requested for the demo.
    assert linked["email"].endswith("02_bec_bank_change_narmada.eml")
    assert linked["invoice"].endswith("inv_narmada_changed_bank.pdf")
    assert linked["case"].endswith("case_s07.json")
