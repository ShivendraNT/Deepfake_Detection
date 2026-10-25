/**
 * Reducers for the Notebook's live panel.
 *
 * They only relay fields that the companion API already published. A band is copied from the
 * event; it is never inferred from a reason code or a detector value.
 */

import type {
  AskChip,
  Band,
  CompanionEvent,
  CompanionState,
  Coverage,
  SealStatus,
} from '../../../../shared/contracts'

export interface LastAlert {
  band: Band
  headline: string
  caseId: string | null
  at: string
}

export interface LiveSnapshot {
  callStartedAt: string | null
  callId: string | null
  chips: AskChip[]
  coverage: Coverage | null
  seal: SealStatus | null
  lastAlert: LastAlert | null
  /** Band the policy relayed for the call in progress (reset per call). */
  callBand: Band | null
}

export const EMPTY_LIVE: LiveSnapshot = {
  callStartedAt: null,
  callId: null,
  chips: [],
  coverage: null,
  seal: null,
  lastAlert: null,
  callBand: null,
}

export function reduceLive(previous: LiveSnapshot, event: CompanionEvent): LiveSnapshot {
  const payload = event.payload
  const next: LiveSnapshot = {
    ...previous,
    chips: payload.chips ?? previous.chips,
    coverage: payload.coverage ?? previous.coverage,
    seal: payload.seal ?? previous.seal,
  }

  switch (event.type) {
    case 'call.started':
      return {
        ...next,
        callStartedAt: event.occurred_at,
        callId: payload.call_id ?? previous.callId,
        callBand: null,
      }
    case 'call.stopped':
    case 'session.stopped':
      return {
        ...next,
        callStartedAt: null,
        callId: null,
        chips: [],
        coverage: null,
        seal: null,
        callBand: null,
      }
    case 'live.chips':
      return {
        ...next,
        callStartedAt: previous.callStartedAt ?? event.occurred_at,
        callId: payload.call_id ?? previous.callId,
      }
    case 'alert.raised':
      return {
        ...next,
        callBand: previous.callId && payload.band ? payload.band : previous.callBand,
        lastAlert: payload.band
          ? {
              band: payload.band,
              headline: payload.headline,
              caseId: payload.case_id ?? null,
              at: event.occurred_at,
            }
          : previous.lastAlert,
      }
    default:
      return next
  }
}

/**
 * Events that may change the session/capture fields. Other events (`live.chips`,
 * `coverage.changed`, `oob.*`, `report.ready`) are about one case or one call and must not
 * clear `monitoring` just because their payload defaults it to false.
 */
const STATEFUL_EVENTS = new Set([
  'session.started',
  'session.stopped',
  'state.changed',
  'call.started',
  'call.stopped',
  'analysis.started',
  'analysis.completed',
  'alert.raised',
  'case.updated',
  'draft.ready',
])

/**
 * Optimistic merge from an event. This is never the authority: the Workspace also refreshes
 * `/companion/state` after each event, so session_id/consent_id/expiry/source_label come from
 * the backend snapshot, not from a partial payload.
 */
export function mergeState(
  previous: CompanionState | null,
  event: CompanionEvent,
): CompanionState | null {
  if (!previous) return previous
  const payload = event.payload
  const stateful = STATEFUL_EVENTS.has(event.type)
  return {
    ...previous,
    mode: payload.state,
    monitoring: stateful ? payload.monitoring : previous.monitoring,
    source: stateful ? (payload.source ?? previous.source) : previous.source,
    mode_label: stateful ? (payload.mode_label ?? previous.mode_label) : previous.mode_label,
    demo: stateful ? payload.demo : previous.demo,
    updated_at: event.occurred_at,
    last_event_id: event.event_id,
  }
}
