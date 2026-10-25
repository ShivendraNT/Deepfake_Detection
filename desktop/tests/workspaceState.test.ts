import * as React from 'react'
import { renderToString } from 'react-dom/server'
import { beforeAll, describe, expect, it } from 'vitest'

import type {
  CompanionEvent,
  CompanionPayload,
  CompanionState,
} from '../shared/contracts'
import { EMPTY_LIVE, mergeState, reduceLive } from '../renderer/src/workspace/lib/live'
import { satyaStatus } from '../renderer/src/workspace/lib/status'

function state(overrides: Partial<CompanionState> = {}): CompanionState {
  return {
    version: '1',
    mode: 'SLEEP',
    hidden: false,
    monitoring: false,
    session_id: null,
    consent_id: null,
    source: null,
    source_label: null,
    started_at: null,
    updated_at: '2026-10-25T00:00:00Z',
    expires_at: null,
    demo: false,
    mode_label: null,
    last_event_id: null,
    policy_authority: 'satyapan.policy',
    raw_scores_visible: false,
    manual_only: true,
    ...overrides,
  }
}

function event(
  type: CompanionEvent['type'],
  payload: Partial<CompanionPayload> = {},
): CompanionEvent {
  const full: CompanionPayload = {
    state: 'ACTIVE',
    mascot_mood: 'attentive',
    headline: 'test',
    explanation: '',
    band: null,
    reason_codes: [],
    info_codes: [],
    evidence_ids: [],
    next_actions: [],
    monitoring: false,
    source: null,
    mode_label: null,
    demo: false,
    ...payload,
  }
  return {
    version: '1',
    event_id: 'evt_00000001',
    type,
    session_id: 'session_1',
    occurred_at: '2026-10-25T00:00:00Z',
    payload: full,
  }
}

beforeAll(() => {
  ;(globalThis as unknown as { React: unknown }).React = React
  if (typeof globalThis.window === 'undefined') {
    const win = {
      location: { search: '', href: 'http://localhost:5174/?view=workspace' },
      addEventListener: () => {},
      removeEventListener: () => {},
      localStorage: {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
      },
    }
    ;(globalThis as unknown as { window: unknown }).window = win
    ;(globalThis as unknown as { localStorage: unknown }).localStorage = win.localStorage
  }
})

describe('Notebook status follows the six CompanionModes', () => {
  it('maps every mode and the live call snapshot', () => {
    expect(satyaStatus(null, EMPTY_LIVE).key).toBe('sleeping')
    expect(satyaStatus(state({ mode: 'SLEEP' }), EMPTY_LIVE).key).toBe('sleeping')
    expect(
      satyaStatus(state({ mode: 'ACTIVE', session_id: 'session_1' }), EMPTY_LIVE).key,
    ).toBe('watching')
    expect(
      satyaStatus(state({ mode: 'ACTIVE', session_id: 'session_1' }), {
        ...EMPTY_LIVE,
        callId: 'call_1',
      }).key,
    ).toBe('listening')
    expect(
      satyaStatus(state({ mode: 'ALERT', session_id: 'session_1' }), EMPTY_LIVE).key,
    ).toBe('alert')
    expect(
      satyaStatus(state({ mode: 'INVESTIGATING', session_id: 'session_1' }), EMPTY_LIVE).key,
    ).toBe('checking')
    expect(
      satyaStatus(state({ mode: 'SCRIBE', session_id: 'session_1' }), EMPTY_LIVE).key,
    ).toBe('writing')
    expect(satyaStatus(state({ mode: 'DISABLED' }), EMPTY_LIVE).key).toBe('off')
  })

  it('treats alert/checking/writing as active, not sleeping', () => {
    for (const mode of ['ALERT', 'INVESTIGATING', 'SCRIBE'] as const) {
      const status = satyaStatus(state({ mode, session_id: 'session_1' }), EMPTY_LIVE)
      expect(status.active).toBe(true)
      expect(status.sessionActive).toBe(true)
    }
    expect(satyaStatus(state({ mode: 'DISABLED' }), EMPTY_LIVE).active).toBe(false)
  })
})

describe('event merge never invents or clears session state', () => {
  it('does not clear monitoring on a live.chips event', () => {
    const before = state({ mode: 'ACTIVE', monitoring: true, session_id: 'session_1' })
    const after = mergeState(
      before,
      event('live.chips', { state: 'ACTIVE', monitoring: false, headline: 'chips' }),
    )
    expect(after?.monitoring).toBe(true)
    expect(after?.mode).toBe('ACTIVE')
  })

  it('clears monitoring on call.stopped', () => {
    const before = state({ mode: 'ACTIVE', monitoring: true, session_id: 'session_1' })
    const after = mergeState(
      before,
      event('call.stopped', { state: 'ACTIVE', monitoring: false, headline: 'stopped' }),
    )
    expect(after?.monitoring).toBe(false)
    expect(after?.mode).toBe('ACTIVE')
  })

  it('resets the live snapshot on session.stopped', () => {
    const live = { ...EMPTY_LIVE, callId: 'call_1', callStartedAt: '2026-10-25T00:00:00Z' }
    const after = reduceLive(
      live,
      event('session.stopped', { state: 'SLEEP', monitoring: false, headline: 'sleep' }),
    )
    expect(after.callId).toBeNull()
    expect(after.callStartedAt).toBeNull()
  })
})

describe('NowTab renders the actual mode, not a generic sleeping panel', () => {
  async function renderNow(overrides: Partial<CompanionState>) {
    const { default: NowTab } = await import('../renderer/src/workspace/tabs/NowTab')
    return renderToString(
      React.createElement(NowTab, {
        state: state(overrides),
        live: EMPTY_LIVE,
        onOpenCase: () => {},
      }),
    )
  }

  it('shows an alert panel for ALERT', async () => {
    const html = await renderNow({ mode: 'ALERT', session_id: 'session_1' })
    expect(html).toContain('An alert is open.')
    expect(html).not.toContain('Wake Satya')
  })

  it('shows checking for INVESTIGATING and writing for SCRIBE', async () => {
    const checking = await renderNow({ mode: 'INVESTIGATING', session_id: 'session_1' })
    expect(checking).toContain('Checking the evidence now.')
    expect(checking).not.toContain('Wake Satya')
    const writing = await renderNow({ mode: 'SCRIBE', session_id: 'session_1' })
    expect(writing).toContain('Writing a draft.')
    expect(writing).not.toContain('Wake Satya')
  })

  it('shows off and sleeping correctly', async () => {
    const off = await renderNow({ mode: 'DISABLED' })
    expect(off).toContain('Satya is off.')
    expect(off).toContain('Turn on')
    const sleeping = await renderNow({ mode: 'SLEEP' })
    expect(sleeping).toContain('Wake Satya')
  })
})
