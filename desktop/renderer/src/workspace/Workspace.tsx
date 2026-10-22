import {
  AlertTriangle,
  CheckCircle,
  Copy,
  ExternalLink,
  FileText,
  Lock,
  RefreshCw,
  Shield,
  ShieldAlert,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import type { CaseSummary, WorkspaceSnapshot } from '../../../shared/contracts'
import { createCompanionClient } from '../companion/CompanionApiClient'
import { reasonLabel } from '../companion/reasonLabels'

export default function Workspace(): JSX.Element {
  const [client] = useState(() => createCompanionClient())
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<WorkspaceSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    client
      .listCases()
      .then((items) => {
        if (!active) return
        setCases(items)
        if (items.length > 0) setSelectedId(items[0].case_id)
        setLoading(false)
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [client])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    setLoading(true)
    client
      .workspace(selectedId)
      .then((data) => {
        if (!active) return
        setSnapshot(data)
        setLoading(false)
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [client, selectedId])

  const copyToClipboard = (text: string, label: string) => {
    void navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100 select-none">
      {/* Sidebar */}
      <aside className="flex w-72 flex-col border-r border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5 text-emerald-400" />
          <h1 className="text-base font-bold tracking-tight text-white">Satyapan Workspace</h1>
        </div>
        <p className="mb-3 text-xs text-slate-400">Cases under verification desk review</p>

        <div className="flex-1 space-y-1 overflow-y-auto">
          {cases.map((c) => (
            <button
              key={c.case_id}
              type="button"
              onClick={() => setSelectedId(c.case_id)}
              className={`flex w-full flex-col rounded-lg p-2.5 text-left text-xs transition ${
                selectedId === c.case_id
                  ? 'bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-500/40'
                  : 'text-slate-300 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-center justify-between font-medium">
                <span className="font-mono text-[11px] text-slate-400">{c.case_id}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    c.band === 'HOLD'
                      ? 'bg-rose-500/20 text-rose-300'
                      : c.band === 'VERIFY'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-emerald-500/20 text-emerald-300'
                  }`}
                >
                  {c.band}
                </span>
              </div>
              <div className="mt-1 truncate font-medium text-slate-200">{c.title}</div>
            </button>
          ))}
          {cases.length === 0 && !loading && (
            <div className="p-4 text-center text-xs text-slate-500">No active cases</div>
          )}
        </div>

        <div className="mt-auto border-t border-slate-800 pt-3 text-[11px] text-slate-500">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Lock className="h-3 w-3" />
            <span>Authority: satyapan.policy</span>
          </div>
          <div className="mt-1">All reports are MANUAL_ONLY drafts.</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="grid h-full place-items-center">
            <RefreshCw className="h-6 w-6 animate-spin text-slate-500" />
          </div>
        ) : snapshot ? (
          <div className="mx-auto max-w-4xl space-y-6">
            {/* Case Header */}
            <header className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-400">{snapshot.case_id}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                      {snapshot.kind}
                    </span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                      satyapan.policy
                    </span>
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300">
                      MANUAL_ONLY
                    </span>
                  </div>
                  <h2 className="mt-2 text-xl font-bold text-white">{snapshot.title}</h2>
                  <p className="mt-1 text-xs text-slate-400">{snapshot.explanation}</p>
                </div>

                <div className="flex flex-col items-end gap-1">
                  <div
                    className={`rounded-lg px-3 py-1.5 text-sm font-bold tracking-wide ${
                      snapshot.band === 'HOLD'
                        ? 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40'
                        : snapshot.band === 'VERIFY'
                          ? 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40'
                          : 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40'
                    }`}
                  >
                    BAND: {snapshot.band}
                  </div>
                  <span className="text-[11px] text-slate-400">
                    Floor: <strong className="text-slate-300">{snapshot.floor_band}</strong>
                  </span>
                </div>
              </div>

              {/* Transaction Summary */}
              <div className="mt-4 grid grid-cols-3 gap-4 border-t border-slate-800/80 pt-4 text-xs">
                <div>
                  <span className="text-slate-500">Payee (Masked):</span>
                  <div className="font-mono font-medium text-slate-200">
                    {snapshot.payee_masked ?? '—'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500">Amount:</span>
                  <div className="font-medium text-slate-200">
                    {snapshot.amount_inr ? `₹${snapshot.amount_inr.toLocaleString('en-IN')}` : '—'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500">Queue:</span>
                  <div className="font-medium text-slate-200">{snapshot.queue}</div>
                </div>
              </div>
            </header>

            {/* Reason Codes & Forensic Signals */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Triggered Reasons & Forensic Signals
              </h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {snapshot.reason_codes.map((code) => (
                  <div
                    key={code}
                    className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-200"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
                    <span className="font-semibold">{code}</span>
                    <span className="text-slate-400">({reasonLabel(code)})</span>
                  </div>
                ))}
                {snapshot.reason_codes.length === 0 && (
                  <div className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-200">
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                    <span>No adverse signals detected</span>
                  </div>
                )}
              </div>
            </section>

            {/* Evidence Index (Custody Chain) */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Evidence Custody Index (SHA-256)
              </h3>
              <div className="mt-3 divide-y divide-slate-800 overflow-hidden rounded-lg border border-slate-800">
                {snapshot.evidence.map((ev) => (
                  <div key={ev.evidence_id} className="flex items-center justify-between p-3 text-xs">
                    <div>
                      <span className="font-semibold text-slate-200">{ev.evidence_id}</span>
                      <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                        {ev.channel}
                      </span>
                      {ev.filename && (
                        <div className="mt-0.5 font-mono text-[11px] text-slate-400">
                          {ev.filename}
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-[10px] text-slate-500">SHA: {ev.sha256_short}</div>
                      <div className="text-[10px] text-slate-400">{ev.size_bytes} bytes</div>
                    </div>
                  </div>
                ))}
                {snapshot.evidence.length === 0 && (
                  <div className="p-3 text-xs text-slate-500">No evidence attached</div>
                )}
              </div>
            </section>

            {/* Generated Statutory Drafts */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Statutory Drafts (Section 63 BSA & 1930 Helpline)
                </h3>
                <span className="text-[10px] text-amber-300">Requires Human Review</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-4">
                {snapshot.drafts.map((d) => (
                  <div
                    key={d.draft_id}
                    className="flex flex-col justify-between rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 text-xs"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white">
                          {d.kind === 'section63' ? 'BSA 2023 Sec 63 Certificate' : '1930 Phone Script'}
                        </span>
                        <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-300">
                          {d.submission}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-400">Status: {d.status}</p>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        copyToClipboard(
                          JSON.stringify(d.fields, null, 2),
                          d.kind,
                        )
                      }
                      className="mt-3 flex items-center justify-center gap-1.5 rounded bg-slate-800 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-slate-700"
                    >
                      <Copy className="h-3 w-3" />
                      <span>{copied === d.kind ? 'Copied!' : 'Copy Draft Fields'}</span>
                    </button>
                  </div>
                ))}
                {snapshot.drafts.length === 0 && (
                  <div className="col-span-2 p-3 text-xs text-slate-500">
                    No statutory drafts prepared yet for this case.
                  </div>
                )}
              </div>
            </section>
          </div>
        ) : (
          <div className="grid h-full place-items-center text-xs text-slate-500">
            Select a case to inspect details
          </div>
        )}
      </main>
    </div>
  )
}
