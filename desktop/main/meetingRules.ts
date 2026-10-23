/** Pure window-title rules for the meeting notice (unit-tested; no Electron imports). */

import type { MeetingInfo } from '../shared/contracts'

interface Rule {
  app: string
  test: RegExp
}

const RULES: Rule[] = [
  // Chrome/Edge/Brave/Arc show the active tab title: "Meet - abc-defg-hij" or "Meet – <name>".
  // The Meet home page ("Google Meet") is not a call, so only the in-call title counts.
  { app: 'Google Meet', test: /^Meet\s*[-–—]\s*(?!Google Chrome|Microsoft Edge|Brave|Arc)\S/i },
  { app: 'Zoom', test: /\bZoom\s+(Meeting|Webinar)\b/i },
  { app: 'Microsoft Teams', test: /\b(meeting|call)\b.*\|\s*Microsoft Teams|Microsoft Teams.*\b(meeting|call)\b/i },
  { app: 'WhatsApp', test: /WhatsApp.*\b(voice|video)?\s*call\b|\b(voice|video) call\b.*WhatsApp/i },
  { app: 'Webex', test: /\bWebex\b.*\b(meeting|call)\b|Cisco Webex Meetings/i },
  { app: 'Slack huddle', test: /\bHuddle\b.*Slack|Slack.*\bHuddle\b/i },
  { app: 'Skype', test: /\bSkype\b.*\bcall\b/i },
  { app: 'Jitsi Meet', test: /\bJitsi Meet\b/i },
]

/** Never treat our own windows (or the Notebook) as a meeting. */
const OWN = /\bSatya\b|Satyapan/i

/** Pure: the first window name that looks like an active call, or null. */
export function detectMeeting(windowNames: string[]): MeetingInfo | null {
  for (const raw of windowNames) {
    const title = raw.trim()
    if (!title || OWN.test(title)) continue
    for (const rule of RULES) {
      if (rule.test.test(title)) return { app: rule.app, title: title.slice(0, 120) }
    }
  }
  return null
}

export function sameMeeting(a: MeetingInfo | null, b: MeetingInfo | null): boolean {
  if (a === null || b === null) return a === b
  return a.app === b.app && a.title === b.title
}

