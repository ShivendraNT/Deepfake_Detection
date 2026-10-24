import { describe, expect, it } from 'vitest'

import { detectMeeting, sameMeeting } from '../main/meetingRules'

describe('meeting notice from window names', () => {
  it('recognises the common call apps', () => {
    expect(detectMeeting(['Meet - abc-defg-hij - Google Chrome'])?.app).toBe('Google Meet')
    expect(detectMeeting(['Meet – Weekly vendor sync - Microsoft Edge'])?.app).toBe('Google Meet')
    expect(detectMeeting(['Zoom Meeting'])?.app).toBe('Zoom')
    expect(detectMeeting(['Meeting with Rajesh Iyer | Microsoft Teams'])?.app).toBe('Microsoft Teams')
    expect(detectMeeting(['WhatsApp Voice Call'])?.app).toBe('WhatsApp')
  })

  it('ignores home pages, ordinary windows and our own windows', () => {
    expect(detectMeeting(['Google Meet - Google Chrome'])).toBeNull()
    expect(detectMeeting(['Inbox (3) - priya@demo.example - Gmail - Google Chrome', 'Zoom Workplace'])).toBeNull()
    expect(detectMeeting(['Satya — Notebook', 'Satya says'])).toBeNull()
    expect(detectMeeting(['Meet - Google Chrome'])).toBeNull()
  })

  it('compares meetings by app and title', () => {
    const a = { app: 'Zoom', title: 'Zoom Meeting' }
    expect(sameMeeting(a, { ...a })).toBe(true)
    expect(sameMeeting(a, null)).toBe(false)
    expect(sameMeeting(null, null)).toBe(true)
  })
})
