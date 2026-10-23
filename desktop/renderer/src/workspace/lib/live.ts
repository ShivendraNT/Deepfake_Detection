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

/** Merge event-relayed fields into the last full state envelope. */
export function mergeState(
  previous: CompanionState | null,
  event: CompanionEvent,
): CompanionState | null {
  if (!previous) return previous
  return {
    ...previous,
    mode: event.payload.state,
    monitoring: event.payload.monitoring,
    source: event.payload.source ?? previous.source,
    mode_label: event.payload.mode_label ?? previous.mode_label,
    updated_at: event.occurred_at,
    last_event_id: event.event_id,
  }
}
