/**
 * Small pure formatters used across the Notebook.
 *
 * Nothing here knows about a policy decision. These helpers only format data that already
 * carries a band; they never compute or change one.
 */

import type { Band } from '../../../../shared/contracts'

const INR = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

export const BAND_WORD: Record<Band, string> = {
  PASS: 'Looks OK',
  VERIFY: 'Verify first',
  HOLD: 'On hold',
}

/** Whole rupees in Indian grouping, e.g. 4850000 -> "₹48,50,000". */
export function formatInr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || !Number.isFinite(amount)) return '—'
  return `₹${INR.format(Math.round(amount))}`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB'] as const
  let value = bytes / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`
}

/** Accounts are always shown masked. An already-masked value is left untouched. */
export function maskAccount(value: string | null | undefined): string {
  if (!value) return '—'
  if (value.includes('•') || value.includes('*')) return value
  const digits = value.replace(/\D/g, '')
  if (digits.length < 4) return value
  return `••••${digits.slice(-4)}`
}

/** Short hash for dense rows. The full value stays available through the copy button. */
export function shortHash(value: string, head = 10): string {
  if (value.length <= head + 1) return value
  return `${value.slice(0, head)}…`
}

export function formatDuration(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export function secondsSince(iso: string | null | undefined, now = Date.now()): number {
  if (!iso) return 0
  const at = new Date(iso).getTime()
  if (Number.isNaN(at)) return 0
  return Math.max(0, Math.floor((now - at) / 1000))
}

/** "just now", "2 min ago", "3 hrs ago", "yesterday", "24 Oct". */
export function relativeTime(iso: string, now = Date.now()): string {
  const at = new Date(iso).getTime()
  if (Number.isNaN(at)) return '—'
  const seconds = Math.max(0, Math.floor((now - at) / 1000))
  if (seconds < 45) return 'just now'
  if (seconds < 90) return '1 min ago'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} ${hours === 1 ? 'hr' : 'hrs'} ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return '—'
  return at.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return '—'
  return at.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

export interface TimelineGroup<T> {
  label: string
  items: T[]
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function bucketFor(at: Date, now: Date): string {
  const seconds = Math.max(0, Math.floor((now.getTime() - at.getTime()) / 1000))
  if (seconds < 120) return 'Just now'
  if (seconds < 3600) return 'Last hour'
  if (sameDay(at, now)) return 'Earlier today'
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (sameDay(at, yesterday)) return 'Yesterday'
  return at.toLocaleDateString('en-IN', { day: 'numeric', month: 'long' })
}

/** Newest first, grouped into calm relative-time buckets. */
export function groupTimeline<T extends { at: string }>(
  items: T[],
  now = Date.now(),
): TimelineGroup<T>[] {
  const sorted = [...items].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
  const nowDate = new Date(now)
  const groups = new Map<string, T[]>()
  for (const item of sorted) {
    const at = new Date(item.at)
    if (Number.isNaN(at.getTime())) continue
    const label = bucketFor(at, nowDate)
    const bucket = groups.get(label)
    if (bucket) bucket.push(item)
    else groups.set(label, [item])
  }
  return Array.from(groups, ([label, groupItems]) => ({ label, items: groupItems }))
}

const ACTION_LABELS: Record<string, string> = {
  'alert.raised': 'Alert raised',
  'analysis.completed': 'Check completed',
  'analysis.started': 'Check started',
  'call.started': 'Call detected',
  'call.stopped': 'Call ended',
  'case.updated': 'Case updated',
  'coverage.changed': 'Audio coverage changed',
  'demo.replay': 'Replay reviewed',
  'draft.ready': 'Draft prepared',
  'error': 'Something went wrong',
  'evidence.received': 'Evidence received',
  'live.chips': 'Payment trick noted',
  'oob.result': 'Approver answered',
  'oob.sent': 'Verification sent',
  'report.ready': 'Report pack ready',
  'session.started': 'Watching started',
  'session.stopped': 'Watching stopped',
  'state.changed': 'State changed',
}

export function actionLabel(action: string): string {
  const known = ACTION_LABELS[action]
  if (known) return known
  return action
    .replace(/[._]/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function channelLabel(channel: string): string {
  const labels: Record<string, string> = {
    audio: 'Voice note',
    call_audio: 'Call audio',
    email: 'Email',
    pdf: 'PDF',
    text: 'Text',
    whatsapp_text: 'WhatsApp text',
  }
  return labels[channel] ?? actionLabel(channel)
}
