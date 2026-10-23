/**
 * copy.ts — the single source of truth for Satya's trilingual voice (MASCOT_SPEC §8).
 *
 * Languages:
 * - 'en': English (calm, clear, no jargon)
 * - 'hinglish': Conversational natural Hindi-English everyday finance team speech
 * - 'hi': शुद्ध एवं सरल हिन्दी (Proofread against MASCOT_SPEC §8)
 *
 * Rule: missing key in any language falls back to the English text, NEVER the raw key name.
 */

export type Lang = 'en' | 'hinglish' | 'hi'

export type CopyVars = Record<string, string | number | undefined>

interface CopyEntry {
  en: string
  hinglish: string
  hi: string
}

export const COPY_TABLE: Record<string, CopyEntry> = {
  // ---- Finale: consent scopes, live captions, alerts with quotes, Screen Guard, notices ----
  'consent.body.v2': {
    en: "I'll keep watch for payment tricks. I ask before I listen to any call, and nothing is saved unless you say so.",
    hinglish: 'Main payment wale dhokhon par nazar rakhunga. Kisi bhi call ko sunne se pehle poochhunga, aur aapke kahe bina kuch save nahi hoga.',
    hi: 'मैं पेमेंट से जुड़े धोखों पर नज़र रखूँगा। किसी भी कॉल को सुनने से पहले पूछूँगा, और आपकी इजाज़त के बिना कुछ भी सेव नहीं होगा।',
  },
  'consent.scope.meetings': {
    en: 'Notice when a meeting starts (window names only)',
    hinglish: 'Meeting shuru hone par pehchaan-na (sirf window ka naam)',
    hi: 'मीटिंग शुरू होने पर पहचानना (सिर्फ़ विंडो का नाम)',
  },
  'consent.scope.listen_yes': {
    en: 'Listen to a call only after you say yes',
    hinglish: 'Call tabhi sunna jab aap haan kahein',
    hi: 'कॉल तभी सुनना जब आप हाँ कहें',
  },
  'consent.scope.screen': {
    en: 'Glance at on-screen text for payment tricks (on this laptop)',
    hinglish: 'Screen ke text mein payment dhokhe dekhna (isi laptop par)',
    hi: 'स्क्रीन के टेक्स्ट में पेमेंट धोखे देखना (इसी लैपटॉप पर)',
  },
  'consent.scope.files_v2': {
    en: 'Check files you hand me',
    hinglish: 'Aapki di hui files check karna',
    hi: 'आपकी दी हुई फ़ाइलें जाँचना',
  },
  'consent.never': {
    en: 'Never: your microphone, recordings, or sending anything off this laptop.',
    hinglish: 'Kabhi nahi: aapka mic, recording, ya laptop se bahar kuch bhejna.',
    hi: 'कभी नहीं: आपका माइक, रिकॉर्डिंग, या लैपटॉप से बाहर कुछ भेजना।',
  },
  'call.title.app': {
    en: "You're in a {app} call.",
    hinglish: 'Aap {app} call par hain.',
    hi: 'आप {app} कॉल पर हैं।',
  },
  'live.listening_to': {
    en: 'Listening to {app}',
    hinglish: '{app} sun raha hoon',
    hi: '{app} सुन रहा हूँ',
  },
  'live.the_call': { en: 'the call', hinglish: 'call', hi: 'कॉल' },
  'live.demo': {
    en: 'DEMO REPLAY — NOT LIVE CAPTURE',
    hinglish: 'DEMO REPLAY — NOT LIVE CAPTURE',
    hi: 'DEMO REPLAY — NOT LIVE CAPTURE',
  },
  'live.waiting': {
    en: 'Waiting for the other person to speak…',
    hinglish: 'Saamne wale ke bolne ka intezaar…',
    hi: 'सामने वाले के बोलने का इंतज़ार…',
  },
  'live.band.PASS': {
    en: 'Nothing risky asked so far',
    hinglish: 'Abhi tak kuch risky nahi maanga',
    hi: 'अभी तक कुछ जोखिम भरा नहीं माँगा गया',
  },
  'live.band.VERIFY': {
    en: 'Verify before you pay',
    hinglish: 'Paise bhejne se pehle verify karo',
    hi: 'पैसे भेजने से पहले पुष्टि करें',
  },
  'live.band.HOLD': {
    en: "Hold — don't pay on this call",
    hinglish: 'Ruko — is call par payment mat karo',
    hi: 'रुकिए — इस कॉल पर पेमेंट न करें',
  },
  'live.note': {
    en: 'Captions stay on this laptop and vanish when the call ends.',
    hinglish: 'Captions isi laptop par rehte hain aur call khatam hote hi mit jaate hain.',
    hi: 'कैप्शन इसी लैपटॉप पर रहते हैं और कॉल ख़त्म होते ही मिट जाते हैं।',
  },
  'action.stop_listening': { en: 'Stop listening', hinglish: 'Sunna band karo', hi: 'सुनना बंद करें' },
  'cue.RUSH': { en: 'Rushing you', hinglish: 'Jaldi karwa rahe hain', hi: 'जल्दबाज़ी करवा रहे हैं' },
  'cue.AUTHORITY': { en: 'Claims to be the boss', hinglish: 'Boss hone ka daava', hi: 'बॉस होने का दावा' },
  'cue.UNREACHABLE': { en: "Says they can't talk", hinglish: 'Kehte hain baat nahi kar sakte', hi: 'कहते हैं बात नहीं कर सकते' },
  'cue.AMOUNT': { en: 'Money amount', hinglish: 'Rakam', hi: 'रक़म' },
  'cue.note': {
    en: 'Grey hints are context only. They never change the decision.',
    hinglish: 'Grey hints sirf context hain. Inse faisla nahi badalta.',
    hi: 'ग्रे संकेत सिर्फ़ संदर्भ हैं। इनसे फ़ैसला नहीं बदलता।',
  },
  'alert.said': { en: 'What they said', hinglish: 'Unhone kya kaha', hi: 'उन्होंने क्या कहा' },
  'alert.body.v2': {
    en: "That doesn't prove who is speaking — so check the payment with {approver} on their own phone.",
    hinglish: 'Isse pakka nahi hota ki bol kaun raha hai — isliye payment {approver} se unke apne phone par confirm karo.',
    hi: 'इससे पक्का नहीं होता कि बोल कौन रहा है — इसलिए पेमेंट {approver} से उनके अपने फ़ोन पर पक्का करें।',
  },
  'action.liveness': { en: 'Video check tips', hinglish: 'Video check tips', hi: 'वीडियो जाँच के सुझाव' },
  'liveness.title': {
    en: 'Is the face real? Try a quick check',
    hinglish: 'Chehra asli hai? Ek chhota check karo',
    hi: 'क्या चेहरा असली है? एक छोटी जाँच करें',
  },
  'liveness.body': {
    en: 'Live face-swaps often glitch when people move. Politely ask them to:',
    hinglish: 'Live face-swap hilne-dulne par aksar gadbad karte hain. Unse vinamrata se kaho:',
    hi: 'लाइव फ़ेस-स्वैप हिलने-डुलने पर अक्सर गड़बड़ाते हैं। उनसे विनम्रता से कहें:',
  },
  'liveness.1': {
    en: 'Turn their head fully to one side',
    hinglish: 'Sir poori tarah ek taraf ghumaayein',
    hi: 'सिर पूरी तरह एक तरफ़ घुमाएँ',
  },
  'liveness.2': {
    en: 'Wave a hand slowly in front of their face',
    hinglish: 'Chehre ke saamne dheere se haath hilaayein',
    hi: 'चेहरे के सामने धीरे से हाथ हिलाएँ',
  },
  'liveness.3': {
    en: "Hold up today's date written on paper",
    hinglish: 'Kaagaz par aaj ki date likh kar dikhaayein',
    hi: 'काग़ज़ पर आज की तारीख़ लिखकर दिखाएँ',
  },
  'liveness.note': {
    en: "A pass doesn't prove who they are. Verifying the payment does.",
    hinglish: 'Pass hone se pehchaan pakki nahi hoti. Payment verify karna zaroori hai.',
    hi: 'पास होने से पहचान पक्की नहीं होती। पेमेंट की पुष्टि ही पक्की करती है।',
  },
  'screen.title': {
    en: 'I noticed something on your screen',
    hinglish: 'Aapki screen par kuch dikha',
    hi: 'आपकी स्क्रीन पर कुछ दिखा',
  },
  'screen.title.clipboard': {
    en: 'About what you copied',
    hinglish: 'Jo aapne copy kiya',
    hi: 'जो आपने कॉपी किया',
  },
  'screen.clear': {
    en: 'Looks OK — I found no payment tricks.',
    hinglish: 'Theek lag raha hai — koi payment dhokha nahi mila.',
    hi: 'ठीक लग रहा है — कोई पेमेंट धोखा नहीं मिला।',
  },
  'screen.unknown_account': {
    en: '{vendor} is named next to an account that is not in your vendor master ({accounts}).',
    hinglish: '{vendor} ke saath ek aisa account dikh raha hai jo vendor master mein nahi hai ({accounts}).',
    hi: '{vendor} के साथ ऐसा खाता दिख रहा है जो वेंडर मास्टर में नहीं है ({accounts})।',
  },
  'screen.asks': { en: 'It asks for', hinglish: 'Isme maanga gaya', hi: 'इसमें माँगा गया' },
  'screen.note': {
    en: 'I read this on this laptop and kept nothing. Checking it properly saves it as evidence.',
    hinglish: 'Maine ise isi laptop par padha aur kuch nahi rakha. Theek se check karne par yeh evidence ban jayega.',
    hi: 'मैंने इसे इसी लैपटॉप पर पढ़ा और कुछ नहीं रखा। ठीक से जाँचने पर यह सबूत के रूप में सेव होगा।',
  },
  'action.check_this': { en: 'Check it properly', hinglish: 'Theek se check karo', hi: 'ठीक से जाँचें' },
  'action.listen_now': { en: 'Listen to a call now', hinglish: 'Abhi call suno', hi: 'अभी कॉल सुनें' },
  'action.open_settings': { en: 'Open setup checklist', hinglish: 'Setup checklist kholo', hi: 'सेटअप चेकलिस्ट खोलें' },
  'action.ok': { en: 'OK', hinglish: 'Theek hai', hi: 'ठीक है' },
  'notice.asr_missing.title': {
    en: "My ears aren't installed yet",
    hinglish: 'Mere kaan abhi install nahi hue',
    hi: 'मेरे कान अभी इंस्टॉल नहीं हुए',
  },
  'notice.asr_missing.body': {
    en: "I can't turn speech into words on this laptop. Run `make asr` in the Satyapan folder, then restart the engine.",
    hinglish: 'Main is laptop par awaaz ko shabdon mein nahi badal pa raha. Satyapan folder mein `make asr` chalaayein, phir engine restart karein.',
    hi: 'मैं इस लैपटॉप पर आवाज़ को शब्दों में नहीं बदल पा रहा। Satyapan फ़ोल्डर में `make asr` चलाएँ, फिर इंजन दोबारा शुरू करें।',
  },
  'notice.capture_error.title': {
    en: "I couldn't hear the call",
    hinglish: 'Main call sun nahi paaya',
    hi: 'मैं कॉल सुन नहीं पाया',
  },
  'notice.capture_error.body': {
    en: '{reason}. I stopped listening. Check the Screen & System Audio Recording permission for Satya.',
    hinglish: '{reason}. Maine sunna band kar diya. Satya ke liye Screen & System Audio Recording permission check karein.',
    hi: '{reason}। मैंने सुनना बंद कर दिया। Satya के लिए Screen & System Audio Recording अनुमति जाँचें।',
  },
  'notice.backend.title': {
    en: "I can't reach my brain",
    hinglish: 'Mera dimaag (engine) nahi mil raha',
    hi: 'मेरा दिमाग़ (इंजन) नहीं मिल रहा',
  },
  'notice.backend.body': {
    en: 'Start the local engine with `make run`, then wake me again.',
    hinglish: '`make run` se local engine chalaayein, phir mujhe jagaayein.',
    hi: '`make run` से लोकल इंजन चलाएँ, फिर मुझे जगाएँ।',
  },
  'notice.call_ended.title': {
    en: 'The call ended, so I stopped listening.',
    hinglish: 'Call khatam ho gayi, isliye maine sunna band kar diya.',
    hi: 'कॉल ख़त्म हो गई, इसलिए मैंने सुनना बंद कर दिया।',
  },
  'notice.listening_stopped.title': {
    en: 'I stopped listening.',
    hinglish: 'Maine sunna band kar diya.',
    hi: 'मैंने सुनना बंद कर दिया।',
  },
  'notice.call_ended.body': {
    en: 'Captions were dropped. The chips and the decision are kept in your Notebook.',
    hinglish: 'Captions mita diye gaye. Chips aur faisla Notebook mein hain.',
    hi: 'कैप्शन मिटा दिए गए। चिप्स और फ़ैसला आपकी नोटबुक में हैं।',
  },
  'notice.voice_note.title': {
    en: "I didn't judge the voice itself",
    hinglish: 'Maine awaaz ko khud nahi parkha',
    hi: 'मैंने आवाज़ को ख़ुद नहीं परखा',
  },
  'quip.hello': { en: 'Hi! I’m Satya.', hinglish: 'Namaste! Main Satya.', hi: 'नमस्ते! मैं सत्य हूँ।' },
  'quip.watching': { en: 'On watch!', hinglish: 'Nazar rakh raha hoon!', hi: 'नज़र रख रहा हूँ!' },
  'quip.sleep': { en: 'Zzz… wake me anytime.', hinglish: 'Zzz… jab chaaho jaga lena.', hi: 'Zzz… जब चाहें जगा लें।' },
  'quip.listening': { en: "I'm listening.", hinglish: 'Sun raha hoon.', hi: 'सुन रहा हूँ।' },
  'quip.hmm': { en: 'Hmm… {chip}?', hinglish: 'Hmm… {chip}?', hi: 'हम्म… {chip}?' },
  'quip.pause': { en: "Wait! Don't pay yet.", hinglish: 'Ruko! Abhi paise mat bhejo.', hi: 'रुकिए! अभी पैसे न भेजें।' },
  'quip.safe': { en: 'Phew, all good!', hinglish: 'Phew, sab theek!', hi: 'चलो, सब ठीक!' },
  'quip.gulp': { en: 'Let me look…', hinglish: 'Dekhta hoon…', hi: 'देखता हूँ…' },
  'quip.writing': { en: 'Writing your report…', hinglish: 'Report likh raha hoon…', hi: 'रिपोर्ट लिख रहा हूँ…' },
  'quip.pet': { en: 'Hehe, that tickles!', hinglish: 'Hehe, gudgudi hoti hai!', hi: 'हीही, गुदगुदी होती है!' },
  'quip.drop': { en: 'Drop it on me!', hinglish: 'Mujh par daal do!', hi: 'मुझ पर छोड़ दीजिए!' },
  'quip.meeting': { en: '{app}? Want me to listen?', hinglish: '{app}? Sunun kya?', hi: '{app}? क्या मैं सुनूँ?' },
  'quip.screen': { en: 'Look at this…', hinglish: 'Yeh dekho…', hi: 'यह देखिए…' },
  'quip.bye': { en: 'Bye! Find me in the menu bar.', hinglish: 'Bye! Menu bar mein milunga.', hi: 'अलविदा! मेन्यू बार में मिलूँगा।' },
  // Consent Card
  'consent.title': {
    en: 'Can I keep watch?',
    hinglish: 'Kya main nazar rakhun?',
    hi: 'क्या मैं नज़र रखूँ?',
  },
  'consent.body': {
    en: "I'll notice when a call starts and ask before I listen. I only look for payment tricks. Nothing is saved unless you say so.",
    hinglish: 'Call shuru hote hi main pehle poochhunga, phir hi sununga. Main sirf payment wale dhokhe dhoondhta hoon. Aapke kahe bina kuch save nahi hota.',
    hi: 'कॉल शुरू होने पर मैं पहले पूछूँगा, फिर ही सुनूँगा। मैं सिर्फ़ पेमेंट से जुड़े धोखे ढूँढता हूँ। आपकी इजाज़त के बिना कुछ भी सेव नहीं होता.',
  },
  'consent.scope.notice': {
    en: 'Notice calls (no recording)',
    hinglish: 'Call notice karna (recording nahi)',
    hi: 'कॉल पहचानना (रिकॉर्डिंग नहीं)',
  },
  'consent.scope.listen': {
    en: 'Listen to a call when you say yes',
    hinglish: 'Aapki haan par call sunna',
    hi: 'आपकी हाँ पर कॉल सुनना',
  },
  'consent.scope.files': {
    en: 'Check files you give me',
    hinglish: 'Aapki di hui files check karna',
    hi: 'आपकी दी हुई फ़ाइलें जाँचना',
  },
  'action.start_watching': {
    en: 'Start watching',
    hinglish: 'Nazar rakhna shuru karo',
    hi: 'नज़र रखना शुरू करें',
  },
  'action.not_now': {
    en: 'Not now',
    hinglish: 'Abhi nahi',
    hi: 'अभी नहीं',
  },

  // Call Ask Card
  'call.title': {
    en: 'Sounds like a call.',
    hinglish: 'Lagta hai call chal rahi hai.',
    hi: 'लगता है कॉल चल रही है।',
  },
  'call.body': {
    en: "Want me to listen for payment tricks? I won't record it.",
    hinglish: 'Payment wale dhokhon ke liye sunun? Main record nahi karunga.',
    hi: 'क्या मैं पेमेंट से जुड़े धोखों के लिए सुनूँ? मैं रिकॉर्ड नहीं करूँगा।',
  },
  'action.listen_call': {
    en: 'Listen to this call',
    hinglish: 'Yeh call suno',
    hi: 'यह कॉल सुनें',
  },
  'action.not_this_call': {
    en: 'Not this one',
    hinglish: 'Is baar nahi',
    hi: 'इस बार नहीं',
  },

  // Live Listening Card
  'live.title': {
    en: 'Listening…',
    hinglish: 'Sun raha hoon…',
    hi: 'सुन रहा हूँ…',
  },
  'live.active_call': {
    en: 'Active call check',
    hinglish: 'Call check chal raha hai',
    hi: 'सक्रिय कॉल जाँच',
  },
  'coverage.degraded': {
    en: "Audio is unclear — I won't judge the voice.",
    hinglish: 'Awaaz saaf nahi — main awaaz par faisla nahi karunga.',
    hi: 'आवाज़ साफ़ नहीं है — मैं आवाज़ पर फ़ैसला नहीं करूँगा।',
  },
  'coverage.usable': {
    en: 'Audio is clear.',
    hinglish: 'Awaaz saaf hai.',
    hi: 'आवाज़ साफ़ है।',
  },
  'seal.not_verified': {
    en: 'Voice not verified by Seal',
    hinglish: 'Awaaz Seal se verified nahi',
    hi: 'आवाज़ सील से सत्यापित नहीं',
  },
  'seal.verified': {
    en: 'Voice verified by VoiceSeal',
    hinglish: 'Awaaz VoiceSeal se verified hai',
    hi: 'आवाज़ वॉइस-सील द्वारा सत्यापित है',
  },

  // Asks / Red Flag Chips
  'ask.A1': {
    en: 'New account',
    hinglish: 'Naya account',
    hi: 'नया खाता',
  },
  'ask.A2': {
    en: 'OTP / PIN',
    hinglish: 'OTP / PIN',
    hi: 'ओटीपी / पिन',
  },
  'ask.A3': {
    en: 'Screen sharing',
    hinglish: 'Screen share',
    hi: 'स्क्रीन शेयर',
  },
  'ask.A4': {
    en: 'Keep it secret',
    hinglish: 'Kisi ko mat batao',
    hi: 'किसी को मत बताओ',
  },
  'ask.A5': {
    en: 'Skip approval',
    hinglish: 'Approval chhod do',
    hi: 'मंज़ूरी छोड़ दो',
  },
  'ask.A6': {
    en: 'Gift card / crypto / UPI collect',
    hinglish: 'Gift card / crypto / UPI collect',
    hi: 'गिफ़्ट कार्ड / क्रिप्टो / यूपीआई कलेक्ट',
  },
  'ask.A7': {
    en: 'Change bank details',
    hinglish: 'Bank details badlo',
    hi: 'बैंक विवरण बदलो',
  },

  // Alert Card
  'alert.title': {
    en: 'Pause before you pay.',
    hinglish: 'Paise bhejne se pehle ek second ruko.',
    hi: 'पैसे भेजने से पहले एक पल रुकिए।',
  },
  'alert.body': {
    en: "This call asked for: {chips}. That doesn't prove who is speaking — let's check with {approver} on their own phone.",
    hinglish: 'Is call mein maanga gaya: {chips}. Isse yeh pakka nahi hota ki bol kaun raha hai — chalo {approver} se unke apne phone par confirm karte hain.',
    hi: 'इस कॉल में माँगा गया: {chips}। इससे यह पक्का नहीं होता कि बोल कौन रहा है — चलिए {approver} से उनके अपने फ़ोन पर पुष्टि करते हैं।',
  },
  'alert.chips_fallback': {
    en: 'urgent changes',
    hinglish: 'zaroori badlaav',
    hi: 'ज़रूरी बदलाव',
  },
  'action.verify': {
    en: 'Verify with {approver}',
    hinglish: '{approver} se verify karo',
    hi: '{approver} से पुष्टि करें',
  },
  'action.verify_with_approver': {
    en: 'Verify with {approver}',
    hinglish: '{approver} se verify karo',
    hi: '{approver} से पुष्टि करें',
  },
  'action.copy_reply': {
    en: 'Copy a safe reply',
    hinglish: 'Safe jawab copy karo',
    hi: 'सुरक्षित जवाब कॉपी करें',
  },
  'action.copy_safe_reply': {
    en: 'Copy a safe reply',
    hinglish: 'Safe jawab copy karo',
    hi: 'सुरक्षित जवाब कॉपी करें',
  },
  'safe_reply': {
    en: "I'll verify this through our registered process and call you back.",
    hinglish: 'Hum ise registered process se verify karke aapko wapas call karenge.',
    hi: 'हम इसे अपनी रजिस्टर्ड प्रक्रिया से सत्यापित करके आपको वापस कॉल करेंगे।',
  },
  'action.open_notebook': {
    en: 'Open Notebook',
    hinglish: 'Notebook kholo',
    hi: 'नोटबुक खोलें',
  },
  'action.open_reports': {
    en: 'Open Reports',
    hinglish: 'Reports kholo',
    hi: 'रिपोर्ट्स खोलें',
  },
  'action.dismiss': {
    en: 'Close',
    hinglish: 'Band karein',
    hi: 'बंद करें',
  },
  'action.cancel': {
    en: 'Cancel',
    hinglish: 'Cancel karein',
    hi: 'रद्द करें',
  },
  'action.hold': {
    en: 'Hold payment',
    hinglish: 'Payment rokein',
    hi: 'पेमेंट रोकें',
  },

  // OOB Verification Cards
  'oob.wait': {
    en: 'Asked {approver} on their own phone. Waiting…',
    hinglish: '{approver} se unke phone par poochha hai. Intezaar…',
    hi: '{approver} से उनके फ़ोन पर पूछा है। इंतज़ार…',
  },
  'oob.wait.badge': {
    en: 'Out-of-band verification sent',
    hinglish: 'Approver ke phone par request bhej di gayi hai',
    hi: 'मंज़ूरीकर्ता के फ़ोन पर सत्यापन अनुरोध भेजा गया है',
  },
  'oob.title.approved': {
    en: 'Payment confirmed',
    hinglish: 'Payment confirm ho gaya',
    hi: 'पेमेंट सत्यापित हो गया',
  },
  'oob.title.notice': {
    en: 'Verification notice',
    hinglish: 'Verification alert',
    hi: 'सत्यापन सूचना',
  },
  'oob.approved': {
    en: '{approver} confirmed this exact payment. You can continue.',
    hinglish: '{approver} ne isi payment ko confirm kiya. Aap aage badh sakte hain.',
    hi: '{approver} ने इसी पेमेंट की पुष्टि की। आप आगे बढ़ सकते हैं।',
  },
  'oob.rejected': {
    en: '{approver} rejected this request. Keep the payment on hold.',
    hinglish: '{approver} ne request reject ki. Payment hold par rakhein.',
    hi: '{approver} ने यह अनुरोध अस्वीकार कर दिया। पेमेंट होल्ड पर रखें।',
  },
  'oob.not_requested': {
    en: "{approver} says they didn't ask for this. I've put the payment on hold.",
    hinglish: 'Unki taraf se yeh request nahi aayi thi. Payment hold par daal di hai.',
    hi: '{approver} ने कहा कि उन्होंने यह नहीं माँगा। मैंने पेमेंट होल्ड पर डाल दिया है।',
  },
  'oob.expired': {
    en: 'No answer from {approver} — that is not a yes. Keep it on hold.',
    hinglish: '{approver} ka jawab nahi aaya — iska matlab haan nahi. Hold par rakho.',
    hi: '{approver} का जवाब नहीं आया — इसका मतलब हाँ नहीं है। होल्ड पर रखें।',
  },

  // File Ask Card
  'file.title': {
    en: 'Should I read this?',
    hinglish: 'Kya main ise padhun?',
    hi: 'क्या मैं इसे पढ़ूँ?',
  },
  'file.body': {
    en: 'I\'ll check "{name}" and keep its fingerprint in your Notebook.',
    hinglish: 'Main "{name}" check karke uska fingerprint aapki Notebook mein rakhunga.',
    hi: 'मैं "{name}" जाँचकर उसका फ़िंगरप्रिंट आपकी नोटबुक में रखूँगा।',
  },
  'action.check_it': {
    en: 'Check it',
    hinglish: 'Check karo',
    hi: 'जाँचें',
  },
  'action.no_thanks': {
    en: 'No thanks',
    hinglish: 'Rehne do',
    hi: 'रहने दें',
  },

  // Result Cards
  'result.PASS': {
    en: 'Looks OK.',
    hinglish: 'Theek lag raha hai.',
    hi: 'ठीक लग रहा है।',
  },
  'result.VERIFY': {
    en: 'Verify first.',
    hinglish: 'Pehle verify karo.',
    hi: 'पहले पुष्टि करें।',
  },
  'result.HOLD': {
    en: 'Hold this payment.',
    hinglish: 'Yeh payment roko.',
    hi: 'यह पेमेंट रोकें।',
  },

  // Scribe / Golden-Hour Report Cards
  'scribe.ask': {
    en: 'Money already left? I can prepare your report pack now. Every minute counts.',
    hinglish: 'Paise chale gaye? Main abhi report pack bana deta hoon. Har minute keemti hai.',
    hi: 'पैसे जा चुके हैं? मैं अभी रिपोर्ट पैक तैयार कर देता हूँ। हर मिनट क़ीमती है।',
  },
  'action.prepare': {
    en: 'Prepare it',
    hinglish: 'Bana do',
    hi: 'तैयार करें',
  },
  'action.prepare_report': {
    en: 'Prepare it',
    hinglish: 'Bana do',
    hi: 'तैयार करें',
  },
  'scribe.writing': {
    en: 'Writing your report pack…',
    hinglish: 'Report pack likh raha hoon…',
    hi: 'रिपोर्ट पैक लिख रहा हूँ…',
  },
  'scribe.body.done': {
    en: '1930 helpline, bank freeze letter, and CERT-In draft pack ready.',
    hinglish: '1930 helpline, bank freeze letter, aur CERT-In draft pack taiyaar hai.',
    hi: '1930 हेल्पलाइन, बैंक फ़्रीज़ पत्र और सर्ट-इन ड्राफ़्ट पैक तैयार है।',
  },
  'scribe.body.writing': {
    en: 'Assembling hashes and evidence ledger for golden-hour freeze…',
    hinglish: 'Golden-hour freeze ke liye hashes aur evidence ledger joda ja raha hai…',
    hi: 'गोल्डन-आवर फ़्रीज़ के लिए हैश और साक्ष्य लेज़र तैयार किया जा रहा है…',
  },
  'scribe.status.ready': {
    en: '✓ ready',
    hinglish: '✓ taiyaar',
    hi: '✓ तैयार',
  },
  'scribe.status.writing': {
    en: 'writing…',
    hinglish: 'likh raha hoon…',
    hi: 'लिख रहा हूँ…',
  },
  'scribe.status.pending': {
    en: 'pending',
    hinglish: 'baaki hai',
    hi: 'बाक़ी है',
  },
  'scribe.section.1930': {
    en: '1930 Helpline Packet',
    hinglish: '1930 Helpline Packet',
    hi: '1930 हेल्पलाइन पैकेट',
  },
  'scribe.section.bank': {
    en: 'Bank Freeze Letter',
    hinglish: 'Bank Freeze Letter',
    hi: 'बैंक फ़्रीज़ पत्र',
  },
  'scribe.section.certin': {
    en: 'CERT-In Incident Report',
    hinglish: 'CERT-In Incident Report',
    hi: 'सर्ट-इन घटना रिपोर्ट',
  },
  'scribe.section.ledger': {
    en: 'Evidence Ledger & Hashes',
    hinglish: 'Evidence Ledger aur Hashes',
    hi: 'साक्ष्य लेज़र एवं हैश',
  },
  'scribe.section.police': {
    en: 'Police Complaint Draft',
    hinglish: 'Police Complaint Draft',
    hi: 'पुलिस शिकायत ड्राफ़्ट',
  },
  'scribe.done': {
    en: 'Done. 5 drafts ready — you review and submit.',
    hinglish: 'Ho gaya. 5 drafts taiyaar — aap check karke submit karein.',
    hi: 'हो गया। 5 ड्राफ़्ट तैयार — आप जाँचकर सबमिट करें।',
  },

  // Toast / System Notifications
  'toast.sleep': {
    en: "Sleeping. I'm not listening.",
    hinglish: 'So raha hoon. Kuch nahi sun raha.',
    hi: 'सो रहा हूँ। कुछ नहीं सुन रहा।',
  },
  'toast.stopped': {
    en: 'I stopped listening: {reason}.',
    hinglish: 'Maine sunna band kiya: {reason}.',
    hi: 'मैंने सुनना बंद किया: {reason}।',
  },
  'toast.off': {
    en: 'Bye! Bring me back from the menu bar.',
    hinglish: 'Bye! Menu bar se wapas bula lena.',
    hi: 'अलविदा! मेन्यू बार से वापस बुला लें।',
  },
  'toast.no_backend': {
    en: "I can't reach my brain, so I went to sleep.",
    hinglish: 'Mera dimaag (backend) nahi mil raha, isliye so gaya.',
    hi: 'मेरा दिमाग़ (बैकएंड) नहीं मिल रहा, इसलिए सो गया।',
  },
  'clipboard_empty': {
    en: 'Clipboard is empty — copy an email or message first.',
    hinglish: 'Clipboard khali hai — pehle email ya message copy karein.',
    hi: 'क्लिपबोर्ड खाली है — पहले ईमेल या संदेश कॉपी करें।',
  },
  'scanning_screen': {
    en: 'Scanning screen for fraud indicators…',
    hinglish: 'Screen par fraud indicators scan ho rahe hain…',
    hi: 'स्क्रीन पर धोखाधड़ी के संकेत स्कैन हो रहे हैं…',
  },
  'screen_guard_active': {
    en: 'Screen Guard active: watching screen for payment tricks.',
    hinglish: 'Screen Guard active: payment tricks ke liye screen par nazar hai.',
    hi: 'स्क्रीन गार्ड सक्रिय: स्क्रीन पर नज़र रखी जा रही है।',
  },
  'screen_guard_paused': {
    en: 'Screen Guard paused.',
    hinglish: 'Screen Guard pause ho gaya.',
    hi: 'स्क्रीन गार्ड रुका हुआ है।',
  },
  'screen_guard_resumed': {
    en: 'Screen Guard resumed.',
    hinglish: 'Screen Guard wapas shuru ho gaya.',
    hi: 'स्क्रीन गार्ड पुनः सक्रिय।',
  },
  'toast.capture_error': {
    en: 'Audio capture error — went to sleep for safety.',
    hinglish: 'Audio capture me dikkat aayi — safety ke liye so gaya.',
    hi: 'ऑडियो कैप्चर में समस्या — सुरक्षा के लिए सो गया।',
  },
  'toast.copied': {
    en: 'Safe reply copied to clipboard.',
    hinglish: 'Safe jawab copy ho gaya.',
    hi: 'सुरक्षित उत्तर कॉपी हो गया।',
  },

  // Radial Menu Labels
  'menu.watch': {
    en: 'Watch',
    hinglish: 'Nazar rakho',
    hi: 'नज़र रखें',
  },
  'menu.sleep': {
    en: 'Sleep',
    hinglish: 'So jao',
    hi: 'सो जाएँ',
  },
  'menu.check': {
    en: 'Check something',
    hinglish: 'Kuch check karo',
    hi: 'कुछ जाँचें',
  },
  'menu.notebook': {
    en: 'Notebook',
    hinglish: 'Notebook',
    hi: 'नोटबुक',
  },
  'menu.off': {
    en: 'Turn off',
    hinglish: 'Band karo',
    hi: 'बंद करें',
  },

  // Common Reason Strings & Signals
  'reason.voice_not_verified': {
    en: 'Voice not verified by Seal',
    hinglish: 'Awaaz Seal se verified nahi',
    hi: 'आवाज़ सील से सत्यापित नहीं',
  },
  'reason.urgent_bypass': {
    en: 'Urgent bypass requested',
    hinglish: 'Emergency bypass maanga gaya',
    hi: 'आपातकालीन मंज़ूरी बाईपास माँगा गया',
  },
  'reason.screen_sharing': {
    en: 'Screen sharing requested',
    hinglish: 'Screen share karne ko bola gaya',
    hi: 'स्क्रीन शेयर करने का अनुरोध किया गया',
  },
  'reason.new_payee': {
    en: 'New payee account ••••9917 not on vendor master',
    hinglish: 'Naya payee account ••••9917 vendor list me nahi hai',
    hi: 'नया खाता ••••9917 वेंडर मास्टर में नहीं है',
  },
  'reason.amount_limit': {
    en: 'Amount ₹48,50,000 exceeds floor limit',
    hinglish: '₹48,50,000 ki raqam floor limit se zyada hai',
    hi: '₹48,50,000 की राशि सीमा से अधिक है',
  },
  'reason.screen_clean': {
    en: 'No urgent payment tricks, remote scam tools, or credential requests found on screen.',
    hinglish: 'Screen par koi payment trick, remote tool ya OTP maangne wala fraud nahi mila.',
    hi: 'स्क्रीन पर कोई भुगतान ट्रिक, रिमोट टूल या धोखाधड़ी नहीं पाई गई।',
  },
  'ASK_PAYEE_CHANGE': {
    en: 'Beneficiary change requested',
    hinglish: 'Account badalne ki request',
    hi: 'लाभार्थी बदलने का अनुरोध',
  },
  'FLOOR_N2_NEW_LARGE': {
    en: 'Large amount to new vendor',
    hinglish: 'Naye vendor ko badi payment',
    hi: 'नए वेंडर को बड़ी राशि का भुगतान',
  },
  'ASK_SECRECY': {
    en: 'Keep transaction secret',
    hinglish: 'Transaction secret rakhne ko bola gaya',
    hi: 'लेन-देन गुप्त रखने को कहा गया',
  },
  'ASK_REMOTE_ACCESS': {
    en: 'Remote access tool requested',
    hinglish: 'Remote access tool download karne ko bola gaya',
    hi: 'रिमोट एक्सेस टूल का अनुरोध किया गया',
  },
  'ASK_CREDENTIAL': {
    en: 'OTP/PIN credential requested',
    hinglish: 'OTP ya PIN maanga gaya',
    hi: 'ओटीपी या पिन माँगा गया',
  },
  'reason.caller_new_account': {
    en: 'The caller asked for a new account.',
    hinglish: 'Caller ne naya account maanga.',
    hi: 'कॉलर ने नए खाते का अनुरोध किया।',
  },
  'reason.caller_secret_skip': {
    en: 'The caller asked to keep it secret and skip approval.',
    hinglish: 'Caller ne secret rakhne aur approval chhodne ko bola.',
    hi: 'कॉलर ने इसे गुप्त रखने और मंज़ूरी छोड़ने को कहा।',
  },
  'reason.vendor_differs': {
    en: 'The bank account differs from the vendor master.',
    hinglish: 'Bank account vendor master se alag hai.',
    hi: 'बैंक खाता वेंडर मास्टर से भिन्न है।',
  },
  'reason.call_registered_number': {
    en: 'Call the vendor on the number already on file — not the one in the email.',
    hinglish: 'Vendor ko purane registered number par call karein — email wale par nahi.',
    hi: 'वेंडर को पहले से दर्ज नंबर पर कॉल करें — ईमेल वाले नंबर पर नहीं।',
  },
  'reason.no_tricks_copied': {
    en: 'No urgent payment tricks found in copied text',
    hinglish: 'Copy kiye text me koi payment trick nahi mili.',
    hi: 'कॉपी किए गए टेक्स्ट में कोई संदिग्ध संकेत नहीं मिले।',
  },
}

/** Translates reason bullet points or signal codes dynamically into target language */
export function translateReason(reason: string, lang: Lang = 'en'): string {
  if (lang === 'en') return reason

  const trimmed = reason.trim()
  if (COPY_TABLE[trimmed]) {
    return t(trimmed, lang)
  }

  // Reverse match against exact English strings in COPY_TABLE
  for (const [key, entry] of Object.entries(COPY_TABLE)) {
    if (entry.en.toLowerCase() === trimmed.toLowerCase()) {
      return t(key, lang)
    }
  }

  const lower = trimmed.toLowerCase()

  // Dynamic regex for "This payment is ₹48,50,000 to ACME Corp."
  const paymentToMatch = trimmed.match(/^This payment is\s+(.+?)\s+to\s+(.+)$/i)
  if (paymentToMatch) {
    const amount = paymentToMatch[1]
    let payee = paymentToMatch[2].trim()
    if (payee.endsWith('.')) {
      payee = payee.slice(0, -1).trim()
    }
    if (lang === 'hi') {
      return `यह भुगतान ${amount} ${payee} के लिए है।`
    }
    return `Yeh payment ${amount} ${payee} ke liye hai.`
  }

  if (lower.includes('voice not verified')) return t('reason.voice_not_verified', lang)
  if (lower.includes('urgent bypass') || lower.includes('bypass requested')) return t('reason.urgent_bypass', lang)
  if (lower.includes('screen sharing')) return t('reason.screen_sharing', lang)
  if (lower.includes('exceeds floor limit')) return t('reason.amount_limit', lang)
  if (lower.includes('not on vendor master') || lower.includes('new payee')) return t('reason.new_payee', lang)
  if (lower.includes('no urgent payment tricks') || lower.includes('remote scam tools')) return t('reason.screen_clean', lang)
  if (lower.includes('new account')) return t('reason.caller_new_account', lang)
  if (lower.includes('secret') && lower.includes('approval')) return t('reason.caller_secret_skip', lang)
  if (lower.includes('differs from') || lower.includes('vendor master')) return t('reason.vendor_differs', lang)
  if (lower.includes('call the vendor') || lower.includes('number already on file')) return t('reason.call_registered_number', lang)
  if (lower.includes('copied text')) return t('reason.no_tricks_copied', lang)

  return reason
}

/** Translates card headlines dynamically into target language */
export function translateHeadline(headline: string, lang: Lang = 'en', defaultBand?: string): string {
  if (lang === 'en') return headline

  const trimmed = headline.trim()
  if (COPY_TABLE[trimmed]) {
    return t(trimmed, lang)
  }

  // Reverse match against exact English strings
  for (const [key, entry] of Object.entries(COPY_TABLE)) {
    if (entry.en.toLowerCase() === trimmed.toLowerCase()) {
      return t(key, lang)
    }
  }

  const lower = trimmed.toLowerCase()
  if (lower.includes('pause before you pay') || defaultBand === 'HOLD') {
    return t('alert.title', lang)
  }
  if (lower.includes('verify first') || defaultBand === 'VERIFY') {
    return t('result.VERIFY', lang)
  }
  if (lower.includes('looks ok') || defaultBand === 'PASS') {
    return t('result.PASS', lang)
  }
  if (lower.includes('hold this payment')) {
    return t('result.HOLD', lang)
  }
  if (lower.includes('payment confirmed')) {
    return t('oob.title.approved', lang)
  }
  if (lower.includes('verification notice')) {
    return t('oob.title.notice', lang)
  }
  if (lower.includes('screen looks ok')) {
    return lang === 'hi' ? 'स्क्रीन ठीक लग रही है' : 'Screen theek lag rahi hai'
  }
  if (lower.includes('text looks ok')) {
    return lang === 'hi' ? 'टेक्स्ट ठीक लग रहा है' : 'Text theek lag raha hai'
  }

  return headline
}

/** Translates section titles for Scribe report pack */
export function translateSectionTitle(title: string, lang: Lang = 'en'): string {
  if (lang === 'en') return title
  const lower = title.toLowerCase()
  if (lower.includes('1930')) return t('scribe.section.1930', lang)
  if (lower.includes('bank freeze')) return t('scribe.section.bank', lang)
  if (lower.includes('cert-in') || lower.includes('certin')) return t('scribe.section.certin', lang)
  if (lower.includes('ledger') || lower.includes('hashes')) return t('scribe.section.ledger', lang)
  if (lower.includes('police')) return t('scribe.section.police', lang)
  return title
}

/** Translates toast messages whether passed as a key or as raw English copy */
export function translateToast(textOrKey: string, lang: Lang = 'en'): string {
  const trimmed = textOrKey.trim()

  // 1. Direct key match (in every language, English included)
  if (COPY_TABLE[trimmed]) {
    return t(trimmed, lang)
  }
  if (lang === 'en') return textOrKey

  // 2. Stopped listening with reason
  if (trimmed.toLowerCase().startsWith('i stopped listening:')) {
    const rawReason = trimmed.replace(/^i stopped listening:\s*/i, '').replace(/\.$/, '')
    const translatedReason = translateReason(rawReason, lang)
    return t('toast.stopped', lang, { reason: translatedReason })
  }

  // 3. Exact English reverse match
  for (const [key, entry] of Object.entries(COPY_TABLE)) {
    if (entry.en.toLowerCase() === trimmed.toLowerCase()) {
      return t(key, lang)
    }
  }

  // 4. Fuzzy English toast patterns
  const lower = trimmed.toLowerCase()
  if (lower.includes('clipboard is empty')) return t('clipboard_empty', lang)
  if (lower.includes('scanning screen')) return t('scanning_screen', lang)
  if (lower.includes('screen guard active')) return t('screen_guard_active', lang)
  if (lower.includes('screen guard paused')) return t('screen_guard_paused', lang)
  if (lower.includes('screen guard resumed')) return t('screen_guard_resumed', lang)
  if (lower.includes('sleeping') && lower.includes('not listening')) return t('toast.sleep', lang)
  if (lower.includes("can't reach my brain") || lower.includes('cannot reach my brain')) return t('toast.no_backend', lang)
  if (lower.includes('bring me back from the menu bar')) return t('toast.off', lang)
  if (lower.includes('capture error')) return t('toast.capture_error', lang)
  if (lower.includes('copied to clipboard') || lower.includes('safe reply copied')) return t('toast.copied', lang)
  if (lower.includes('done. 5 drafts ready') || lower.includes('5 drafts ready')) return t('scribe.done', lang)

  return t(textOrKey, lang)
}

/**
 * Pure translation function.
 * - Missing key in target lang falls back to the EN text.
 * - Unknown key falls back to formatted readable label, NEVER the raw key name.
 * - Interpolates `{placeholder}` with provided `vars`.
 */
/** Like `t`, but returns free text unchanged when it is not a copy key. */
export function tx(textOrKey: string, lang: Lang = 'en', vars?: CopyVars): string {
  if (COPY_TABLE[textOrKey]) return t(textOrKey, lang, vars)
  if (!vars) return textOrKey
  return textOrKey.replace(/\{(\w+)\}/g, (_, name: string) =>
    vars[name] !== undefined ? String(vars[name]) : `{${name}}`,
  )
}

export function t(key: string, lang: Lang = 'en', vars?: CopyVars): string {
  const entry = COPY_TABLE[key]
  let template: string

  if (entry) {
    template = entry[lang] || entry.en
  } else {
    // Missing key entirely: fallback to clean, human-readable text derived from key, not raw key
    template = key.replace(/^[a-z]+\./, '').replace(/_/g, ' ')
  }

  if (!vars) return template

  return template.replace(/\{(\w+)\}/g, (_, varName: string) => {
    const val = vars[varName]
    return val !== undefined ? String(val) : `{${varName}}`
  })
}

