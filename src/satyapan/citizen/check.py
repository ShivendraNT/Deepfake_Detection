"""Citizen Scam Check for anything a person forwards: text, screenshot, voice note, photo,
video, e-mail or PDF (finale, consumer journey).

The file goes through the quick check (every detector on this device, band from the policy
engine, nothing kept); any text it contains (the message, what the voice note said, what the
screenshot reads) also goes through the T24 "impossible claim" rules, and the band is the
higher of the two (raise-only). The answer is coarse on purpose: band, what to do, why, and
what could not be checked here. Never a score.
"""

from __future__ import annotations

import re
from typing import Any

from satyapan.citizen.rules import ACTION_TEXT, IMPOSSIBLE_CLAIMS, LINKS, scam_check, share_link
from satyapan.contracts.enums import Band, Channel, Lang, ReasonCode
from satyapan.contracts.explain import CitizenFileResult
from satyapan.policy.bands import rank

CHECKED = {
    "voice": {Lang.EN: "the voice (cloned or real)", Lang.HI: "आवाज़ (नकली/क्लोन या असली)"},
    "face": {Lang.EN: "the face (swapped or real)", Lang.HI: "चेहरा (बदला हुआ या असली)"},
    "text": {Lang.EN: "the wording (known scam patterns)", Lang.HI: "शब्द (जाने-पहचाने ठगी पैटर्न)"},
    "asks": {Lang.EN: "what it asks you to do", Lang.HI: "यह आपसे क्या करवाना चाहता है"},
}
MAX_BYTES = 40 * 1024 * 1024
R = ReasonCode
# The same findings in a person's words (the shared templates speak to a finance team:
# "the vendor", "your checker"). Codes not listed keep the shared text.
PERSONAL_WHY: dict[ReasonCode, dict[Lang, str]] = {
    R.ASK_NEW_ACCOUNT: {
        Lang.EN: "It asks you to send money to a new or 'safe' account. Don't pay; call the "
        "person or bank back on a number you already have.",
        Lang.HI: "यह आपसे किसी नए या 'सुरक्षित' खाते में पैसे भेजने को कहता है। पैसे मत भेजिए; "
        "अपने पास पहले से मौजूद नंबर पर उस व्यक्ति या बैंक को वापस कॉल कीजिए।",
    },
    R.ASK_CREDENTIAL: {
        Lang.EN: "Somebody asked for an OTP, PIN, password or card detail. Never share one with "
        "anyone, not even someone who says they are from the bank.",
        Lang.HI: "किसी ने ओटीपी, पिन, पासवर्ड या कार्ड की जानकारी माँगी। यह किसी को मत दीजिए, बैंक "
        "वाला बनकर बात करने वाले को भी नहीं।",
    },
    R.ASK_REMOTE_ACCESS: {
        Lang.EN: "It asks you to install a screen-sharing app (AnyDesk, TeamViewer, "
        "QuickSupport). Don't install it; hang up.",
        Lang.HI: "यह आपसे स्क्रीन-शेयरिंग ऐप (AnyDesk, TeamViewer, QuickSupport) डालने को कहता है। "
        "उसे मत डालिए; कॉल काट दीजिए।",
    },
    R.ASK_SECRECY: {
        Lang.EN: "It tells you to keep this secret from family or friends. Scammers cut you off "
        "from help; tell someone you trust before you act.",
        Lang.HI: "यह आपसे परिवार या दोस्तों से बात छिपाने को कहता है। ठग आपको अकेला करते हैं; कुछ "
        "करने से पहले किसी भरोसेमंद व्यक्ति को बताइए।",
    },
    R.ASK_BYPASS: {
        Lang.EN: "It asks you to skip the usual checks. A genuine request can wait for a "
        "call-back.",
        Lang.HI: "यह आपसे सामान्य जाँच छोड़ने को कहता है। असली काम एक वापसी कॉल तक रुक सकता है।",
    },
    R.ASK_UNUSUAL_PAYMENT_METHOD: {
        Lang.EN: "It asks for payment by gift card, crypto or a UPI collect request. Genuine "
        "offices never ask for these; don't pay.",
        Lang.HI: "यह गिफ़्ट कार्ड, क्रिप्टो या UPI कलेक्ट रिक्वेस्ट से भुगतान माँगता है। असली दफ़्तर "
        "ऐसा कभी नहीं माँगते; पैसे मत भेजिए।",
    },
    R.ASK_PAYEE_CHANGE: {
        Lang.EN: "It asks you to pay different bank details than usual. Confirm on a number you "
        "already have before paying.",
        Lang.HI: "यह आपसे हमेशा से अलग बैंक खाते में पैसे भेजने को कहता है। भेजने से पहले अपने पास "
        "मौजूद नंबर पर पक्का कीजिए।",
    },
    R.STYLE_PRESSURE: {
        Lang.EN: "The wording pushes urgency, threats or secrecy, a common scam tactic. Slow down.",
        Lang.HI: "शब्दों में जल्दबाज़ी, धमकी या गोपनीयता का दबाव है, जो ठगी का आम तरीका है। रुकिए।",
    },
    R.TEXT_SCAM_LIKELY: {
        Lang.EN: "This reads like known scam messages (a trained model, not proof). Check with the "
        "sender on a number you already have.",
        Lang.HI: "यह जाने-पहचाने ठगी संदेशों जैसा लगता है (एक प्रशिक्षित मॉडल, सबूत नहीं)। अपने पास "
        "मौजूद नंबर पर भेजने वाले से पक्का कीजिए।",
    },
    R.VOICE_LIKELY_SYNTHETIC: {
        Lang.EN: "The voice shows signs of being AI-cloned. Don't act on it; call the person back "
        "on a number you already have.",
        Lang.HI: "इस आवाज़ में AI से नकल किए जाने के संकेत हैं। इस पर कार्रवाई मत कीजिए; अपने पास "
        "मौजूद नंबर पर उस व्यक्ति को वापस कॉल कीजिए।",
    },
    R.VIDEO_LIKELY_SYNTHETIC: {
        Lang.EN: "The face in the video shows signs of being swapped or AI-made. Don't trust it; "
        "call the person back on a number you already have.",
        Lang.HI: "वीडियो के चेहरे में बदले जाने या AI से बने होने के संकेत हैं। भरोसा मत कीजिए; अपने "
        "पास मौजूद नंबर पर उस व्यक्ति को वापस कॉल कीजिए।",
    },
    R.VIDEO_SUSPICIOUS: {
        Lang.EN: "The face in the video looked unusual to the face check (not sure enough to "
        "call it fake). Call the person back on a number you already have before acting.",
        Lang.HI: "चेहरे की जाँच को वीडियो का चेहरा असामान्य लगा (नकली कहने लायक पक्का नहीं)। कुछ "
        "करने से पहले अपने पास मौजूद नंबर पर वापस कॉल कीजिए।",
    },
    R.IMAGE_FACE_LIKELY_SYNTHETIC: {
        Lang.EN: "The face in this photo shows signs of being swapped or AI-made. A photo is "
        "not proof of who someone is.",
        Lang.HI: "इस फ़ोटो के चेहरे में बदले जाने या AI से बने होने के संकेत हैं। फ़ोटो किसी की पहचान का सबूत नहीं है।",
    },
    R.IMAGE_FACE_INCONCLUSIVE: {
        Lang.EN: "Satya could not check the face in this photo (no face, or too small). Treat "
        "it as unchecked.",
        Lang.HI: "सत्य इस फ़ोटो का चेहरा नहीं जाँच सका (चेहरा नहीं है या बहुत छोटा है)। इसे बिना जाँचा मानिए।",
    },
    R.VOICE_NO_SIGNS: {
        Lang.EN: "The voice check found no signs of a cloned voice (not proof it is genuine).",
        Lang.HI: "आवाज़ की जाँच में नकल की गई आवाज़ के संकेत नहीं मिले (यह असली होने का सबूत नहीं है)।",
    },
    R.VIDEO_NO_SIGNS: {
        Lang.EN: "The face check found no signs of a swapped face (not proof of who it is).",
        Lang.HI: "चेहरे की जाँच में बदले हुए चेहरे के संकेत नहीं मिले (यह पहचान का सबूत नहीं है)।",
    },
    R.IMAGE_FACE_NO_SIGNS: {
        Lang.EN: "The face check found no signs of a swapped or AI-made face (a photo still "
        "proves nothing about who sent it).",
        Lang.HI: "चेहरे की जाँच में बदले हुए या AI से बने चेहरे के संकेत नहीं मिले (फ़ोटो फिर भी "
        "यह साबित नहीं करती कि भेजा किसने)।",
    },
    R.MULTI_GROUP_STRONG: {
        Lang.EN: "Several different warning signs at once.",
        Lang.HI: "एक साथ कई अलग-अलग चेतावनी संकेत।",
    },
    R.GREY_FLAG: {
        Lang.EN: "Part of this file could not be read, so the check is incomplete. Treat it "
        "with care.",
        Lang.HI: "इस फ़ाइल का कुछ हिस्सा पढ़ा नहीं जा सका, इसलिए जाँच अधूरी है। सावधानी रखिए।",
    },
}


def personal_why(code: ReasonCode, lang: Lang, fallback: str) -> str:
    return PERSONAL_WHY.get(code, {}).get(lang, fallback)


def citizen_check(
    state: Any, data: bytes, filename: str | None, media_type: str, lang: Lang = Lang.EN
) -> CitizenFileResult:
    from satyapan.quickcheck import quick_check

    if len(data) > MAX_BYTES:
        raise ValueError("file too large for a quick check (40 MB max)")
    r = quick_check(state, data, filename, media_type, lang)
    words = r.transcript or (
        data.decode("utf-8", errors="replace") if r.channel == Channel.MANUAL else ""
    )
    band, why, hits = r.band, [], []
    if words.strip():
        rules = scam_check(words, lang)
        hits = rules.rule_hits
        if rank(rules.band) > rank(band):
            band = rules.band
        why += [
            (en if lang == Lang.EN else hi)
            for rule_id, _pat, en, hi in IMPOSSIBLE_CLAIMS
            if rule_id in hits
        ]
    why += [
        personal_why(code, lang, text)
        for code, text in zip(r.reason_codes + r.info_codes, r.why, strict=True)
    ]
    action = ACTION_TEXT[lang][band]
    links = dict(LINKS)
    links["share"] = share_link(band, lang)
    # "not_analysed" means the model is missing: it is listed under not_checked, never here.
    checked = [
        CHECKED[k][lang]
        for k in ("voice", "face", "text", "asks")
        if r.findings.get(k, "not_analysed") != "not_analysed"
    ]
    return CitizenFileResult(
        band=band,
        action_text=action,
        rule_hits=hits,
        links=links,
        why=list(dict.fromkeys(why))[:6],
        checked=checked,
        not_checked=r.not_checked,
        heard_or_read=_tidy(words) if r.channel != Channel.MANUAL and words else None,
        seconds=r.seconds,
    )


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:600]


__all__ = ["Band", "citizen_check"]
