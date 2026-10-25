/**
 * The Notebook's single source of truth for "what is Satya doing right now?".
 *
 * The backend has six CompanionModes; the UI used to treat only ACTIVE as awake, so ALERT,
 * INVESTIGATING and SCRIBE fell back to "Sleeping". This maps every mode (plus the live call
 * snapshot) to one label, description and tone, and is used by the header, sidebar, Now tab and
 * Privacy tab. It never computes or changes a band.
 */

import type { CompanionState } from '../../../../shared/contracts'
import type { LiveSnapshot } from './live'

export type SatyaStatusKey =
  | 'sleeping'
  | 'watching'
  | 'listening'
  | 'checking'
  | 'alert'
  | 'writing'
  | 'off'

export interface SatyaStatus {
  key: SatyaStatusKey
  label: string
  detail: string
  /** Satya is doing something (not asleep and not off). */
  active: boolean
  /** A consented session exists; this is what "Notice calls" follows. */
  sessionActive: boolean
  /** A call is actually being listened to (call id from the event stream). */
  listening: boolean
}

export function satyaStatus(
  state: CompanionState | null,
  live: LiveSnapshot,
): SatyaStatus {
  const mode = state?.mode ?? 'SLEEP'
  const listening = live.callId !== null || live.callStartedAt !== null
  const sessionActive = Boolean(state?.session_id)

  if (mode === 'DISABLED') {
    return {
      key: 'off',
      label: 'Off',
      detail: 'Satya is off. Nothing is being watched.',
      active: false,
      sessionActive,
      listening: false,
    }
  }
  if (mode === 'ALERT') {
    return {
      key: 'alert',
      label: 'Alert',
      detail: 'An alert is open. The band comes only from the policy engine.',
      active: true,
      sessionActive,
      listening,
    }
  }
  if (mode === 'INVESTIGATING') {
    return {
      key: 'checking',
      label: 'Checking',
      detail: 'Checking the evidence now. The band comes only from the policy engine.',
      active: true,
      sessionActive,
      listening,
    }
  }
  if (mode === 'SCRIBE') {
    return {
      key: 'writing',
      label: 'Writing',
      detail: 'Writing a draft. You review it and submit it yourself.',
      active: true,
      sessionActive,
      listening,
    }
  }
  if (listening) {
    return {
      key: 'listening',
      label: 'Listening',
      detail: 'Listening to this call only. Captions stay in memory and vanish when it ends.',
      active: true,
      sessionActive: true,
      listening: true,
    }
  }
  if (mode === 'ACTIVE' || sessionActive) {
    return {
      key: 'watching',
      label: 'Watching',
      detail: 'Watching. I notice calls and ask before I listen.',
      active: true,
      sessionActive,
      listening: false,
    }
  }
  return {
    key: 'sleeping',
    label: 'Sleeping',
    detail: 'Satya is asleep. Nothing is being watched.',
    active: false,
    sessionActive: false,
    listening: false,
  }
}

/** Theme token name for the status dot. Components map it through `tone`. */
export function statusTone(key: SatyaStatusKey): 'watch' | 'coral' | 'amber' | 'write' | 'slate' {
  switch (key) {
    case 'alert':
      return 'coral'
    case 'checking':
      return 'amber'
    case 'writing':
      return 'write'
    case 'watching':
    case 'listening':
      return 'watch'
    default:
      return 'slate'
  }
}
