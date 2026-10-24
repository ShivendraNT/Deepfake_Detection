/**
 * mockLive.ts — the browser rehearsal of a live call (`npm run dev:web`).
 *
 * A scripted "deepfake CFO" call whose captions, highlight spans, chips and relayed band mirror
 * what the real local engine produced for the same script (see docs/finale/LIVE_DEMO.md).
 * It is a UI fixture: the band below is copied from that real run, never computed here.
 */

import type {
  AskQuote,
  CaptionLine,
  HealthInfo,
  ScreenFinding,
  TranscriptHighlight,
} from '../../../shared/contracts'

export interface MockCaption {
  at_ms: number
  text: string
  highlights: Array<[kind: 'ask' | 'cue', code: string, needle: string]>
}

export const MOCK_CALL: MockCaption[] = [
  {
    at_ms: 3600,
    text: "Hi Priya, this is Rajesh. I am stuck in a board meeting so I can't talk long.",
    highlights: [
      ['cue', 'UNREACHABLE', 'I am stuck in a board meeting'],
      ['cue', 'UNREACHABLE', "can't talk long"],
    ],
  },
  {
    at_ms: 8600,
    text: 'We are closing a confidential acquisition today. I need you to transfer 48 lakh rupees to a new escrow account.',
    highlights: [
      ['ask', 'A4', 'confidential'],
      ['cue', 'AMOUNT', '48 lakh rupees'],
      ['ask', 'A1', 'new escrow account'],
    ],
  },
  {
    at_ms: 13600,
    text: "I will send you the account details on chat. Please don't loop in Arjun, keep this between us.",
    highlights: [
      ['ask', 'A1', 'account details on chat'],
      ['ask', 'A4', "don't loop in Arjun"],
      ['ask', 'A4', 'keep this between us'],
    ],
  },
  {
    at_ms: 17400,
    text: 'Skip the usual approval, I will sign it off later.',
    highlights: [
      ['ask', 'A5', 'Skip the usual approval'],
      ['ask', 'A5', 'I will sign it off later'],
    ],
  },
]

export function captionFor(step: MockCaption, index: number): CaptionLine {
  const spans: TranscriptHighlight[] = []
  for (const [kind, code, needle] of step.highlights) {
    const start = step.text.indexOf(needle)
    if (start >= 0) spans.push({ kind, code, start, end: start + needle.length })
  }
  return {
    id: `mock_line_${index}`,
    text: step.text,
    t_start_s: Math.max(0, step.at_ms / 1000 - 4),
    t_end_s: step.at_ms / 1000 - 0.8,
    spans,
    latency_ms: 790,
  }
}

/** Quotes the backend would attach, first span per ask code. */
export function quotesUntil(index: number): AskQuote[] {
  const seen = new Map<string, AskQuote>()
  MOCK_CALL.slice(0, index + 1).forEach((step) => {
    for (const [kind, code, needle] of step.highlights) {
      if (kind === 'ask' && !seen.has(code)) {
        seen.set(code, { code: code as AskQuote['code'], text: needle, at_s: step.at_ms / 1000 - 4 })
      }
    }
  })
  return [...seen.values()]
}

export const MOCK_HEALTH: HealthInfo = {
  backend: true,
  asr: {
    engine: 'mock',
    model: 'browser rehearsal',
    ready: true,
    error: null,
    warmup_ms: 0,
    last_latency_ms: 790,
    language: 'en',
  },
  voice_model: false,
  video: { ready: true, error: null, model: 'rehearsal', calibrated: false },
  vendors: 5,
  oob_url: 'http://127.0.0.1:8000/oob',
}

export const MOCK_SCREEN_FINDING: ScreenFinding = {
  app: 'Gmail — Google Chrome',
  meeting: null,
  asks: [
    { code: 'A7', text: 'Updated bank details', at_s: null },
    { code: 'A4', text: 'Keep this confidential', at_s: null },
  ],
  cues: [],
  accounts_masked: ['••••7788'],
  unknown_accounts_masked: ['••••7788'],
  vendors: ['Narmada Demo Logistics LLP'],
  suspicious: true,
}
