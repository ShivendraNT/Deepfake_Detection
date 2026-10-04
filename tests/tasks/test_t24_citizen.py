"""T24 acceptance (stretch): citizen Scam Check — coarse output only."""

from __future__ import annotations

import json
import re

import pytest

from satyapan.citizen.rules import scam_check
from satyapan.contracts import Band, Lang
from tests.helpers import api_ok

pytestmark = pytest.mark.task("T24")


@pytest.mark.parametrize(
    ("text", "band"),
    [
        ("CBI officer on WhatsApp video call says I am under digital arrest", Band.HOLD),
        ("Please share the OTP you received", Band.HOLD),
        ("RBI says move your savings to a safe account", Band.HOLD),
        ("Keep this confidential and send money to the new account", Band.VERIFY),
        ("Your order has shipped", Band.PASS),
    ],
)
def test_bands(text: str, band: Band) -> None:
    assert scam_check(text, Lang.EN).band == band


def test_no_scores_ever() -> None:
    out = scam_check("share OTP", Lang.EN).model_dump(mode="json")
    assert "score" not in json.dumps(out).lower()


def test_links_and_hindi() -> None:
    r = scam_check("ओटीपी बताइए", Lang.HI)
    assert r.links["call_1930"] == "tel:1930" and r.links["share"].startswith(
        "https://wa.me/?text="
    )
    assert re.search(r"[ऀ-ॿ]", r.action_text)


def test_api(client) -> None:
    r = api_ok(client.post("/scam-check", json={"text": "share otp", "lang": "en"}), "T24")
    assert r.status_code == 200 and r.json()["band"] == "HOLD"
