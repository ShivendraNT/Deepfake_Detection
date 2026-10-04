"""Domain checks (look-alike, .bank.in, free-mail). TASK T04 — see docs/tasks/T04-domain-checks.md.

Pure functions, no network, no DNS lookups.
"""

from __future__ import annotations

# Free-mail providers: a "corporate" claim from these is suspicious.
FREEMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.in",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "rediffmail.com",
        "proton.me",
        "protonmail.com",
        "icloud.com",
        "aol.com",
        "zoho.com",
        "gmx.com",
        "mail.com",
        "yandex.com",
    }
)

# Words that mean "this sender claims to be a bank". Real Indian banks use *.bank.in (RBI).
BANK_CLAIM_WORDS: tuple[str, ...] = (
    "bank",
    "banking",
    "rbi",
    "reserve bank",
    "nbfc",
    "बैंक",
)


def levenshtein(a: str, b: str) -> int:
    """Classic edit distance (insert/delete/substitute = 1). Implement it yourself (DP table)."""
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")


def normalise_domain(domain: str) -> str:
    """Lower-case, strip a trailing dot, decode IDNA/punycode ("xn--...") to Unicode."""
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")


def is_lookalike(domain: str, known_domains: set[str], max_distance: int = 2) -> str | None:
    """Return the known domain this one imitates, or None.

    A look-alike is a domain that is NOT exactly a known domain but
    (a) has edit distance <= max_distance to a known domain, or
    (b) contains Unicode confusables (use confusable_homoglyphs.confusables.is_dangerous)
        and equals a known domain after mapping confusables to ASCII.
    Exact matches are NOT look-alikes.
    """
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")


def claims_to_be_bank(display_name: str, domain: str) -> bool:
    """True if the SENDER claims to be a bank: a BANK_CLAIM_WORDS word appears as a whole token
    in the display name (split on non-letters) or in a domain label (split on '.' and '-').
    Case-insensitive. The subject is NOT used ("updated bank details" from a vendor is normal).
    Examples: ("Fictional Bank A Alerts", "x.example") -> True;
              ("Narmada Accounts", "narmada-logistics.example") -> False;
              ("Alerts", "fictional-bank-a-secure.example") -> True;
              ("Riverbank Foods", "riverbank-foods.example") -> False (no whole-token match)."""
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")


def is_bank_in(domain: str) -> bool:
    """True if domain is 'bank.in' or ends with '.bank.in'."""
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")


def is_freemail(domain: str) -> bool:
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")
