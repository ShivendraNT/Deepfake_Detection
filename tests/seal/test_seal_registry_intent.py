"""Seal Registry (passkey-started sessions, TESLA disclosure) and Intent Seal (py_webauthn)."""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

from satyapan.contracts import SealSessionKind
from satyapan.seal import intent as it
from satyapan.seal import tesla
from satyapan.seal.registry import (
    RegistryError,
    SealRegistry,
    seal_start_challenge,
    seal_start_statement,
)
from satyapan.seal.softauth import SoftAuthenticator
from satyapan.seal.voiceseal import DEFAULT_PARAMS
from tests.seal.seal_fixtures import MEETING, NOW, RP, enrol_more, enrolled

T0_MS = int(NOW.timestamp() * 1000)


def _start(
    reg: SealRegistry,
    auth: SoftAuthenticator,
    *,
    employee: str = "emp_rajesh",
    meeting: str = MEETING,
    kind: SealSessionKind = SealSessionKind.MEETING,
    seed: bytes = b"s1",
    t0_ms: int = T0_MS,
    sign_meeting: str | None = None,
):  # type: ignore[no-untyped-def]
    commitment, keys = tesla.make_chain(seed, 100)
    from satyapan.seal.registry import binding_for

    stmt = seal_start_statement(
        employee_id=employee,
        kind=kind,
        binding=binding_for(kind, sign_meeting or meeting),
        commitment_hex=commitment.hex(),
        t0_ms=t0_ms,
        epoch_ms=5000,
        n_epochs=100,
        params_id=DEFAULT_PARAMS.params_id,
    )
    assertion = auth.get(seal_start_challenge(stmt))
    s = reg.start_session(
        employee_id=employee,
        kind=kind,
        meeting=meeting,
        commitment_hex=commitment.hex(),
        t0_ms=t0_ms,
        epoch_ms=5000,
        n_epochs=100,
        params_id=DEFAULT_PARAMS.params_id,
        assertion=assertion,
        now=NOW,
    )
    return s, keys


def test_session_start_and_disclosure() -> None:
    store, auth = enrolled()
    reg = SealRegistry(passkeys=store)
    s, keys = _start(reg, auth)
    assert s.binding == "meet:abc-defg-hij" and s.employee_id == "emp_rajesh"
    later = NOW + timedelta(seconds=26)  # epochs 0-4 have ended
    with pytest.raises(RegistryError, match="epoch_not_ended"):
        reg.disclose(s.id, 5, keys[5].hex(), later)
    with pytest.raises(RegistryError, match="key_mismatch"):
        reg.disclose(s.id, 4, os.urandom(32).hex(), later)
    v = reg.disclose(s.id, 4, keys[4].hex(), later)
    assert v.last_disclosed_epoch == 4
    assert reg.keys(s.id) == {e: keys[e] for e in range(5)}  # earlier keys derived
    assert reg.disclose(s.id, 2, keys[2].hex(), later).last_disclosed_epoch == 4  # idempotent
    with pytest.raises(RegistryError, match="key_mismatch"):
        reg.disclose(s.id, 2, keys[3].hex(), later)
    v = reg.disclose(s.id, 9, keys[9].hex(), NOW + timedelta(seconds=50))  # incremental check
    assert v.last_disclosed_epoch == 9
    view = reg.meeting("abc-defg-hij")
    assert len(view) == 1 and [k.epoch for k in view[0].keys] == list(range(10))


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"sign_meeting": "https://meet.google.com/xyz-uvwq-rst"}, "passkey_rejected"),
        ({"t0_ms": T0_MS - 10 * 60 * 1000}, "stale_start"),
    ],
)
def test_session_start_rejections(change: dict[str, object], reason: str) -> None:
    store, auth = enrolled()
    reg = SealRegistry(passkeys=store)
    with pytest.raises(RegistryError, match=reason):
        _start(reg, auth, **change)  # type: ignore[arg-type]


def test_replayed_commitment_and_wrong_person() -> None:
    store, auth = enrolled()
    meera = enrol_more(store, "emp_meera")
    reg = SealRegistry(passkeys=store)
    _start(reg, auth, seed=b"same")
    with pytest.raises(RegistryError, match="replayed_commitment"):
        _start(reg, auth, seed=b"same")
    with pytest.raises(RegistryError, match="passkey_rejected"):  # Meera's key, Rajesh's name
        _start(reg, meera, seed=b"other")
    with pytest.raises(RegistryError, match="passkey_rejected"):  # not enrolled at all
        _start(reg, SoftAuthenticator(), employee="emp_sunil", seed=b"third")


def test_voice_note_keys_are_not_published_and_presence() -> None:
    store, auth = enrolled()
    reg = SealRegistry(passkeys=store)
    note, nkeys = _start(reg, auth, kind=SealSessionKind.VOICE_NOTE, meeting="VN-1", seed=b"n")
    assert note.binding == "note:VN-1"
    meet, mkeys = _start(reg, auth, seed=b"m")
    t = NOW + timedelta(seconds=11)
    reg.disclose(note.id, 1, nkeys[1].hex(), t)
    reg.disclose(meet.id, 1, mkeys[1].hex(), t)
    assert all(v.session.kind == SealSessionKind.MEETING for v in reg.meeting(MEETING))
    assert reg.meeting("note:VN-1") == []
    assert [s.id for s in reg.live_elsewhere("emp_rajesh", "meet:xyz-uvwq-rst", t)] == [meet.id]
    assert reg.live_elsewhere("emp_rajesh", meet.binding, t) == []
    assert reg.live_elsewhere("emp_rajesh", "meet:xyz-uvwq-rst", t + timedelta(minutes=2)) == []


# ------------------------------------------------------------------ Intent Seal


def _intent(**kw: object) -> it.PaymentIntent:
    args: dict[str, object] = {
        "case_id": "case_s06",
        "requester": "emp_rajesh",
        "amount_inr": 4_850_000,
        "account_number": "99998888004821",
        "ifsc": "FAKM0000482",
        "now": NOW,
    }
    args.update(kw)
    return it.make_intent(**args)  # type: ignore[arg-type]


def test_intent_display_and_canonical_challenge() -> None:
    i = _intent(nonce="n" * 24)
    assert it.display_text(i) == "Approve ₹48,50,000 to A/c ••••4821 (FAKM0000482) for case_s06?"
    assert it.intent_challenge(i) == it.intent_challenge(_intent(nonce="n" * 24))
    assert it.format_inr(999) == "₹999" and it.format_inr(1_00_00_000) == "₹1,00,00,000"
    assert it.matches_payment(i, 4_850_000, "99998888004821")
    assert not it.matches_payment(i, 48_500_000, "99998888004821")


def test_intent_genuine_and_attacks() -> None:
    store, auth = enrolled()
    svc = it.IntentService(passkeys=store)
    i = _intent()
    issued = svc.issue(i)
    assert issued["display_text"].startswith("Approve ₹48,50,000")
    assert issued["request_options"]["challenge"]  # base64url of SHA-256(intent)
    a = auth.get(it.intent_challenge(i))

    def reason(presented: it.PaymentIntent, assertion: dict[str, object]) -> str:
        with pytest.raises(it.IntentError) as e:
            svc.verify(presented, assertion, NOW)
        return e.value.reason

    tampered = i.model_copy(update={"amount_inr": 48_500_000})
    assert reason(tampered, a) == "signature_rejected"
    swapped = i.model_copy(
        update={
            "beneficiary": i.beneficiary.model_copy(
                update={"account_sha256": it.account_sha256("99997777000099")}
            )
        }
    )
    assert reason(swapped, a) == "signature_rejected"
    phish = auth.get(it.intent_challenge(i), origin="https://satyapan-login.example")
    assert reason(i, phish) == "signature_rejected"
    mallory = SoftAuthenticator(rp_id=RP.rp_id, origin="http://localhost:5173")
    mallory.cred_id, mallory.count = auth.cred_id, 10_000  # claims Rajesh's credential id
    assert reason(i, mallory.get(it.intent_challenge(i))) == "signature_rejected"
    assert reason(i.model_copy(update={"requester": "emp_sunil"}), a) == "wrong_requester"
    ok = svc.verify(i, a, NOW)  # the genuine approval still works after all the failures
    assert ok.intent.amount_inr == 4_850_000
    assert reason(i, a) == "replay"
    late = _intent()
    svc.issue(late)
    with pytest.raises(it.IntentError, match="expired"):
        svc.verify(late, auth.get(it.intent_challenge(late)), NOW + timedelta(hours=1))
    with pytest.raises(it.IntentError, match="unknown_nonce"):
        svc.verify(_intent(), a, NOW)
