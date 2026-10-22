import {
  AlertTriangle,
  FileCheck2,
  Fingerprint,
  Lock,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  evidenceKey,
  loadEvidence,
  type EvidenceBundle,
} from '../lib/data'
import { actionLabel, channelLabel, formatBytes, formatDateTime } from '../lib/format'
import Empty from '../ui/Empty'
import Hash from '../ui/Hash'
import Section from '../ui/Section'
import { button, focusRing, inset, surface, tone } from '../ui/theme'

type CheckState =
  | { status: 'idle'; message: '' }
  | { status: 'checking'; message: string }
  | { status: 'ok'; message: string }
  | { status: 'changed'; message: string }
  | { status: 'error'; message: string }

const IDLE_CHECK: CheckState = { status: 'idle', message: '' }

function checkColor(status: CheckState['status']): string {
  if (status === 'ok') return tone.green
  if (status === 'changed' || status === 'error') return tone.coral
  return tone.slate
}

function CheckIcon({ status }: { status: CheckState['status'] }): JSX.Element {
  if (status === 'ok') return <ShieldCheck size={14} aria-hidden="true" />
  if (status === 'changed' || status === 'error') {
    return <ShieldAlert size={14} aria-hidden="true" />
  }
  return <RefreshCw size={14} className="animate-spin" aria-hidden="true" />
}

export default function EvidenceTab(): JSX.Element {
  const [bundles, setBundles] = useState<EvidenceBundle[]>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [check, setCheck] = useState<CheckState>(IDLE_CHECK)

  useEffect(() => {
    let active = true
    setLoading(true)
    void loadEvidence()
      .then((items) => {
        if (!active) return
        setBundles(items)
        setSelectedKey((current) => current ?? (items[0] ? evidenceKey(items[0]) : null))
        setError(null)
        setLoading(false)
      })
      .catch((reason: unknown) => {
        if (!active) return
        setError(reason instanceof Error ? reason.message : 'Evidence could not be loaded.')
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const selected = bundles.find((item) => evidenceKey(item) === selectedKey) ?? bundles[0] ?? null

  async function recheck(): Promise<void> {
    setCheck({ status: 'checking', message: 'Checking every stored hash against the vault…' })
    try {
      const before = new Map(bundles.map((item) => [evidenceKey(item), item.evidence.sha256_short]))
      const fresh = await loadEvidence()
      const changed = fresh.filter(
        (item) => before.get(evidenceKey(item)) !== item.evidence.sha256_short,
      )
      setBundles(fresh)
      if (changed.length > 0) {
        setCheck({
          status: 'changed',
          message: `A hash differs for ${changed
            .map((item) => item.evidence.filename ?? item.evidence.evidence_id)
            .join(', ')}. This needs a human review. Satya did not change any band.`,
        })
      } else {
        setCheck({
          status: 'ok',
          message: `Integrity check passed at ${formatDateTime(
            new Date().toISOString(),
          )}. ${fresh.length} ${fresh.length === 1 ? 'file matches' : 'files match'} the stored hash chain.`,
        })
      }
    } catch (reason) {
      setCheck({
        status: 'error',
        message: reason instanceof Error ? reason.message : 'The integrity check could not run.',
      })
    }
  }

  return (
    <div className="grid min-h-[560px] grid-cols-[320px_minmax(0,1fr)] gap-4">
      <Section title="Kept files" bodyClassName="p-2" className="overflow-hidden">
        {loading ? (
          <div className={`flex items-center gap-2 px-3 py-4 text-[12px] ${surface.muted}`}>
            <RefreshCw size={14} className="animate-spin" aria-hidden="true" /> Loading evidence…
          </div>
        ) : bundles.length > 0 ? (
          <div className="max-h-[560px] space-y-1 overflow-y-auto pr-1">
            {bundles.map((item) => {
              const key = evidenceKey(item)
              const active = selected ? key === evidenceKey(selected) : false
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSelectedKey(key)}
                  aria-pressed={active}
                  className={`${focusRing} w-full rounded-[10px] px-3 py-3 text-left transition ${
                    active ? surface.active : surface.hover
                  }`}
                >
                  <p className="truncate text-[13px] font-medium">
                    {item.evidence.filename ?? item.evidence.evidence_id}
                  </p>
                  <p className={`mt-1 text-[12px] ${surface.muted}`}>
                    {channelLabel(item.evidence.channel)} · {formatBytes(item.evidence.size_bytes)}
                  </p>
                  <p className={`mt-1 truncate text-[12px] ${surface.muted}`}>{item.caseTitle}</p>
                </button>
              )
            })}
          </div>
        ) : (
          <Empty
            icon={FileCheck2}
            title="Nothing kept yet"
            body="Files you hand to Satya appear here with a fingerprint and a custody chain."
          />
        )}
      </Section>

      <div className="min-w-0">
        {error ? (
          <Empty icon={AlertTriangle} title="Evidence could not load" body={error} />
        ) : selected ? (
          <div className="space-y-4">
            <Section
              title={selected.evidence.filename ?? selected.evidence.evidence_id}
              description={selected.caseTitle}
              action={
                <button type="button" onClick={() => void recheck()} className={button.outline}>
                  <RefreshCw size={14} aria-hidden="true" />
                  Re-check integrity
                </button>
              }
            >
              <div className="grid grid-cols-2 gap-4 text-[12px]">
                <div>
                  <p className={surface.muted}>Channel</p>
                  <p className="mt-1 font-medium">{channelLabel(selected.evidence.channel)}</p>
                </div>
                <div>
                  <p className={surface.muted}>Size</p>
                  <p className="mt-1 font-medium">{formatBytes(selected.evidence.size_bytes)}</p>
                </div>
                <div>
                  <p className={surface.muted}>Evidence ID</p>
                  <p className="mt-1 font-medium">{selected.evidence.evidence_id}</p>
                </div>
                <div>
                  <p className={surface.muted}>SHA-256</p>
                  <div className="mt-1">
                    <Hash value={selected.evidence.sha256_short} head={12} />
                  </div>
                </div>
              </div>

              {selected.evidence.excerpt ? (
                <p className={`mt-4 rounded-[10px] border px-3 py-2 text-[12px] ${surface.line} ${inset}`}>
                  {selected.evidence.excerpt}
                </p>
              ) : null}
            </Section>

            <Section
              title="Custody chain"
              description="Each row records who touched the file and when. The chain is append-only."
            >
              {selected.custody.length > 0 ? (
                <ol className="space-y-3">
                  {selected.custody.map((row, index) => (
                    <li key={`${row.at}-${row.action}-${index}`} className="flex items-start gap-3">
                      <span
                        className={`grid h-8 w-8 shrink-0 place-items-center rounded-full border ${surface.line} ${inset}`}
                        aria-hidden="true"
                      >
                        {index === 0 ? (
                          <Fingerprint size={14} style={{ color: tone.watch }} />
                        ) : (
                          <Lock size={14} className={surface.muted} />
                        )}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium">{actionLabel(row.action)}</p>
                        <p className={`mt-1 text-[12px] ${surface.muted}`}>
                          {row.actor} · {formatDateTime(row.at)}
                        </p>
                      </div>
                      <Hash value={row.sha256_short} head={8} className="mt-0.5 shrink-0" />
                    </li>
                  ))}
                </ol>
              ) : (
                <p className={`text-[12px] ${surface.muted}`}>
                  No custody rows are stored for this file yet.
                </p>
              )}

              {check.status !== 'idle' ? (
                <div
                  className={`mt-4 flex items-start gap-2 rounded-[10px] border px-3 py-2 text-[12px]`}
                  style={{
                    borderColor: `${checkColor(check.status)}40`,
                    backgroundColor: `${checkColor(check.status)}12`,
                    color: checkColor(check.status),
                  }}
                  role="status"
                >
                  <span className="mt-0.5">
                    <CheckIcon status={check.status} />
                  </span>
                  <span className="leading-relaxed">{check.message}</span>
                </div>
              ) : (
                <p className={`mt-4 text-[12px] ${surface.muted}`}>
                  Re-check compares the stored hash with the vault. It never changes a band.
                </p>
              )}
            </Section>
          </div>
        ) : (
          <Empty
            icon={FileCheck2}
            title="Select a kept file"
            body="Pick a file on the left to see its fingerprint and custody chain."
          />
        )}
      </div>
    </div>
  )
}
