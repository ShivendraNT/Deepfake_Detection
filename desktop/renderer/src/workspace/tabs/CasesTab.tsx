import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  FolderOpen,
  Lock,
  RefreshCw,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import type { CaseSummary, WorkspaceSnapshot } from '../../../../shared/contracts'
import { api } from '../../shared/api'
import { reasonLabel } from '../../companion/reasonLabels'
import {
  BAND_WORD,
  formatBytes,
  formatInr,
  maskAccount,
  relativeTime,
} from '../lib/format'
import BandBadge from '../ui/BandBadge'
import Empty from '../ui/Empty'
import Hash from '../ui/Hash'
import PolicyTrace from '../ui/PolicyTrace'
import Section from '../ui/Section'
import { FONT_MONO, focusRing, inset, surface, tone } from '../ui/theme'

export interface CasesTabProps {
  initialCaseId?: string | null
  /** Bumped after a case/evidence event so the list and the open case re-read the backend. */
  refreshKey?: number
}

function draftTitle(kind: 'section63' | 'helpline_1930'): string {
  return kind === 'section63' ? 'BSA 2023 §63 certificate' : '1930 helpline script'
}

function CaseDetail({ snapshot }: { snapshot: WorkspaceSnapshot }): JSX.Element {
  return (
    <div className="space-y-4">
      <Section>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <code
                className={`rounded-[6px] px-1.5 py-0.5 text-[12px] ${surface.inset} ${surface.muted}`}
                style={{ fontFamily: FONT_MONO }}
              >
                {snapshot.case_id}
              </code>
              <span className={`text-[12px] ${surface.muted}`}>{snapshot.kind}</span>
            </div>
            <h2 className="mt-2 text-[20px] font-semibold leading-tight tracking-[-0.02em]">
              {snapshot.title}
            </h2>
          </div>
          <BandBadge band={snapshot.band} />
        </div>

        <div className="mt-4 grid grid-cols-3 gap-4 border-t pt-4 text-[12px]">
          <div>
            <p className={surface.muted}>Policy floor</p>
            <p className="mt-1 font-medium">{BAND_WORD[snapshot.floor_band]}</p>
          </div>
          <div>
            <p className={surface.muted}>Queue</p>
            <p className="mt-1 font-medium">{snapshot.queue.replace(/_/g, ' ').toLowerCase()}</p>
          </div>
          <div>
            <p className={surface.muted}>Status</p>
            <p className="mt-1 font-medium">{snapshot.status.replace(/_/g, ' ').toLowerCase()}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 border-t pt-4">
          <div>
            <p className={`text-[12px] ${surface.muted}`}>Payee</p>
            <p className="mt-1 break-words text-[14px] font-medium">
              {maskAccount(snapshot.payee_masked)}
            </p>
          </div>
          <div>
            <p className={`text-[12px] ${surface.muted}`}>Amount</p>
            <p className="mt-1 text-[20px] font-semibold tracking-[-0.02em]">
              {formatInr(snapshot.amount_inr)}
            </p>
          </div>
        </div>
      </Section>

      <Section
        title="Why Satya paused this"
        description="Plain words from the policy's reasons. No scores are shown."
      >
        {snapshot.reason_codes.length > 0 ? (
          <ul className="space-y-2">
            {snapshot.reason_codes.map((code) => (
              <li key={code} className="flex items-start gap-2 text-[13px]">
                <AlertTriangle
                  size={14}
                  className="mt-0.5 shrink-0"
                  style={{ color: tone.amber }}
                  aria-hidden="true"
                />
                <span>{reasonLabel(code)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-start gap-2 text-[13px]">
            <CheckCircle2
              size={14}
              className="mt-0.5 shrink-0"
              style={{ color: tone.green }}
              aria-hidden="true"
            />
            <span>No adverse reason was recorded for this case.</span>
          </p>
        )}
        {snapshot.trace ? <PolicyTrace trace={snapshot.trace} /> : null}
      </Section>

      <div className="grid grid-cols-2 gap-4">
        <Section title="Evidence" description="Hashes are computed before a file is opened.">
          {snapshot.evidence.length > 0 ? (
            <ul className="space-y-3">
              {snapshot.evidence.map((evidence) => (
                <li key={evidence.evidence_id} className="min-w-0">
                  <p className="truncate text-[13px] font-medium">
                    {evidence.filename ?? evidence.evidence_id}
                  </p>
                  <p className={`mt-1 text-[12px] ${surface.muted}`}>
                    {evidence.channel} · {formatBytes(evidence.size_bytes)}
                  </p>
                  <div className="mt-1">
                    <Hash value={evidence.sha256_short} label="SHA-256" head={12} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={`text-[12px] ${surface.muted}`}>No evidence attached to this case.</p>
          )}
        </Section>

        <Section title="Drafts" description="Every draft needs a human review. Nothing was sent.">
          {snapshot.drafts.length > 0 ? (
            <ul className="space-y-3">
              {snapshot.drafts.map((draft) => (
                <li key={draft.draft_id} className="flex items-start gap-2">
                  <FileText
                    size={14}
                    className="mt-0.5 shrink-0"
                    style={{ color: tone.write }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium">{draftTitle(draft.kind)}</p>
                    <p className={`mt-0.5 text-[12px] ${surface.muted}`}>
                      Draft · manual submission only
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className={`text-[12px] ${surface.muted}`}>No drafts prepared for this case yet.</p>
          )}
        </Section>
      </div>
    </div>
  )
}

export default function CasesTab({ initialCaseId = null, refreshKey = 0 }: CasesTabProps): JSX.Element {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(initialCaseId)
  const [snapshot, setSnapshot] = useState<WorkspaceSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    void api.listCases().then((result) => {
      if (!active) return
      if (!result.ok) {
        setError(result.error)
        setLoading(false)
        return
      }
      const items = result.data
      setCases(items)
      setSelectedId((current) => {
        if (current && items.some((item) => item.case_id === current)) return current
        return initialCaseId ?? items[0]?.case_id ?? null
      })
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [initialCaseId, refreshKey])

  useEffect(() => {
    if (initialCaseId) {
      setSelectedId(initialCaseId)
    }
  }, [initialCaseId])

  useEffect(() => {
    if (!selectedId) {
      setSnapshot(null)
      return
    }
    let active = true
    setDetailLoading(true)
    void api.workspace(selectedId).then((result) => {
      if (!active) return
      if (result.ok) {
        setSnapshot(result.data)
        setError(null)
      } else {
        setSnapshot(null)
        setError(`This case could not be loaded: ${result.error}`)
      }
      setDetailLoading(false)
    })
    return () => {
      active = false
    }
  }, [selectedId, refreshKey])

  return (
    <div className="grid min-h-[560px] grid-cols-[300px_minmax(0,1fr)] gap-4">
      <Section title="Cases" bodyClassName="p-2" className="flex flex-col overflow-hidden">
        {loading ? (
          <div className={`flex items-center gap-2 px-3 py-4 text-[12px] ${surface.muted}`}>
            <RefreshCw size={14} className="animate-spin" aria-hidden="true" /> Loading cases…
          </div>
        ) : cases.length > 0 ? (
          <div className="max-h-[560px] space-y-1 overflow-y-auto pr-1">
            {cases.map((item) => {
              const selected = item.case_id === selectedId
              return (
                <button
                  key={item.case_id}
                  type="button"
                  onClick={() => setSelectedId(item.case_id)}
                  aria-pressed={selected}
                  className={`${focusRing} w-full rounded-[10px] px-3 py-3 text-left transition ${
                    selected ? surface.active : surface.hover
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 flex-1 truncate text-[13px] font-medium">{item.title}</p>
                    <BandBadge band={item.band} size="sm" />
                  </div>
                  <p className={`mt-1 text-[12px] ${surface.muted}`}>
                    {item.queue.replace(/_/g, ' ').toLowerCase()} · {relativeTime(item.updated_at)}
                  </p>
                </button>
              )
            })}
          </div>
        ) : (
          <Empty
            icon={FolderOpen}
            title="No cases yet"
            body="Cases appear here when Satya checks a payment or you hand him a file."
          />
        )}
      </Section>

      <div className="min-w-0">
        {error ? (
          <Empty
            icon={AlertTriangle}
            title="Could not load this case"
            body={error}
            action={
              <p className={`text-[12px] ${surface.muted}`}>
                Nothing changed. The policy band was not touched.
              </p>
            }
          />
        ) : detailLoading ? (
          <div
            className={`grid h-full place-items-center rounded-[18px] border ${surface.line} ${inset}`}
          >
            <span className={`flex items-center gap-2 text-[12px] ${surface.muted}`}>
              <RefreshCw size={14} className="animate-spin" aria-hidden="true" /> Loading case detail…
            </span>
          </div>
        ) : snapshot ? (
          <CaseDetail snapshot={snapshot} />
        ) : (
          <Empty
            icon={Lock}
            title="Select a case"
            body="Pick a case on the left to see its band, reasons, evidence and drafts."
          />
        )}
      </div>
    </div>
  )
}
