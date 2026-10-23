import { describe, expect, it } from 'vitest'

import {
  t,
  translateHeadline,
  translateReason,
  translateSectionTitle,
  translateToast,
  type Lang,
} from '../renderer/src/shared/copy'

describe('F08: Trilingual copy engine (copy.ts)', () => {
  it('translates consent titles across EN, Hinglish and हिन्दी', () => {
    expect(t('consent.title', 'en')).toBe('Can I keep watch?')
    expect(t('consent.title', 'hinglish')).toBe('Kya main nazar rakhun?')
    expect(t('consent.title', 'hi')).toBe('क्या मैं नज़र रखूँ?')
  })

  it('translates alert copy with variable interpolation', () => {
    const en = t('alert.body', 'en', { chips: 'OTP, Screen sharing', approver: 'Priya' })
    expect(en).toContain('OTP, Screen sharing')
    expect(en).toContain('Priya')
    expect(en).toContain("let's check with Priya on their own phone.")

    const hi = t('alert.body', 'hi', { chips: 'ओटीपी', approver: 'प्रिया' })
    expect(hi).toContain('ओटीपी')
    expect(hi).toContain('प्रिया')
    expect(hi).toContain('पुष्टि करते हैं')
  })

  it('falls back to English when a key is missing in target language, never the key', () => {
    // Test with a mock key or safe fallback
    const result = t('action.start_watching', 'hinglish')
    expect(result).toBe('Nazar rakhna shuru karo')

    const unknown = t('custom.some_random_action', 'hi')
    expect(unknown).not.toContain('custom.')
    expect(unknown).toBe('some random action')
  })

  it('provides safe reply text for one-click copy', () => {
    expect(t('safe_reply', 'en')).toBe(
      "I'll verify this through our registered process and call you back.",
    )
    expect(t('safe_reply', 'hinglish')).toBe(
      'Hum ise registered process se verify karke aapko wapas call karenge.',
    )
    expect(t('safe_reply', 'hi')).toBe(
      'हम इसे अपनी रजिस्टर्ड प्रक्रिया से सत्यापित करके आपको वापस कॉल करेंगे।',
    )
  })

  it('translates reason bullets dynamically across Hinglish and Hindi', () => {
    const r1 = 'New payee account ••••9917 not on vendor master'
    expect(translateReason(r1, 'hinglish')).toBe('Naya payee account ••••9917 vendor list me nahi hai')
    expect(translateReason(r1, 'hi')).toBe('नया खाता ••••9917 वेंडर मास्टर में नहीं है')

    const r2 = 'Amount ₹48,50,000 exceeds floor limit'
    expect(translateReason(r2, 'hinglish')).toBe('₹48,50,000 ki raqam floor limit se zyada hai')
    expect(translateReason(r2, 'hi')).toBe('₹48,50,000 की राशि सीमा से अधिक है')

    const r3 = 'Voice not verified by Seal'
    expect(translateReason(r3, 'hinglish')).toBe('Awaaz Seal se verified nahi')
    expect(translateReason(r3, 'hi')).toBe('आवाज़ सील से सत्यापित नहीं')

    const r4 = 'This payment is ₹48,50,000 to ACME Corp.'
    expect(translateReason(r4, 'hinglish')).toBe('Yeh payment ₹48,50,000 ACME Corp ke liye hai.')
    expect(translateReason(r4, 'hi')).toBe('यह भुगतान ₹48,50,000 ACME Corp के लिए है।')
  })

  it('translates headlines and section titles without leaving English text', () => {
    expect(translateHeadline('Pause before you pay.', 'hinglish')).toBe('Paise bhejne se pehle ek second ruko.')
    expect(translateHeadline('Pause before you pay.', 'hi')).toBe('पैसे भेजने से पहले एक पल रुकिए।')

    expect(translateHeadline('Verify first.', 'hinglish')).toBe('Pehle verify karo.')
    expect(translateHeadline('Verify first.', 'hi')).toBe('पहले पुष्टि करें।')

    expect(translateSectionTitle('1930 Helpline Packet', 'hi')).toBe('1930 हेल्पलाइन पैकेट')
    expect(translateSectionTitle('Bank Freeze Letter', 'hi')).toBe('बैंक फ़्रीज़ पत्र')
    expect(translateSectionTitle('CERT-In Incident Report', 'hi')).toBe('सर्ट-इन घटना रिपोर्ट')
  })

  it('translates toast messages and raw English phrases into Hinglish and Hindi', () => {
    expect(translateToast('toast.sleep', 'hinglish')).toBe('So raha hoon. Kuch nahi sun raha.')
    expect(translateToast('toast.sleep', 'hi')).toBe('सो रहा हूँ। कुछ नहीं सुन रहा।')

    expect(translateToast('Clipboard is empty — copy an email or message first.', 'hinglish')).toBe(
      'Clipboard khali hai — pehle email ya message copy karein.',
    )
    expect(translateToast('Clipboard is empty — copy an email or message first.', 'hi')).toBe(
      'क्लिपबोर्ड खाली है — पहले ईमेल या संदेश कॉपी करें।',
    )

    expect(translateToast('I stopped listening: timeout.', 'hinglish')).toContain('Maine sunna band kiya:')
    expect(translateToast('I stopped listening: timeout.', 'hi')).toContain('मैंने सुनना बंद किया:')
  })

  it('contains no emojis in any translation string (anti-slop rule MASCOT_SPEC §7)', () => {
    // Unicode regex for common emojis
    const emojiRegex = /\p{Extended_Pictographic}/u
    const keys = [
      'consent.title',
      'consent.body',
      'call.title',
      'call.body',
      'alert.title',
      'alert.body',
      'file.title',
      'file.body',
      'oob.wait',
      'oob.wait.badge',
      'oob.approved',
      'oob.not_requested',
      'oob.expired',
      'scribe.ask',
      'scribe.writing',
      'scribe.done',
      'scribe.body.done',
      'scribe.body.writing',
      'toast.sleep',
      'toast.off',
      'toast.capture_error',
    ]

    for (const key of keys) {
      for (const lang of ['en', 'hinglish', 'hi'] as Lang[]) {
        const text = t(key, lang, { name: 'test.pdf', approver: 'Approver', chips: 'OTP' })
        expect(emojiRegex.test(text)).toBe(false)
      }
    }
  })
})

