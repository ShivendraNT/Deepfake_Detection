import {
  AlertTriangle,
  AudioLines,
  CheckCheck,
  Clock3,
  FileCheck2,
  FileText,
  FolderOpen,
  PhoneCall,
  PhoneOff,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  Smartphone,
  Square,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import type { CompanionEvent } from '../../../../shared/contracts'
import { loadAuditRows } from '../lib/data'
import { actionLabel, groupTimeline, relativeTime } from '../lib/format'
import Empty from '../ui/Empty'
import Section from '../ui/Section'
import { FONT_MONO, surface, tone } from '../ui/theme'

export interface TimelineTabProps {
  events: CompanionEvent[]
}

interface TimelineItem {
  id: string
  at: string
  actor: string
  action: string
  detail: string
  live: boolean
}

const ACTION_ICONS: Record<string, LucideIcon> = {
  'alert.raised': ShieldAlert,
  'analysis.completed': CheckCheck,
  'analysis.started': Search,
  'call.started': PhoneCall,
  'call.stopped': PhoneOff,
  'case.updated': FolderOpen,
  'coverage.changed': AudioLines,
  'demo.replay': RotateCcw,
  'draft.ready': FileText,
  'error': AlertTriangle,
  'evidence.received': FileCheck2,
  'live.chips': AudioLines,
  'oob.result': Smartphone,
  'oob.sent': Smartphone,
  'report.ready': FileText,
  'session.started': Play,
  'session.stopped': Square,
  'state.changed': RefreshCw,
}

function iconFor(action: string): LucideIcon {
  if (ACTION_ICONS[action]) return ACTION_ICONS[action]
  if (action.startsWith('alert')) return ShieldAlert
  if (action.startsWith('call')) return PhoneCall
  if (action.startsWith('report') || action.startsWith('draft')) return FileText
  return Clock3
}

function colorFor(action: string): string {
  if (action.startsWith('alert') || action === 'error') return tone.coral
  if (action.startsWith('oob')) return tone.watch
  if (action.startsWith('report') || action.startsWith('draft')) return tone.write
  return tone.slate
}

function eventToItem(event: CompanionEvent): TimelineItem {
  return {
    id: event.event_id,
    at: event.occurred_at,
    actor: 'Satya',
    action: event.type,
    detail:
      event.payload.headline || event.payload.explanation || 'Satya recorded this event locally.',
    live: true,
  }
}

export default function TimelineTab({ events }: TimelineTabProps): JSX.Element {
  const [audit, setAudit] = useState<TimelineItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let active = true
    setLoading(true)
    void loadAuditRows()
      .then((rows) => {
        if (!active) return
        setAudit(
          rows.map((row, index) => ({
            id: `audit-${index}-${row.at}-${row.action}`,
            at: row.at,
            actor: row.actor,
            action: row.action,
            detail: row.detail,
            live: false,
          })),
        )
        setError(null)
        setLoading(false)
      })
      .catch((reason: unknown) => {
        if (!active) return
        setError(reason instanceof Error ? reason.message : 'The audit log could not be loaded.')
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const items = useMemo(() => {
    const liveItems = events.map(eventToItem)
    const seen = new Set<string>()
    return [...audit, ...liveItems].filter((item) => {
      if (seen.has(item.id)) return false
      seen.add(item.id)
      return true
    })
  }, [audit, events])

  const groups = useMemo(() => groupTimeline(items, now), [items, now])

  return (
    <Section
      title="Every action, in order"
      description="Append-only. Newest first. Satya never edits a past entry."
      action={
        <span className={`text-[12px] ${surface.muted}`}>
          {items.length} {items.length === 1 ? 'entry' : 'entries'}
        </span>
      }
    >
      {loading ? (
        <div className={`flex items-center gap-2 py-6 text-[12px] ${surface.muted}`}>
          <RefreshCw size={14} className="animate-spin" aria-hidden="true" /> Loading the audit trail…
        </div>
      ) : error ? (
        <Empty
          icon={AlertTriangle}
          title="The timeline could not load"
          body={error}
        />
      ) : items.length === 0 ? (
        <Empty
          icon={Clock3}
          title="Nothing logged yet"
          body="When Satya notices a call, checks a file or raises an alert, the entry appears here."
        />
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <div key={group.label}>
              <p className={`mb-2 text-[12px] font-semibold ${surface.muted}`}>{group.label}</p>
              <ol className="relative space-y-1 border-l border-[rgba(42,34,56,0.10)] pl-4 dark:border-[rgba(237,232,245,0.10)]">
                {group.items.map((item) => {
                  const Icon = iconFor(item.action)
                  const color = colorFor(item.action)
                  return (
                    <li key={item.id} className="relative py-2">
                      <span
                        className="absolute -left-[27px] top-3 grid h-5 w-5 place-items-center rounded-full border bg-[#FFFCF7] dark:bg-[#1C1828]"
                        style={{ borderColor: `${color}40` }}
                        aria-hidden="true"
                      >
                        <Icon size={11} style={{ color }} />
                      </span>
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium">{actionLabel(item.action)}</p>
                          <p className={`mt-1 break-words text-[12px] leading-relaxed ${surface.muted}`}>
                            {item.detail}
                          </p>
                          <p className={`mt-1 text-[12px] ${surface.muted}`}>
                            {item.actor}
                            {item.live ? (
                              <span
                                className="ml-2 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[12px]"
                                style={{ backgroundColor: `${tone.watch}12`, color: tone.watch }}
                              >
                                live
                              </span>
                            ) : null}
                          </p>
                        </div>
                        <time
                          className={`shrink-0 text-[12px] ${surface.muted}`}
                          dateTime={item.at}
                          title={item.at}
                          style={{ fontFamily: FONT_MONO }}
                        >
                          {relativeTime(item.at, now)}
                        </time>
                      </div>
                    </li>
                  )
                })}
              </ol>
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}
