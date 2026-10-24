"""F11 acceptance: the golden-hour report pack v2 (five manual-only sections)."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, urlparse

import pytest

from satyapan.contracts import GENESIS_HASH, CustodyEvent, CustodyRow
from satyapan.report.pack import format_inr
from satyapan.report.pack_v2 import build_report_pack_v2
from tests.helpers import DEMO_DAY

ALLOWED_SOURCES = {"maker_entered", "vault", "vendor_master", "user_confirmed", "system"}
SECTION_ORDER = [
    "helpline_1930",
    "bank_fraud_desk",
    "ncrp_portal",
    "cert_in",
    "bsa_s63_part_a",
]


def _custody_rows(case) -> list[CustodyRow]:
    """Fake-but-valid custody chain: one INTAKE row per evidence, hashes matching the vault."""
    rows: list[CustodyRow] = []
    prev = GENESIS_HASH
    for seq, evidence in enumerate(case.evidence, start=1):
        row_hash = hashlib.sha256(f"{evidence.id}:{seq}".encode()).hexdigest()
        rows.append(
            CustodyRow(
                seq=seq,
                case_id=case.id,
                evidence_id=evidence.id,
                event=CustodyEvent.INTAKE,
                actor=evidence.submitted_by,
                at=evidence.captured_at,
                payload={"sha256": evidence.sha256, "size": evidence.size_bytes},
                prev_hash=prev,
                row_hash=row_hash,
            )
        )
        prev = row_hash
    return rows


@pytest.fixture()
def case(repo):
    found = repo.get("case_s12")
    assert found is not None
    return found


@pytest.fixture()
def custody(case) -> list[CustodyRow]:
    return _custody_rows(case)


@pytest.fixture()
def pack(case, master, custody):
    return build_report_pack_v2(case, master, custody, DEMO_DAY)


def _section(pack, section_id: str):
    matches = [s for s in pack.sections if s.id == section_id]
    assert len(matches) == 1, f"expected exactly one {section_id}"
    return matches[0]


def test_five_sections_in_exact_order(pack) -> None:
    assert [section.id for section in pack.sections] == SECTION_ORDER


def test_pack_is_a_manual_only_v2_draft(pack, case) -> None:
    assert pack.version == "2"
    assert pack.case_id == case.id
    assert pack.generated_at == DEMO_DAY
    assert pack.money_left_at == case.txn.sent_at
    assert pack.submission == "MANUAL_ONLY"
    assert pack.auto_submit is False
    for section in pack.sections:
        assert section.status == "DRAFT_REQUIRES_HUMAN_REVIEW"
        assert section.title and section.destination and section.body


def test_helpline_1930_is_utr_first_with_ordered_fields(pack) -> None:
    section = _section(pack, "helpline_1930")
    assert section.open_url == "tel:1930"
    assert section.body.splitlines()[0].startswith("UTR FAKEUTR620001:")
    assert [field.label for field in section.fields] == [
        "UTR",
        "Amount",
        "Date and time",
        "Debit account (masked)",
        "Beneficiary account",
        "IFSC / UPI",
        "Beneficiary bank",
    ]
    values = {field.label: field.value for field in section.fields}
    assert values["UTR"] == "FAKEUTR620001"
    assert values["Amount"] == format_inr(620000) == "₹6,20,000"
    assert values["Beneficiary account"] == "99996666006200"


def test_every_field_has_a_valid_source_and_vault_fields_cite_evidence(pack) -> None:
    for section in pack.sections:
        for field in section.fields:
            assert field.source in ALLOWED_SOURCES, (section.id, field.label)
            if field.source == "vault":
                assert field.evidence_id, (section.id, field.label)
            else:
                assert field.evidence_id is None or re.fullmatch(
                    r"^ev_[A-Za-z0-9_\-]+$", field.evidence_id
                )


def test_account_numbers_are_marked_sensitive(pack) -> None:
    helpline = _section(pack, "helpline_1930")
    by_label = {field.label: field for field in helpline.fields}
    assert by_label["Debit account (masked)"].sensitive is True
    assert by_label["Beneficiary account"].sensitive is True
    assert by_label["UTR"].sensitive is False

    bank = _section(pack, "bank_fraud_desk")
    beneficiary = next(field for field in bank.fields if field.label == "Beneficiary")
    assert "99996666006200" in beneficiary.value
    assert beneficiary.sensitive is True


def test_bank_mailto_is_url_encoded_and_matches_the_body(pack) -> None:
    section = _section(pack, "bank_fraud_desk")
    assert section.open_url is not None
    assert section.open_url.startswith("mailto:?")
    raw_query = section.open_url.split("?", 1)[1]
    assert " " not in raw_query and "\n" not in raw_query

    query = parse_qs(urlparse(section.open_url).query)
    fields = {field.label: field.value for field in section.fields}
    assert [field.label for field in section.fields] == [
        "To",
        "Subject",
        "UTR",
        "Amount",
        "Beneficiary",
    ]
    assert query["subject"] == [fields["Subject"]]
    assert query["body"] == [section.body]
    assert "FAKEUTR620001" in section.body and "₹6,20,000" in section.body


def test_ncrp_portal_has_portal_fields_then_vault_evidence(pack, case) -> None:
    section = _section(pack, "ncrp_portal")
    assert section.open_url == "https://cybercrime.gov.in"
    assert [field.label for field in section.fields[:6]] == [
        "Incident date/time",
        "Category",
        "Platform/channel",
        "Suspect identifiers",
        "Transaction table",
        "Description",
    ]
    evidence_fields = [field for field in section.fields if field.source == "vault"]
    assert len(evidence_fields) == len(case.evidence)
    for field, evidence in zip(evidence_fields, case.evidence, strict=True):
        assert field.evidence_id == evidence.id
        assert (evidence.filename or evidence.id) in field.value
        assert evidence.sha256 in field.value


def test_cert_in_applies_follows_body_corporate(case, master, custody) -> None:
    corporate = build_report_pack_v2(case, master, custody, DEMO_DAY)
    section = _section(corporate, "cert_in")
    assert section.applies is True
    assert section.open_url == "mailto:incident@cert-in.org.in"
    assert section.deadline_hint == (
        "Within 6 hours of noticing (CERT-In Directions, 2022) — confirm with your IT/legal team"
    )
    labels = [field.label for field in section.fields]
    assert labels == [
        "Incident type",
        "Time noticed",
        "Systems affected",
        "Description",
        "Actions taken",
        "Contact",
    ]
    assert any(
        field.value == "Identity theft, spoofing and phishing attacks" for field in section.fields
    )

    individual = build_report_pack_v2(case, master, custody, DEMO_DAY, body_corporate=False)
    assert _section(individual, "cert_in").applies is False


def test_bsa_s63_part_a_uses_custody_hashes_and_custodian_blanks(pack, case, custody) -> None:
    section = _section(pack, "bsa_s63_part_a")
    assert section.open_url is None
    assert "PART A" in section.body
    assert "[See section 63(4)]" in section.body
    assert "lawful control" in section.body.lower()
    assert "Signature" in section.body and "Designation" in section.body

    hash_fields = [field for field in section.fields if re.fullmatch(r"[0-9a-f]{64}", field.value)]
    assert len(hash_fields) == len(case.evidence)
    rows = {row.evidence_id: row for row in custody}
    for field, evidence in zip(hash_fields, case.evidence, strict=True):
        assert field.evidence_id == evidence.id
        assert field.source == "vault"
        assert field.value == evidence.sha256
        assert field.value == rows[evidence.id].payload["sha256"]

    assert [field.value for field in section.fields].count("SHA256") == len(case.evidence)
    assert any("________________" in field.value for field in section.fields)


def test_only_the_three_allowed_destinations_are_opened(pack) -> None:
    allowed = {"tel:1930", "https://cybercrime.gov.in"}
    for section in pack.sections:
        if section.open_url is None:
            continue
        assert section.open_url in allowed or section.open_url.startswith("mailto:"), section.id


def test_generated_by_is_carried_into_drafts(case, master, custody) -> None:
    custom = build_report_pack_v2(case, master, custody, DEMO_DAY, generated_by="emp_arjun")
    assert "emp_arjun" in _section(custom, "bsa_s63_part_a").body
    assert "emp_arjun" in _section(custom, "bank_fraud_desk").body


def test_fake_demo_data_only_and_indian_amount_formatting(pack) -> None:
    helpline = _section(pack, "helpline_1930")
    assert "₹6,20,000" in helpline.body
    assert "FAKEUTR620001" in helpline.body
    assert "FAKE0000620" in helpline.body
    assert "99996666006200" in helpline.body
