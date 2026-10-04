"""T03 acceptance: .eml parser. Run: make task T=T03"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.email.parser import extract_attachments, parse_auth_results, parse_eml

pytestmark = pytest.mark.task("T03")

EMAILS = Path(__file__).resolve().parents[2] / "data" / "demo" / "emails"
EXPECTED = json.loads((EMAILS / "expected.json").read_text(encoding="utf-8"))
TRUSTED = "mx.demo-industries.example"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_email(name: str) -> None:
    exp = EXPECTED[name]
    p = parse_eml((EMAILS / name).read_bytes(), trusted_authserv_id=TRUSTED)
    assert p.from_domain == exp["from_domain"]
    assert p.reply_to_domain == exp["reply_to_domain"]
    assert p.auth.dmarc == exp["dmarc"]
    assert p.auth.trusted == exp["trusted"]
    assert p.auth.untrusted_headers_seen == exp["untrusted_headers_seen"]
    assert len(p.attachments) == exp["attachments"]
    for s in exp["body_must_contain"]:
        assert s in p.body_text, f"{name}: body should contain {s!r}"
    for s in exp["body_must_not_contain"]:
        assert s not in p.body_text, f"{name}: hidden/injected text {s!r} leaked into body_text"


def test_auth_results_topmost_trusted_only() -> None:
    a = parse_auth_results(
        [
            f"{TRUSTED}; spf=fail; dkim=none; dmarc=fail",
            f"{TRUSTED}; spf=pass; dkim=pass; dmarc=pass",
        ],
        TRUSTED,
    )
    assert a.trusted and a.dmarc == "fail" and a.untrusted_headers_seen == 1


def test_auth_results_other_authserv_ignored() -> None:
    a = parse_auth_results(["mx.attacker.example; dmarc=pass"], TRUSTED)
    assert not a.trusted and a.dmarc == "unknown" and a.untrusted_headers_seen == 1


def test_attachment_sha256() -> None:
    raw = (EMAILS / "01_legit_invoice_kaveri.eml").read_bytes()
    atts = extract_attachments(raw)
    assert len(atts) == 1 and atts[0][0] == "inv_kaveri_ok.pdf" and atts[0][2].startswith(b"%PDF")
    p = parse_eml(raw, trusted_authserv_id=TRUSTED)
    import hashlib

    assert p.attachments[0].sha256 == hashlib.sha256(atts[0][2]).hexdigest()


def test_missing_from_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_eml(b"Subject: hi\r\n\r\nbody", trusted_authserv_id=TRUSTED)
