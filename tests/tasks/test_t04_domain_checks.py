"""T04 acceptance: domain checks (25 table-driven cases) + email signals on fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.email.domains import (
    claims_to_be_bank,
    is_bank_in,
    is_freemail,
    is_lookalike,
    levenshtein,
    normalise_domain,
)

pytestmark = pytest.mark.task("T04")

KNOWN = {"kaveri-packaging.example", "narmada-logistics.example", "demo-industries.example"}

CASES = [
    ("lev", ("kitten", "sitting"), 3),
    ("lev", ("", "abc"), 3),
    ("lev", ("same", "same"), 0),
    ("lev", ("packaging", "packagimg"), 1),
    ("look", "kaveri-packagimg.example", "kaveri-packaging.example"),
    ("look", "kaveri-packaging.example", None),  # exact match is not a look-alike
    ("look", "kaveri-packagin.example", "kaveri-packaging.example"),
    ("look", "narmada-logist1cs.example", "narmada-logistics.example"),
    ("look", "demo-lndustries.example", "demo-industries.example"),
    ("look", "totally-different.example", None),
    ("look", "kaveripackaging.example", "kaveri-packaging.example"),  # dropped hyphen
    ("look", "kаveri-packaging.example", "kaveri-packaging.example"),  # Cyrillic 'а'
    ("bankin", "fictionalbanka.bank.in", True),
    ("bankin", "bank.in", True),
    ("bankin", "fictional-bank.in", False),
    ("bankin", "bank.in.evil.example", False),
    ("free", "gmail.com", True),
    ("free", "rediffmail.com", True),
    ("free", "demo-industries.example", False),
    ("claim", ("Fictional Bank A Alerts", "x.example"), True),
    ("claim", ("Narmada Accounts", "narmada-logistics.example"), False),
    ("claim", ("Alerts", "fictional-bank-a-secure.example"), True),
    ("claim", ("Riverbank Foods", "riverbank-foods.example"), False),
    ("claim", ("RBI Helpdesk", "rbi-help.example"), True),
    ("norm", "Kaveri-Packaging.Example.", "kaveri-packaging.example"),
]


@pytest.mark.parametrize(("kind", "arg", "expected"), CASES)
def test_domain_table(kind, arg, expected) -> None:
    if kind == "lev":
        assert levenshtein(*arg) == expected
    elif kind == "look":
        assert is_lookalike(arg, KNOWN) == expected
    elif kind == "bankin":
        assert is_bank_in(arg) is expected
    elif kind == "free":
        assert is_freemail(arg) is expected
    elif kind == "claim":
        assert claims_to_be_bank(*arg) is expected
    elif kind == "norm":
        assert normalise_domain(arg) == expected


EMAILS = Path(__file__).resolve().parents[2] / "data" / "demo" / "emails"
EXPECTED = json.loads((EMAILS / "expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_email_signals_on_fixtures(master, name: str) -> None:
    from satyapan.email.parser import parse_eml
    from satyapan.email.signals import email_signals

    parsed = parse_eml(
        (EMAILS / name).read_bytes(), trusted_authserv_id="mx.demo-industries.example"
    )
    out = email_signals(parsed, master, "ev_test")
    assert sorted(s.code.value for s in out.signals) == sorted(EXPECTED[name]["signals"])
    assert sorted(g.value for g in out.grey_reasons) == sorted(EXPECTED[name]["grey"])
    assert all(s.source == "deterministic" for s in out.signals)
