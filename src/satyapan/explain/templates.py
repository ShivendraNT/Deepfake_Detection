"""Reason-code explanation templates in English and Hindi. TASK T14.

See docs/tasks/T14-explanation-templates.md. Templates are AUTHORITATIVE: the LLM summary is
optional prose on top and falls back to these. Every ReasonCode needs EN and HI text.
Hindi text must be in Devanagari. Keep each text to one or two plain sentences that tell
the maker WHAT HAPPENED and WHAT TO DO. Never say "safe", "verified", "genuine".
"""

from __future__ import annotations

from satyapan.contracts.case import Decision
from satyapan.contracts.enums import Lang, ReasonCode
from satyapan.contracts.explain import Explanation

# Fill this for EVERY ReasonCode. Two examples are given.
REASON_TEXT: dict[ReasonCode, dict[Lang, str]] = {
    # --- floor (transaction vs vendor master) ---
    ReasonCode.FLOOR_K1_KNOWN_IN_PATTERN: {
        Lang.EN: "The beneficiary and bank details match the vendor master, and the amount is "
        "inside this vendor's usual pattern. Continue with the normal payment flow and still "
        "review the evidence attached here.",
        Lang.HI: "लाभार्थी और बैंक विवरण वेंडर मास्टर से मेल खाते हैं और राशि इस वेंडर की सामान्य "
        "रेंज में है। सामान्य भुगतान प्रक्रिया जारी रखें और इस केस से जुड़े सबूत भी देखें।",
    },
    ReasonCode.FLOOR_K2_OUT_OF_PATTERN: {
        Lang.EN: "The beneficiary is in the vendor master, but the amount is above this vendor's "
        "usual payments or the last payment was over 180 days ago. Call the vendor on the number "
        "on file before paying.",
        Lang.HI: "लाभार्थी वेंडर मास्टर में है, लेकिन राशि इस वेंडर के सामान्य भुगतान से अधिक है "
        "या पिछले भुगतान को 180 दिन से ज़्यादा समय हो चुका है। भुगतान से पहले दर्ज नंबर पर वेंडर "
        "को कॉल करें।",
    },
    ReasonCode.FLOOR_N1_NEW_SMALL: {
        Lang.EN: "This is a new beneficiary and the amount is within the small-payment limit. Pay "
        "through the normal flow; the bank's own new-payee checks still apply.",
        Lang.HI: "यह नया लाभार्थी है और राशि छोटे भुगतान की सीमा के भीतर है। सामान्य प्रक्रिया से "
        "भुगतान करें; बैंक अपनी नए लाभार्थी वाली जाँच फिर भी करेगा।",
    },
    ReasonCode.FLOOR_N2_NEW_LARGE: {
        Lang.EN: "This is a new beneficiary and the amount is above the small-payment limit. "
        "Confirm the request with the requester through OOB-Confirm or a callback on the number "
        "on file before paying.",
        Lang.HI: "यह नया लाभार्थी है और राशि छोटे भुगतान की सीमा से ऊपर है। भुगतान से पहले "
        "अनुरोधकर्ता से OOB-Confirm या दर्ज नंबर पर कॉल-बैक के ज़रिए पुष्टि करें।",
    },
    ReasonCode.FLOOR_C1_BANK_CHANGED: {
        Lang.EN: "The bank account differs from the vendor master. Call the vendor back on the "
        "number already on file (not the one in the message) before paying.",
        Lang.HI: "बैंक खाता वेंडर मास्टर से अलग है। भुगतान से पहले वेंडर को पहले से दर्ज नंबर पर "
        "फिर से कॉल करें (संदेश वाले नंबर पर नहीं)।",
    },
    ReasonCode.FLOOR_T1_TRUST_ANCHOR: {
        Lang.EN: "Someone asked to change a phone number, email address or approver that we keep "
        "on file. Nothing changes until the checker confirms it on the old channel and a second "
        "approver agrees.",
        Lang.HI: "किसी ने हमारे रिकॉर्ड में दर्ज फ़ोन नंबर, ईमेल या मंज़ूरी देने वाले को बदलने के "
        "लिए कहा है। जब तक चेकर पुराने चैनल पर पुष्टि नहीं कर लेता और दूसरी मंज़ूरी नहीं मिल जाती, "
        "कुछ न बदलें।",
    },
    ReasonCode.FLOOR_D1_DATA_REQUEST: {
        Lang.EN: "The request is for data or login details rather than a payment. Do not send "
        "anything from this message; take it to the owner of that data through your normal "
        "channel.",
        Lang.HI: "यह अनुरोध भुगतान का नहीं, बल्कि डेटा या लॉगिन जानकारी का है। इस संदेश से कुछ भी "
        "न भेजें; इसे सामान्य चैनल से उस डेटा के मालिक तक पहुँचाएँ।",
    },
    ReasonCode.FLOOR_NONE: {
        Lang.EN: "There is no pending payment on this case yet. If a payment request comes up "
        "during the call, enter it in Satyapan and check the band before acting.",
        Lang.HI: "इस केस पर अभी कोई भुगतान लंबित नहीं है। कॉल के दौरान भुगतान का अनुरोध आए तो उसे "
        "Satyapan में दर्ज करें और कार्रवाई से पहले स्तर देखें।",
    },
    # --- email / sender auth ---
    ReasonCode.EMAIL_AUTH_PASS: {
        Lang.EN: "SPF, DKIM and DMARC checks all passed for the sender's domain. Keep working "
        "through the other checks on this case; on its own this does not settle the payment.",
        Lang.HI: "भेजने वाले के डोमेन की SPF, DKIM और DMARC तीनों जाँचें पास हो गईं। इस केस की "
        "बाकी जाँच जारी रखें; अकेले इस नतीजे से भुगतान तय नहीं होता।",
    },
    ReasonCode.EMAIL_DMARC_FAIL: {
        Lang.EN: "The email failed the sender's DMARC check, so the sending domain did not vouch "
        "for it. Do not use links, attachments or bank details from it; confirm the request on "
        "the number on file.",
        Lang.HI: "ईमेल की DMARC जाँच फेल हुई, यानी भेजने वाले डोमेन ने इसकी पुष्टि नहीं की। इसके "
        "लिंक, अटैचमेंट या बैंक विवरण इस्तेमाल न करें; दर्ज नंबर पर पुष्टि करें।",
    },
    ReasonCode.EMAIL_LOOKALIKE_DOMAIN: {
        Lang.EN: "The sender's domain is not in the vendor master and looks like a near-copy of a "
        "domain we know. Do not reply to it; call the vendor on the number on file and forward "
        "the email to security.",
        Lang.HI: "भेजने वाले का डोमेन वेंडर मास्टर में नहीं है और जाने-पहचाने डोमेन जैसा दिखता है। "
        "इसका जवाब न दें; दर्ज नंबर पर वेंडर को कॉल करें और यह ईमेल सुरक्षा टीम को आगे भेजें।",
    },
    ReasonCode.EMAIL_BANK_NOT_BANK_IN: {
        Lang.EN: "The message claims to come from a bank, but not from the bank's own domain. Do "
        "not use any link, number or QR code inside it; call your bank on the number already on "
        "file.",
        Lang.HI: "संदेश बैंक का लगता है, लेकिन वह बैंक के अपने डोमेन से नहीं आया। इसमें दिए गए "
        "किसी भी लिंक, नंबर या QR code का इस्तेमाल न करें; अपने बैंक को दर्ज नंबर पर कॉल करें।",
    },
    ReasonCode.EMAIL_REPLYTO_MISMATCH: {
        Lang.EN: "A reply to this email would go to a different address than the sender shows. "
        "Reply in the original thread or call the person on the directory number, not the "
        "address in this message.",
        Lang.HI: "इस ईमेल का जवाब देने पर संदेश में दिखाए पते के बजाय किसी और पते पर जाएगा। मूल "
        "ईमेल पर ही जवाब दें या डायरेक्टरी के नंबर पर कॉल करें, संदेश वाले पते पर नहीं।",
    },
    ReasonCode.EMAIL_FREEMAIL_CORPORATE: {
        Lang.EN: "The sender claims to represent a company but writes from a free mail service. "
        "Confirm the request with that person on your directory number before you act on it.",
        Lang.HI: "भेजने वाला कंपनी की ओर से बात कर रहा है, लेकिन ईमेल किसी मुफ़्त ईमेल सेवा से "
        "भेजा गया है। कार्रवाई से पहले डायरेक्टरी के नंबर पर उस व्यक्ति से पुष्टि करें।",
    },
    # --- document ---
    ReasonCode.DOC_NO_ISSUES: {
        Lang.EN: "No mismatch or signs of editing were found in this invoice. Keep reviewing the "
        "other evidence on this case; one clean document does not settle the payment.",
        Lang.HI: "इस बिल में न तो कोई बेमेल मिला और न ही कोई छेड़छाड़। इस केस के बाकी सबूत भी "
        "देखें; एक ठीक-ठाक दस्तावेज़ से भुगतान तय नहीं होता।",
    },
    ReasonCode.DOC_ACCOUNT_MISMATCH: {
        Lang.EN: "The bank account printed on the invoice is not the account in the vendor "
        "master. Do not pay it; call the vendor on the number on file and ask them to reissue "
        "the invoice.",
        Lang.HI: "बिल पर छपा बैंक खाता वेंडर मास्टर के खाते से मेल नहीं खाता। इस पर भुगतान न करें; "
        "दर्ज नंबर पर वेंडर को कॉल करें और बिल दोबारा जारी करवाएँ।",
    },
    ReasonCode.DOC_PDF_EDITED: {
        Lang.EN: "The PDF's metadata shows it was edited or re-exported after it was issued. Ask "
        "the vendor to send the original again from the number on file, and hold the payment "
        "for the checker.",
        Lang.HI: "PDF के मेटाडेटा से पता चलता है कि इसे जारी होने के बाद बदला या दोबारा सेव किया "
        "गया। दर्ज नंबर पर वेंडर को कॉल करके मूल फ़ाइल दोबारा मँगवाएँ और भुगतान रोककर चेकर के पास "
        "भेजें।",
    },
    # --- voice ---
    ReasonCode.VOICE_NO_SIGNS: {
        Lang.EN: "The voice model found no signs of synthetic speech in this clip. Keep the other "
        "checks running on this case; on its own this does not clear the payment.",
        Lang.HI: "आवाज़ मॉडल को इस क्लिप में AI से बनी आवाज़ के कोई संकेत नहीं मिले। इस केस की "
        "बाकी जाँच जारी रखें; अकेले इस नतीजे से भुगतान साफ़ नहीं होता।",
    },
    ReasonCode.VOICE_INCONCLUSIVE: {
        Lang.EN: "The voice model could not decide whether this speech is human or machine-made. "
        "Treat it as undecided and confirm the request out of band before you act.",
        Lang.HI: "आवाज़ मॉडल तय नहीं कर पाया कि यह आवाज़ इंसान की है या मशीन की। इसे अनिर्णित मानें "
        "और कार्रवाई से पहले दूसरे चैनल से पुष्टि करें।",
    },
    ReasonCode.VOICE_LIKELY_SYNTHETIC: {
        Lang.EN: "The caller's voice shows signs of being AI-generated in two windows in a row. "
        "Do not act on this call; confirm through OOB-Confirm or a callback on the number on "
        "file.",
        Lang.HI: "कॉल करने वाले की आवाज़ लगातार दो हिस्सों में AI से बनी हुई लगती है। इस कॉल पर "
        "कार्रवाई न करें; OOB-Confirm या दर्ज नंबर पर कॉल-बैक के ज़रिए पुष्टि करें।",
    },
    # --- video (face) ---
    ReasonCode.VIDEO_NO_SIGNS: {
        Lang.EN: "The face check found no signs of a swapped or generated face in this video. "
        "Video can be faked in ways we cannot see; keep the other checks running and do not "
        "treat this as approval.",
        Lang.HI: "चेहरे की जाँच में इस वीडियो में बदले हुए या AI से बने चेहरे के संकेत नहीं मिले। "
        "वीडियो ऐसे भी नकली हो सकता है जो हमें न दिखे; बाकी जाँच जारी रखें और इसे मंज़ूरी न मानें।",
    },
    ReasonCode.VIDEO_INCONCLUSIVE: {
        Lang.EN: "The face check could not decide, or the face was too small, dark or hidden to "
        "check. Treat it as undecided and confirm the request out of band before you act.",
        Lang.HI: "चेहरे की जाँच तय नहीं कर पाई, या चेहरा जाँच के लिए बहुत छोटा, अँधेरे में या छिपा "
        "हुआ था। इसे अनिर्णित मानें और कार्रवाई से पहले दूसरे चैनल से पुष्टि करें।",
    },
    ReasonCode.VIDEO_LIKELY_SYNTHETIC: {
        Lang.EN: "The face on the video shows signs of being swapped or AI-generated in two "
        "windows in a row. Do not act on this call; confirm through OOB-Confirm or a callback "
        "on the number on file.",
        Lang.HI: "वीडियो में दिख रहा चेहरा लगातार दो हिस्सों में बदला हुआ या AI से बना लगता है। "
        "इस कॉल पर कार्रवाई न करें; OOB-Confirm या दर्ज नंबर पर कॉल-बैक के ज़रिए पुष्टि करें।",
    },
    # --- asks ---
    ReasonCode.ASK_NEW_ACCOUNT: {
        Lang.EN: "The message asks you to pay a new or changed bank account. Do not update the "
        "account from this message; call the vendor on the number on file first.",
        Lang.HI: "संदेश में नए या बदले हुए बैंक खाते में भुगतान करने को कहा गया है। इस संदेश से "
        "खाते की जानकारी न बदलें; पहले दर्ज नंबर पर वेंडर को कॉल करें।",
    },
    ReasonCode.ASK_CREDENTIAL: {
        Lang.EN: "Somebody asked for an OTP, PIN, password or card detail. Never share one, not "
        "even for a 'test'; report this case to security now.",
        Lang.HI: "किसी ने OTP, PIN, पासवर्ड या कार्ड की जानकारी माँगी है। इसे किसी को न बताएँ, "
        "चाहे 'टेस्ट' के नाम पर ही क्यों न पूछा जाए; अभी इस केस की सूचना सुरक्षा टीम को दें।",
    },
    ReasonCode.ASK_REMOTE_ACCESS: {
        Lang.EN: "The sender asked you to install a remote-access or screen-sharing app. Do not "
        "install it and do not share your screen; end the session and tell security.",
        Lang.HI: "भेजने वाले ने रिमोट-एक्सेस या स्क्रीन-शेयर ऐप इंस्टॉल करने को कहा है। इसे "
        "इंस्टॉल न करें और स्क्रीन साझा न करें; सत्र बंद करें और सुरक्षा टीम को बताएँ।",
    },
    ReasonCode.ASK_SECRECY: {
        Lang.EN: "The sender asked you to keep this from colleagues or your manager. Tell your "
        "checker or manager about this request before you take any action.",
        Lang.HI: "भेजने वाले ने इस बात को साथियों या अपने मैनेजर से छिपाने को कहा है। कोई कदम "
        "उठाने से पहले इस अनुरोध के बारे में चेकर या मैनेजर को बताएँ।",
    },
    ReasonCode.ASK_BYPASS: {
        Lang.EN: "The sender asked you to skip the usual approval or two-person check. Follow the "
        "normal process and send this request to the checker instead.",
        Lang.HI: "भेजने वाले ने तय मंज़ूरी या दो-व्यक्ति जाँच को छोड़ने को कहा है। सामान्य प्रक्रिया "
        "ही अपनाएँ और इस अनुरोध को चेकर के पास भेजें।",
    },
    ReasonCode.ASK_UNUSUAL_PAYMENT_METHOD: {
        Lang.EN: "The request asks for payment by gift card, crypto or a collect request instead "
        "of the usual route. Do not pay that way; confirm on the number on file.",
        Lang.HI: "अनुरोध में सामान्य रास्ते के बजाय गिफ़्ट कार्ड, क्रिप्टो या कलेक्ट रिक्वेस्ट से "
        "भुगतान माँगा गया है। इस तरह भुगतान न करें; दर्ज नंबर पर पुष्टि करें।",
    },
    ReasonCode.ASK_PAYEE_CHANGE: {
        Lang.EN: "Somebody asked to change the payee or the bank details on this payment. Do not "
        "edit them from this message; confirm on the number on file first.",
        Lang.HI: "किसी ने इस भुगतान का लाभार्थी या बैंक विवरण बदलने को कहा है। इस संदेश से बदलाव "
        "न करें; पहले दर्ज नंबर पर पुष्टि करें।",
    },
    # --- style (raise-only, capped at VERIFY) ---
    ReasonCode.STYLE_PRESSURE: {
        Lang.EN: "The wording shows unusual urgency, threats or secrecy, a common pressure "
        "tactic. Slow down and confirm the request with the requester on the number on file.",
        Lang.HI: "भाषा में असामान्य जल्दबाज़ी, धमकी या गोपनीयता दिख रही है, जो दबाव बनाने का आम "
        "तरीका है। जल्दबाज़ी न करें और दर्ज नंबर पर अनुरोधकर्ता से पुष्टि करें।",
    },
    # --- watchlist ---
    ReasonCode.WATCHLIST_HIT: {
        Lang.EN: "The sender or caller appears on our watchlist from the last 30 days. Do not "
        "act on this contact; go to the checker and security before any payment.",
        Lang.HI: "भेजने वाला या कॉल करने वाला पिछले 30 दिनों की हमारी वॉचलिस्ट पर है। इस संपर्क "
        "पर कार्रवाई न करें; किसी भी भुगतान से पहले चेकर और सुरक्षा टीम के पास जाएँ।",
    },
    # --- provenance (Satyapan Seal, docs/SEAL.md). Never reassure; "not sealed" is not "fake" ---
    ReasonCode.VOICE_SEALED: {
        Lang.EN: "This speech carries the voice seal of an enrolled executive's device for this "
        "meeting or note. It shows whose device spoke, not that the request is right: keep every "
        "other check and clearance step on this case.",
        Lang.HI: "इस आवाज़ पर एक पंजीकृत अधिकारी के डिवाइस की वॉइस सील है, जो इसी मीटिंग या नोट "
        "से जुड़ी है। इससे सिर्फ़ पता चलता है कि किसके डिवाइस से बात हुई, अनुरोध सही है यह नहीं; "
        "इस केस की बाकी जाँच और मंज़ूरी जारी रखें।",
    },
    ReasonCode.VOICE_UNSEALED_CLAIMED_EXEC: {
        Lang.EN: "The speaker is presented as an enrolled executive, but 15 seconds or more of "
        "speech carry no seal from their device. Not sealed does not mean fake; confirm through "
        "OOB-Confirm or a callback on the number on file before acting.",
        Lang.HI: "बोलने वाले को पंजीकृत अधिकारी बताया गया है, लेकिन 15 सेकंड या उससे ज़्यादा "
        "आवाज़ पर उनके डिवाइस की सील नहीं है। सील न होने का मतलब नकली होना नहीं है; कार्रवाई से "
        "पहले OOB-Confirm या दर्ज नंबर पर कॉल-बैक से पुष्टि करें।",
    },
    ReasonCode.SEAL_PRESENCE_CONFLICT: {
        Lang.EN: "The executive named here is sealing a different meeting from their enrolled "
        "device right now, and this voice carries no seal. Do not act on this call; call them "
        "back on the directory number and tell the checker.",
        Lang.HI: "जिन अधिकारी का नाम यहाँ है, उनका पंजीकृत डिवाइस इसी समय किसी दूसरी मीटिंग में "
        "सील लगा रहा है, और इस आवाज़ पर कोई सील नहीं है। इस कॉल पर कार्रवाई न करें; डायरेक्टरी "
        "के नंबर पर उन्हें कॉल-बैक करें और चेकर को बताएँ।",
    },
    # --- cross-channel (X1: call/message ask + payment, same case, under 30 minutes) ---
    ReasonCode.CROSS_CHANNEL_SEQUENCE: {
        Lang.EN: "Cross-channel sequence: A request to change bank details was followed by a "
        "payment to a new beneficiary within 30 minutes. Verify independently before paying.",
        Lang.HI: "क्रॉस-चैनल चेतावनी: 30 मिनट के भीतर बैंक विवरण बदलने के अनुरोध के बाद नए "
        "लाभार्थी को भुगतान दर्ज किया गया। भुगतान से पहले स्वतंत्र रूप से पुष्टि करें।",
    },
    ReasonCode.CROSS_CHANNEL_URGENT_BYPASS: {
        Lang.EN: "High-risk cross-channel sequence: A call/message asked for secrecy or approval "
        "bypass alongside a new beneficiary. Payment held for verification.",
        Lang.HI: "अति-जोखिम चेतावनी: नए लाभार्थी के साथ-साथ गोपनीयता या मंज़ूरी बाईपास का "
        "अनुरोध मिला। भुगतान रोक दिया गया है।",
    },
    # --- decision-level (policy engine only) ---
    ReasonCode.MULTI_GROUP_STRONG: {
        Lang.EN: "Two or more independent check groups raised a concern together, so this case "
        "is at HOLD. The checker must clear it after their own callback; the maker cannot "
        "release it.",
        Lang.HI: "दो या अधिक अलग-अलग जाँच समूहों ने एक साथ चिंता जताई है, इसलिए यह केस HOLD पर "
        "है। चेकर अपने कॉल-बैक के बाद ही इसे हटा सकता है; मेकर इसे जारी नहीं कर सकता।",
    },
    ReasonCode.GREY_FLAG: {
        Lang.EN: "Part of this case could not be parsed or a detector failed, so the result is "
        "incomplete. Treat it as at least VERIFY and send it to the checker; do not assume the "
        "missing part is fine.",
        Lang.HI: "इस केस का कुछ हिस्सा पढ़ा नहीं जा सका या कोई डिटेक्टर विफल रहा, इसलिए नतीजा "
        "अधूरा है। इसे कम से कम VERIFY मानें और चेकर के पास भेजें; अधूरे हिस्से को ठीक मानकर आगे "
        "न बढ़ें।",
    },
    ReasonCode.OOB_DENIED: {
        Lang.EN: "The requester answered OOB-Confirm and said they did not ask for this payment. "
        "Stop here: the case moves to HOLD and the checker must take it up as suspected fraud.",
        Lang.HI: "अनुरोधकर्ता ने OOB-Confirm का जवाब दिया और कहा कि उसने यह भुगतान नहीं माँगा था। "
        "यहीं रुकें: केस HOLD पर जाता है और चेकर को इसे संदिग्ध धोखाधड़ी के तौर पर खुद देखना होगा।",
    },
    ReasonCode.OOB_APPROVED: {
        Lang.EN: "The requester answered OOB-Confirm and said they did ask for this. Keep working "
        "the other checks on this case; the OOB answer alone does not settle the payment.",
        Lang.HI: "अनुरोधकर्ता ने OOB-Confirm का जवाब दिया और कहा कि उसने यह अनुरोध किया था। इस "
        "केस की बाकी जाँच जारी रखें; OOB के जवाब मात्र से भुगतान तय नहीं होता।",
    },
}

# Suggested line for the maker to say during a live call when the band rises.
SUGGESTED_LINES: dict[Lang, str] = {
    Lang.EN: "I'll process it once it's raised in the system with your login.",
    Lang.HI: "जैसे ही आप अपने लॉगिन से सिस्टम में अनुरोध डालेंगे, मैं इसे प्रोसेस कर दूँगी।",
}

_HEADLINE: dict[Lang, str] = {Lang.EN: "Band: {band}", Lang.HI: "स्तर: {band}"}


def reason_text(code: ReasonCode, lang: Lang) -> str:
    """Return REASON_TEXT[code][lang]. Raise KeyError if missing (tests catch this)."""
    return REASON_TEXT[code][lang]


def explain_template(decision: Decision, lang: Lang) -> Explanation:
    """Band headline + one line per reason code (in decision.reason_codes order).

    Headline EN: "Band: VERIFY" / HI: "स्तर: VERIFY" (band names stay in English).
    Return Explanation(lang=..., band=decision.band, text=..., source="template",
                       reason_codes=decision.reason_codes).
    """
    lines = [_HEADLINE[lang].format(band=decision.band)]
    lines += [reason_text(code, lang) for code in decision.reason_codes]
    return Explanation(
        lang=lang,
        band=decision.band,
        text="\n".join(lines),
        source="template",
        reason_codes=list(decision.reason_codes),
    )
