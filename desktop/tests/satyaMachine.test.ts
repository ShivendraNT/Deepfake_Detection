import { describe, expect, it } from 'vitest'

import type {
  AskChip,
  CompanionEvent,
  CompanionEventType,
  CompanionMode,
  CompanionPayload,
  OobTicket,
} from '../shared/contracts'
import {
  fileKindOf,
  initialSatyaState,
  satyaReducer,
  type SatyaState,
} from '../renderer/src/companion/satyaMachine'

let sequence = 0

function event(
  type: CompanionEventType,
  payload: Partial<CompanionPayload> & Pick<CompanionPayload, 'state' | 'headline'>,
): CompanionEvent {
  sequence += 1
  const full: CompanionPayload = {
    mascot_mood: 'attentive',
    explanation: '',
    band: null,
    reason_codes: [],
    info_codes: [],
    evidence_ids: [],
    next_actions: [],
    monitoring: true,
    source: null,
    mode_label: null,
    demo: true,
    ...payload,
  }
  return {
    version: '1',
    event_id: `evt_test_${String(sequence).padStart(4, '0')}`,
    type,
    session_id: 'session_test',
    occurred_at: '2026-10-24T10:12:00.000Z',
    payload: full,
  }
}

const CHIPS: AskChip[] = [
  { code: 'A1', at_s: 3 },
  { code: 'A4', at_s: 7 },
]

const TICKET: OobTicket = {
  oob_id: 'oob_test',
  case_id: 'case_test',
  approver_name: 'Demo Rajesh',
  channel: 'console',
  inbox_url: '/oob/inbox/demo',
  expires_at: '2026-10-24T10:17:00.000Z',
}

function stateFrom(actions: Parameters<typeof satyaReducer>[1][]): SatyaState {
  return actions.reduce(satyaReducer, initialSatyaState)
}

function watching(): SatyaState {
  return satyaReducer(initialSatyaState, { type: 'SET_MODE', mode: 'WATCHING' })
}

describe('satyaMachine — start and modes', () => {
  it('launches asleep and captures nothing', () => {
    expect(initialSatyaState).toEqual({
      userMode: 'SLEEPING',
      pose: 'sleep',
      card: null,
      caseId: null,
      callId: null,
      chips: [],
      lastBand: null,
      dismissed: false,
    })
  })

  it('wakes on SET_MODE WATCHING', () => {
    const state = watching()
    expect(state.userMode).toBe('WATCHING')
    expect(state.pose).toBe('idle')
    expect(state.card).toBeNull()
  })

  it('does not reset an active call when WATCHING is sent again', () => {
    const inCall = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('call.started', { state: 'ACTIVE', headline: 'Call', call_id: 'call_1' }) },
    ])
    expect(satyaReducer(inCall, { type: 'SET_MODE', mode: 'WATCHING' })).toBe(inCall)
  })

  it('clears transient state when sleeping or off', () => {
    const alert = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('alert.raised', { state: 'ALERT', headline: 'Pause', band: 'HOLD' }) },
    ])
    const asleep = satyaReducer(alert, { type: 'SET_MODE', mode: 'SLEEPING' })
    expect(asleep).toMatchObject({ userMode: 'SLEEPING', pose: 'sleep', card: null, callId: null, chips: [] })
    const off = satyaReducer(asleep, { type: 'SET_MODE', mode: 'OFF' })
    expect(off).toMatchObject({ userMode: 'OFF', pose: 'off', card: null, callId: null })
  })

  it('Sleeping ignores call hints and live events', () => {
    const hint = satyaReducer(initialSatyaState, { type: 'CALL_HINT', hintId: 'h1', source: 'loopback' })
    expect(hint).toBe(initialSatyaState)
    const live = satyaReducer(initialSatyaState, {
      type: 'EVENT',
      event: event('live.chips', { state: 'ACTIVE', headline: 'chips', chips: CHIPS }),
    })
    expect(live).toBe(initialSatyaState)
  })
})

describe('satyaMachine — calls and hints', () => {
  it('shows a call ask on a hint while Watching', () => {
    const state = satyaReducer(watching(), { type: 'CALL_HINT', hintId: 'h1', source: 'loopback' })
    expect(state.pose).toBe('idle')
    expect(state.card).toMatchObject({ kind: 'call_ask', source: 'loopback', id: 'call_ask_h1' })
  })

  it('ignores hints while a card or call is already open', () => {
    const asked = satyaReducer(watching(), { type: 'CALL_HINT', hintId: 'h1', source: 'loopback' })
    expect(satyaReducer(asked, { type: 'CALL_HINT', hintId: 'h2', source: 'loopback' })).toBe(asked)
  })

  it('enters listening and builds a live card on call.started', () => {
    const state = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      {
        type: 'EVENT',
        event: event('call.started', {
          state: 'ACTIVE',
          headline: 'Sounds like a call.',
          call_id: 'call_1',
          case_id: 'case_1',
          coverage: 'usable',
          seal: 'not_verified',
        }),
      },
    ])
    expect(state.pose).toBe('listen')
    expect(state.callId).toBe('call_1')
    expect(state.caseId).toBe('case_1')
    expect(state.card).toMatchObject({ kind: 'live', coverage: 'usable', seal: 'not_verified' })
  })

  it('merges live chips and patches coverage without replacing an alert', () => {
    const listening = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('call.started', { state: 'ACTIVE', headline: 'Call', call_id: 'call_1' }) },
      { type: 'EVENT', event: event('live.chips', { state: 'ACTIVE', headline: 'chips', call_id: 'call_1', chips: CHIPS }) },
      {
        type: 'EVENT',
        event: event('coverage.changed', { state: 'ACTIVE', headline: 'coverage', call_id: 'call_1', coverage: 'degraded' }),
      },
    ])
    expect(listening.chips).toEqual(CHIPS)
    expect(listening.card).toMatchObject({ kind: 'live', coverage: 'degraded' })

    const alert = satyaReducer(listening, {
      type: 'EVENT',
      event: event('alert.raised', { state: 'ALERT', headline: 'Pause', band: 'VERIFY', chips: CHIPS }),
    })
    const afterChips = satyaReducer(alert, {
      type: 'EVENT',
      event: event('live.chips', { state: 'ACTIVE', headline: 'more', call_id: 'call_1', chips: [{ code: 'A2', at_s: 9 }] }),
    })
    expect(afterChips.card?.kind).toBe('alert')
    expect(afterChips.chips.map((chip) => chip.code)).toEqual(['A1', 'A4', 'A2'])
  })

  it('keeps the alert after the call stops, but clears the call id', () => {
    const alert = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('call.started', { state: 'ACTIVE', headline: 'Call', call_id: 'call_1' }) },
      { type: 'EVENT', event: event('alert.raised', { state: 'ALERT', headline: 'Pause', band: 'HOLD' }) },
      { type: 'EVENT', event: event('call.stopped', { state: 'ACTIVE', headline: 'Call ended' }) },
    ])
    expect(alert.callId).toBeNull()
    expect(alert.card?.kind).toBe('alert')
    expect(alert.pose).toBe('alert')
  })
})

describe('satyaMachine — files', () => {
  it('catches on hover and returns to idle on leave', () => {
    expect(satyaReducer(watching(), { type: 'FILE_HOVER', active: true }).pose).toBe('catch')
    const caught = satyaReducer(watching(), { type: 'FILE_HOVER', active: true })
    expect(satyaReducer(caught, { type: 'FILE_HOVER', active: false }).pose).toBe('idle')
  })

  it('ignores file hover and drop while asleep', () => {
    expect(satyaReducer(initialSatyaState, { type: 'FILE_HOVER', active: true }).pose).toBe('sleep')
    const dropped = satyaReducer(initialSatyaState, {
      type: 'FILE_DROP',
      fileId: 'f1',
      name: 'Invoice.pdf',
      kind: 'pdf',
    })
    expect(dropped).toBe(initialSatyaState)
  })

  it('asks before reading a dropped file', () => {
    const state = satyaReducer(watching(), {
      type: 'FILE_DROP',
      fileId: 'f1',
      name: 'Invoice_Oct.pdf',
      kind: 'pdf',
    })
    expect(state.pose).toBe('think')
    expect(state.card).toMatchObject({
      kind: 'file_ask',
      id: 'file_ask_f1',
      file_name: 'Invoice_Oct.pdf',
      file_kind: 'pdf',
    })
  })

  it('infers file kinds without reading the file', () => {
    expect(fileKindOf('a.pdf')).toBe('pdf')
    expect(fileKindOf('note.m4a')).toBe('audio')
    expect(fileKindOf('mail.eml')).toBe('email')
    expect(fileKindOf('shot.PNG')).toBe('image')
    expect(fileKindOf('notes.txt')).toBe('text')
  })
})

describe('satyaMachine — alerts, results and OOB', () => {
  it('copies the policy band and chips into an alert card', () => {
    const state = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      {
        type: 'EVENT',
        event: event('alert.raised', {
          state: 'ALERT',
          headline: 'Pause before you pay.',
          band: 'HOLD',
          chips: CHIPS,
          reason_codes: ['ASK_NEW_ACCOUNT'],
          next_actions: [{ id: 'verify_with_approver', label: 'Verify', variant: 'primary' }],
        }),
      },
    ])
    expect(state.pose).toBe('alert')
    expect(state.lastBand).toBe('HOLD')
    expect(state.dismissed).toBe(false)
    expect(state.card).toMatchObject({ kind: 'alert', band: 'HOLD', chips: CHIPS })
    expect(state.card?.kind === 'alert' ? state.card.actions[0].id : null).toBe('verify_with_approver')
  })

  it('re-opens an alert after a duplicate or a dismissal', () => {
    const alert = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('alert.raised', { state: 'ALERT', headline: 'Pause', band: 'HOLD' }) },
    ])
    const dismissed = satyaReducer(alert, {
      type: 'CARD_ACTION',
      cardId: (alert.card as { id: string }).id,
      actionId: 'close',
    })
    expect(dismissed.card).toBeNull()
    expect(dismissed.dismissed).toBe(true)
    const again = satyaReducer(dismissed, {
      type: 'EVENT',
      event: event('alert.raised', { state: 'ALERT', headline: 'Pause again', band: 'HOLD' }),
    })
    expect(again.card?.kind).toBe('alert')
    expect(again.dismissed).toBe(false)
  })

  it('never invents a band when the event has none', () => {
    const state = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('alert.raised', { state: 'ALERT', headline: 'Pause' }) },
    ])
    expect(state.pose).toBe('alert')
    expect(state.lastBand).toBeNull()
    expect(state.card).toBeNull()
  })

  it('relieves on PASS and alerts on VERIFY/HOLD', () => {
    const pass = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('analysis.completed', { state: 'ALERT', headline: 'Looks OK', band: 'PASS' }) },
    ])
    expect(pass.pose).toBe('relief')
    expect(pass.lastBand).toBe('PASS')
    expect(pass.card).toMatchObject({ kind: 'result', band: 'PASS' })

    const verify = satyaReducer(watching(), {
      type: 'EVENT',
      event: event('analysis.completed', { state: 'ALERT', headline: 'Verify first', band: 'VERIFY' }),
    })
    expect(verify.pose).toBe('alert')
    expect(verify.lastBand).toBe('VERIFY')
    expect(verify.card).toMatchObject({ kind: 'result', band: 'VERIFY' })
  })

  it('waits for OOB, then relieves or keeps the HOLD from the payload', () => {
    const waiting = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('oob.sent', { state: 'ALERT', headline: 'Waiting', band: 'HOLD', ticket: TICKET }) },
    ])
    expect(waiting.card).toMatchObject({ kind: 'oob_wait', approver_name: 'Demo Rajesh' })
    expect(waiting.pose).toBe('alert')

    const approved = satyaReducer(waiting, {
      type: 'EVENT',
      event: event('oob.result', {
        state: 'ALERT',
        headline: 'Approved',
        band: 'PASS',
        oob: { oob_id: 'oob_test', approver_name: 'Demo Rajesh', outcome: 'approved' },
      }),
    })
    expect(approved.pose).toBe('relief')
    expect(approved.lastBand).toBe('PASS')
    expect(approved.card).toMatchObject({ kind: 'oob_result', outcome: 'approved' })

    const rejected = satyaReducer(waiting, {
      type: 'EVENT',
      event: event('oob.result', {
        state: 'ALERT',
        headline: 'Not requested',
        band: 'HOLD',
        oob: { oob_id: 'oob_test', approver_name: 'Demo Rajesh', outcome: 'not_requested' },
      }),
    })
    expect(rejected.pose).toBe('alert')
    expect(rejected.lastBand).toBe('HOLD')
    expect(rejected.card).toMatchObject({ kind: 'oob_result', outcome: 'not_requested' })
  })
})

describe('satyaMachine — card actions, timers and purity', () => {
  it('ignores a stale card click', () => {
    const alert = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('alert.raised', { state: 'ALERT', headline: 'Pause', band: 'HOLD' }) },
    ])
    expect(satyaReducer(alert, { type: 'CARD_ACTION', cardId: 'not_the_card', actionId: 'close' })).toBe(alert)
  })

  it('walks away from a consent or call card', () => {
    const asked = satyaReducer(watching(), { type: 'CALL_HINT', hintId: 'h1', source: 'loopback' })
    const dismissed = satyaReducer(asked, {
      type: 'CARD_ACTION',
      cardId: (asked.card as { id: string }).id,
      actionId: 'not_this_call',
    })
    expect(dismissed.card).toBeNull()
    expect(dismissed.pose).toBe('idle')
    expect(dismissed.dismissed).toBe(true)
  })

  it('returns to idle only when the relief timer is current', () => {
    const pass = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('analysis.completed', { state: 'ALERT', headline: 'Looks OK', band: 'PASS' }) },
    ])
    const cardId = (pass.card as { id: string }).id
    const stale = satyaReducer(pass, { type: 'TIMER', name: 'relief', guardId: 'other' })
    expect(stale).toBe(pass)
    expect(satyaReducer(pass, { type: 'TIMER', name: 'relief', guardId: cardId }).pose).toBe('idle')
  })

  it('keeps listening after a relief timer when a call is still active', () => {
    const state = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('call.started', { state: 'ACTIVE', headline: 'Call', call_id: 'call_1' }) },
      { type: 'EVENT', event: event('analysis.completed', { state: 'ALERT', headline: 'Looks OK', band: 'PASS' }) },
    ])
    expect(satyaReducer(state, { type: 'TIMER', name: 'relief' }).pose).toBe('listen')
  })

  it('sleeps on a capture error and clears the call', () => {
    const state = stateFrom([
      { type: 'SET_MODE', mode: 'WATCHING' },
      { type: 'EVENT', event: event('call.started', { state: 'ACTIVE', headline: 'Call', call_id: 'call_1' }) },
      { type: 'EVENT', event: event('error', { state: 'SLEEP', headline: 'Audio device changed' }) },
    ])
    expect(state.userMode).toBe('SLEEPING')
    expect(state.pose).toBe('sleep')
    expect(state.callId).toBeNull()
    expect(state.card?.kind).toBe('toast')
  })

  it('is pure: it does not mutate or use hidden inputs', () => {
    const frozen = Object.freeze({
      ...watching(),
      chips: Object.freeze([...CHIPS]) as unknown as AskChip[],
    }) as SatyaState
    const snapshot = JSON.stringify(frozen)
    const next = satyaReducer(frozen, {
      type: 'EVENT',
      event: event('live.chips', { state: 'ACTIVE', headline: 'chips', call_id: 'call_1', chips: CHIPS }),
    })
    expect(JSON.stringify(frozen)).toBe(snapshot)
    expect(next).not.toBe(frozen)
  })

  it('ignores an unknown event type', () => {
    const state = watching()
    const unknown = { ...event('state.changed', { state: 'ACTIVE', headline: 'x' }), type: 'future.event' }
    expect(
      satyaReducer(state, {
        type: 'EVENT',
        event: unknown as unknown as CompanionEvent,
      }),
    ).toBe(state)
  })
})
