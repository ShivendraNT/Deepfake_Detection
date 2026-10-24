import { describe, expect, it } from 'vitest'

import type { CompanionEvent, CompanionPayload } from '../shared/contracts'
import { initialSatyaState, satyaReducer } from '../renderer/src/companion/satyaMachine'
import { t } from '../renderer/src/shared/copy'

function alertEvent(payload: Partial<CompanionPayload>): CompanionEvent {
  const full: CompanionPayload = {
    mascot_mood: 'attentive',
    explanation: '',
    band: 'HOLD',
    reason_codes: [],
    info_codes: [],
    evidence_ids: [],
    next_actions: [],
    monitoring: true,
    source: null,
    mode_label: null,
    demo: false,
    state: 'ALERT',
    headline: "Stop: don't pay or share any code on this call",
    ...payload,
  }
  return {
    version: '1',
    event_id: 'evt_personal_1',
    type: 'alert.raised',
    session_id: 'session_test',
    occurred_at: '2026-10-24T22:00:00.000Z',
    payload: full,
  }
}

describe('Consumer live journey: a person on their own call (no company approver)', () => {
  it('keeps the personal actions and no approver on the alert card', () => {
    // Satya starts asleep and ignores everything until consent; watching first.
    const watching = satyaReducer(initialSatyaState, { type: 'SET_MODE', mode: 'WATCHING' })
    const state = satyaReducer(watching, {
      type: 'EVENT',
      event: alertEvent({
        approver_name: null,
        next_actions: [
          { id: 'copy_reply', label: 'Copy a safe reply, then hang up', variant: 'primary' },
          { id: 'call_1930', label: 'Money sent? Call 1930', variant: 'outline' },
          { id: 'open_check', label: 'Prepare my report', variant: 'outline' },
        ],
      }),
    })
    expect(state.card).toMatchObject({ kind: 'alert', band: 'HOLD', approver: null })
    const ids = state.card?.kind === 'alert' ? state.card.actions.map((a) => a.id) : []
    expect(ids).toEqual(['copy_reply', 'call_1930', 'open_check'])
  })

  it('has the personal copy in English, Hinglish and Hindi', () => {
    for (const lang of ['en', 'hinglish', 'hi'] as const) {
      expect(t('alert.body.personal', lang)).not.toContain('alert.body')
      expect(t('action.call_1930', lang)).toContain('1930')
      expect(t('action.open_check', lang).length).toBeGreaterThan(3)
    }
    expect(t('alert.body.personal', 'en')).toContain('number you already have')
  })
})
