import { describe, expect, it } from 'vitest'

import { analyzeScreenText } from '../main/screen'

describe('Screen Guard analysis', () => {
  it('detects urgency and bank change combination as suspicious', () => {
    const text = `
      From: Rajesh CFO <rajesh@example.com>
      URGENT: Please process payment to our new bank account right away.
      New account: 999901234567, IFSC: FAKC0001234.
      Keep it confidential until the audit concludes.
    `
    const result = analyzeScreenText(text)
    expect(result.suspicious).toBe(true)
    expect(result.matches).toContain('Urgent secrecy request')
    expect(result.matches).toContain('Bank account change instruction')
    expect(result.preview).toContain('••••4567')
  })

  it('detects approval bypass attempt', () => {
    const text = `
      Please bypass normal approval for this wire.
      CFO is traveling and authorized directly. Don't call them today.
    `
    const result = analyzeScreenText(text)
    expect(result.suspicious).toBe(true)
    expect(result.headline).toBe('Urgent payment bypass on screen')
  })

  it('detects remote access scam software on screen', () => {
    const text = `
      Bank Support: Please download AnyDesk or TeamViewer so we can assist with your refund.
    `
    const result = analyzeScreenText(text)
    expect(result.suspicious).toBe(true)
    expect(result.headline).toBe('Remote access scam risk on screen')
  })

  it('considers normal work text safe', () => {
    const text = `
      Quarterly review meeting scheduled for tomorrow at 11 AM.
      Please bring the slide deck and notes.
    `
    const result = analyzeScreenText(text)
    expect(result.suspicious).toBe(false)
    expect(result.headline).toBe('Screen looks OK')
  })
})

