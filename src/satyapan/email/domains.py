"""Domain checks (look-alike, .bank.in, free-mail). TASK T04 — see docs/tasks/T04-domain-checks.md.

Pure functions, no network, no DNS lookups.
"""

from __future__ import annotations

import re

from confusable_homoglyphs import confusables

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
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                prev[j] + 1,  # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = curr
    return prev[len(b)]


def normalise_domain(domain: str) -> str:
    """Lower-case, strip a trailing dot, decode IDNA/punycode ("xn--...") to Unicode."""
    d = domain.strip().lower().rstrip(".")
    labels = d.split(".")
    norm_labels: list[str] = []
    for label in labels:
        if label.startswith("xn--"):
            try:
                norm_labels.append(label.encode("ascii").decode("idna"))
            except (UnicodeError, ValueError):
                norm_labels.append(label)
        else:
            norm_labels.append(label)
    return ".".join(norm_labels)


def is_lookalike(domain: str, known_domains: set[str], max_distance: int = 2) -> str | None:
    """Return the known domain this one imitates, or None.

    A look-alike is a domain that is NOT exactly a known domain but
    (a) has edit distance <= max_distance to a known domain, or
    (b) contains Unicode confusables (use confusable_homoglyphs.confusables.is_dangerous)
        and equals a known domain after mapping confusables to ASCII.
    Exact matches are NOT look-alikes.
    """
    norm = normalise_domain(domain)
    known_norm = {normalise_domain(k): k for k in known_domains}

    # Exact matches are NOT look-alikes
    if norm in known_norm:
        return None

    # Check for Unicode confusables (e.g. Cyrillic 'а' imitating ASCII 'a')
    try:
        confusable_items = confusables.is_confusable(norm, preferred_aliases=["latin"])
    except Exception:
        confusable_items = None

    if confusable_items:
        ascii_candidate = norm
        for item in confusable_items:
            for h in item.get("homoglyphs", []):
                char = h.get("c", "")
                if char.isascii():
                    ascii_candidate = ascii_candidate.replace(item["character"], char)
                    break
        if ascii_candidate in known_norm:
            return known_norm[ascii_candidate]

    # Check edit distance <= max_distance against known domains
    for k_norm in sorted(known_norm.keys()):
        if levenshtein(norm, k_norm) <= max_distance:
            return known_norm[k_norm]

    return None


def claims_to_be_bank(display_name: str, domain: str) -> bool:
    """True if the SENDER claims to be a bank: a BANK_CLAIM_WORDS word appears as a whole token
    in the display name (split on non-letters) or in a domain label (split on '.' and '-').
    Case-insensitive. The subject is NOT used ("updated bank details" from a vendor is normal).
    Examples: ("Fictional Bank A Alerts", "x.example") -> True;
              ("Narmada Accounts", "narmada-logistics.example") -> False;
              ("Alerts", "fictional-bank-a-secure.example") -> True;
              ("Riverbank Foods", "riverbank-foods.example") -> False (no whole-token match)."""
    d_name = display_name.lower().strip()
    if "reserve bank" in d_name:
        return True

    single_bank_words = {"bank", "banking", "rbi", "nbfc", "बैंक"}

    # Display name tokens: split on non-letters / non-devanagari
    name_tokens = {tok for tok in re.split(r"[^\w\u0900-\u097F]+", d_name) if tok}
    if name_tokens & single_bank_words:
        return True

    # Domain tokens: split on '.' and '-'
    dom = domain.lower().strip()
    dom_tokens = {tok for part in dom.split(".") for tok in part.split("-") if tok}
    return bool(dom_tokens & single_bank_words)


def is_bank_in(domain: str) -> bool:
    """True if domain is 'bank.in' or ends with '.bank.in'."""
    norm = normalise_domain(domain)
    return norm == "bank.in" or norm.endswith(".bank.in")


def is_freemail(domain: str) -> bool:
    norm = normalise_domain(domain)
    return norm in FREEMAIL_DOMAINS
