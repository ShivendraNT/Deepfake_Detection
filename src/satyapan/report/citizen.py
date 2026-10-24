"""Golden-hour pack for a person whose money has already left (finale, citizen page).

The same UTR-first idea as the business pack (pack.py), from the facts the person types in:
a 1930 call script whose first line is the UTR, a message for the bank's fraud line, the
fields the cybercrime.gov.in "financial fraud" form asks for, and the next steps in order.
Drafts only (`submission = "MANUAL_ONLY"`): there is no public 1930/NCRP API and this module
imports no network library (tests/invariants/test_no_auto_reporting.py).
"""

from __future__ import annotations

from satyapan.citizen.rules import LINKS
from satyapan.contracts.enums import Lang
from satyapan.contracts.report import CitizenReportDraft, EmailDraft, NcrpField, TransactionFacts
from satyapan.report.pack import _fmt_when, _payee_line, format_inr

SUBCATEGORY = {
    "UPI": "UPI related fraud",
    "IMPS": "Internet banking related fraud",
    "NEFT": "Internet banking related fraud",
    "RTGS": "Internet banking related fraud",
    "CARD": "Debit / credit card fraud",
    "WALLET": "E-wallet related fraud",
}

STEPS = {
    Lang.EN: [
        "Call 1930 now and read the script below, UTR first. The sooner you call, the more "
        "money can still be frozen.",
        "Call your bank's 24x7 number from the back of your card or its official app (never a "
        "number from the message) and ask them to block your card/UPI and dispute this "
        "transaction.",
        "File on cybercrime.gov.in > Report financial fraud with the fields below, within 24 "
        "hours even if you already called 1930. Write down the acknowledgement number.",
        "Keep the screenshots, the caller's number and the chat. Do not delete anything.",
        "Report the number or message on Sanchar Saathi (Chakshu) so it can be blocked.",
        "Never pay anyone who promises to recover the money for a fee.",
    ],
    Lang.HI: [
        "अभी 1930 पर कॉल कीजिए और नीचे लिखी बात पढ़िए, सबसे पहले UTR। जितनी जल्दी कॉल करेंगे, "
        "उतना ज़्यादा पैसा रोका जा सकता है।",
        "अपने बैंक का 24x7 नंबर कार्ड के पीछे या बैंक के आधिकारिक ऐप से लीजिए (संदेश वाला नंबर कभी "
        "नहीं) और कार्ड/UPI बंद करवाकर यह लेन-देन विवादित दर्ज कराइए।",
        "24 घंटे के अंदर cybercrime.gov.in पर 'Report financial fraud' में नीचे की जानकारी भरिए, "
        "चाहे 1930 पर कॉल कर चुके हों। पावती नंबर लिख लीजिए।",
        "स्क्रीनशॉट, कॉल करने वाले का नंबर और चैट सँभालकर रखिए। कुछ भी डिलीट मत कीजिए।",
        "संचार साथी (चक्षु) पर नंबर या संदेश की शिकायत कीजिए ताकि उसे बंद किया जा सके।",
        "पैसा 'वापस दिलाने' के नाम पर फ़ीस माँगने वाले को कभी पैसे मत दीजिए।",
    ],
}


def build_citizen_pack(
    facts: TransactionFacts,
    *,
    your_bank: str = "",
    scammer_phone: str = "",
    story: str = "",
    lang: Lang = Lang.EN,
) -> CitizenReportDraft:
    """Drafts from what the person typed; nothing is stored or sent."""
    if not facts.utr:
        raise ValueError("the UTR / transaction ID is what freezes money; add it first")
    if facts.amount_inr <= 0:
        raise ValueError("amount must be a positive number of rupees")
    when = _fmt_when(facts.sent_at, "the time shown in my bank app")
    bank = your_bank.strip() or "my bank"
    payee = _payee_line(facts)
    acct = f" account {facts.debit_account_masked}" if facts.debit_account_masked else ""
    script = [
        f"UTR {facts.utr}: I want to report a financial cyber fraud. Amount "
        f"{format_inr(facts.amount_inr)} sent by {facts.rail} on {when} from my {bank}{acct} "
        f"to {payee}.",
    ]
    if scammer_phone.strip():
        script.append(f"The fraudster contacted me from {scammer_phone.strip()}.")
    if story.strip():
        script.append(f"What happened: {story.strip()}")
    script.append(
        "Please freeze the receiving account and help me get the money back. I have the "
        "screenshots and the transaction receipt."
    )
    bank_msg = EmailDraft(
        to_hint=f"{bank} fraud / customer care (number on your card or the official app)",
        subject=f"URGENT: fraud, UTR {facts.utr}, {format_inr(facts.amount_inr)}",
        body=(
            f"I did not authorise this payment willingly; I was cheated. UTR {facts.utr}, "
            f"{format_inr(facts.amount_inr)} by {facts.rail} on {when} to {payee}. Please "
            "block my card / UPI on this account, raise a dispute for this transaction and "
            "ask the receiving bank to hold the money. I am reporting it on 1930 and "
            "cybercrime.gov.in."
        ),
    )
    fields = [
        ("Category", "Online financial fraud"),
        ("Sub-category", SUBCATEGORY.get(facts.rail, "Other financial fraud")),
        ("Your bank / wallet", bank),
        ("Transaction ID / UTR", facts.utr),
        ("Amount", format_inr(facts.amount_inr)),
        ("Date and time", when),
        ("Money went to (UPI ID / account / IFSC)", payee),
        ("Fraudster's phone number", scammer_phone.strip() or "-"),
        ("What happened", story.strip() or "-"),
    ]
    return CitizenReportDraft(
        facts=facts,
        call_script_1930="\n".join(script),
        bank_message=bank_msg,
        ncrp_draft=[NcrpField(label=k, value=v) for k, v in fields],
        steps=STEPS[lang],
        links=dict(LINKS),
    )
