/**
 * Reports — the golden hour (Scribe + Report Copilot).
 *
 * When money already left, every minute matters: banks can only hold funds that have not moved
 * on. Satya writes five drafts from the case's own data (maker-entered payment, vendor master,
 * evidence-vault hashes). The typing animation runs over the backend's final text, so it can
 * never invent content. A human opens each destination and presses Submit; nothing is filed.
 */

import { Check, Clock3, Copy, Eye, EyeOff, ExternalLink, FileText, Lock, PenLine, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import type { CaseSummary, ReportField, ReportPackV2, ReportSection } from '../../../../shared/contracts'
import { api } from '../../shared/api'
import BandBadge from '../ui/BandBadge'
import Empty from '../ui/Empty'
import Section from '../ui/Section'
import { FONT_MONO, button, inset, surface, tone } from '../ui/theme'

const SOURCE_LABEL: Record<ReportField['source'], string> = {
  maker_entered: 'You entered',
  vault: 'Evidence vault',
  vendor_master: 'Vendor master',
  user_confirmed: 'You confirmed',
  system: 'Satya',
}

const OPEN_LABEL: Record<ReportSection['id'], string> = {
  helpline_1930: 'Call 1930',
  bank_fraud_desk: 'Open the email draft',
  ncrp_portal: 'Open cybercrime.gov.in',
  cert_in: 'Open the CERT-In draft',
  bsa_s63_part_a: 'Copy Part A',
}

const GOLDEN_HOUR_S = 60 * 60

function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

function mask(value: string): string {
  return value.replace(/\d{6,}/g, (digits) => `••••${digits.slice(-4)}`)
}

function openUrlFor(section: ReportSection): string | null {
  if (!section.open_url) return null
  if (section.open_url.startsWith('mailto:')) {
    const subject = encodeURIComponent(section.title)
    const body = encodeURIComponent(`${section.body}\n\n${section.fields.map((f) => `${f.label}: ${f.value}`).join('\n')}`)
    return `${section.open_url}?subject=${subject}&body=${body}`
  }
  return section.open_url
}

/** Reveal the backend's final text character by character (client-side only). */
function useTyped(text: string, start: boolean, cps = 120): string {
  const [count, setCount] = useState(start ? 0 : text.length)
  useEffect(() => {
    if (!start) {
      setCount(text.length)
      return
    }
    setCount(0)
    const timer = window.setInterval(() => {
      setCount((n) => {
        if (n >= text.length) {
          window.clearInterval(timer)
          return n
        }
        return Math.min(text.length, n + Math.ceil(cps / 30))
      })
    }, 33)
    return () => window.clearInterval(timer)
  }, [text, start, cps])
  return text.slice(0, count)
}

function SectionCard({
  section,
  index,
  typing,
  done,
  onDone,
}: {
  section: ReportSection
  index: number
  typing: boolean
  done: boolean
  onDone: (value: boolean) => void
}): JSX.Element {
  const [reveal, setReveal] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const body = useTyped(section.body, typing)
  const finished = body.length >= section.body.length
  const url = openUrlFor(section)

  async function copy(key: string, text: string): Promise<void> {
    const result = await api.copyText(text)
    if (result.ok) {
      setCopied(key)
      window.setTimeout(() => setCopied(null), 1500)
    }
  }

  const allText = `${section.title}\n${section.body}\n${section.fields.map((f) => `${f.label}: ${f.value}`).join('\n')}`

  return (
    <article className={`${inset} p-4 ${section.applies ? '' : 'opacity-70'}`}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-[12px] font-bold text-white"
            style={{ backgroundColor: done ? tone.green : tone.write }}
          >
            {done ? <Check size={14} aria-hidden="true" /> : index + 1}
          </span>
          <div className="min-w-0">
            <h3 className="text-[14px] font-semibold">{section.title}</h3>
            <p className={`text-[12px] ${surface.muted}`}>{section.destination}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {section.deadline_hint ? (
            <span className="rounded-full px-2 py-0.5 text-[11.5px] font-semibold" style={{ backgroundColor: `${tone.amber}22`, color: '#9a6400' }}>
              {section.deadline_hint}
            </span>
          ) : null}
          {!section.applies ? (
            <span className={`rounded-full border px-2 py-0.5 text-[11.5px] ${surface.line} ${surface.muted}`}>Check with IT/legal</span>
          ) : null}
        </div>
      </header>

      <p className="mt-3 min-h-[2.5em] whitespace-pre-wrap text-[13px] leading-relaxed">
        {body}
        {!finished ? <span className="ml-0.5 inline-block h-[1em] w-[2px] animate-pulse align-middle" style={{ backgroundColor: tone.write }} /> : null}
      </p>

      {finished && section.fields.length > 0 ? (
        <table className="mt-3 w-full border-collapse text-left text-[12.5px]">
          <tbody>
            {section.fields.map((field, i) => {
              const value = field.sensitive && !reveal ? mask(field.value) : field.value
              return (
                <tr key={`${field.label}-${i}`} className="border-t" style={{ borderColor: 'rgba(42,34,56,0.08)' }}>
                  <td className={`w-[34%] py-1.5 pr-2 align-top ${surface.muted}`}>{field.label}</td>
                  <td className="break-all py-1.5 pr-2 align-top" style={{ fontFamily: field.source === 'vault' ? FONT_MONO : undefined }}>
                    {value}
                  </td>
                  <td className="w-[1%] whitespace-nowrap py-1.5 pr-2 align-top">
                    <span className={`rounded-full border px-1.5 py-0.5 text-[10.5px] ${surface.line} ${surface.muted}`}>{SOURCE_LABEL[field.source]}</span>
                  </td>
                  <td className="w-[1%] py-1.5 align-top">
                    {field.copy ? (
                      <button type="button" className={button.ghost} onClick={() => void copy(`${i}`, field.value)} aria-label={`Copy ${field.label}`}>
                        {copied === `${i}` ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
                      </button>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ) : null}

      {finished ? (
        <footer className="mt-3 flex flex-wrap items-center gap-2">
          {url && section.id !== 'bsa_s63_part_a' ? (
            <button type="button" className={button.primary} onClick={() => void api.openExternal(url).catch(() => undefined)}>
              <ExternalLink size={14} aria-hidden="true" />
              {OPEN_LABEL[section.id]}
            </button>
          ) : null}
          <button type="button" className={button.outline} onClick={() => void copy('all', allText)}>
            {copied === 'all' ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
            Copy all
          </button>
          {section.fields.some((f) => f.sensitive) ? (
            <button type="button" className={button.ghost} onClick={() => setReveal((v) => !v)}>
              {reveal ? <EyeOff size={14} aria-hidden="true" /> : <Eye size={14} aria-hidden="true" />}
              {reveal ? 'Hide account' : 'Reveal account'}
            </button>
          ) : null}
          <label className="ml-auto flex items-center gap-2 text-[12.5px]">
            <input type="checkbox" checked={done} onChange={(e) => onDone(e.target.checked)} />
            I submitted this myself
          </label>
        </footer>
      ) : null}
    </article>
  )
}

export default function ReportsTab({ preferredCaseId = null }: { preferredCaseId?: string | null }): JSX.Element {
  const now = useNow()
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [caseId, setCaseId] = useState<string | null>(preferredCaseId)
  const [leftAt, setLeftAt] = useState<number | null>(null)
  const [utr, setUtr] = useState('')
  const [pack, setPack] = useState<ReportPackV2 | null>(null)
  const [writing, setWriting] = useState(false)
  const [typingIndex, setTypingIndex] = useState(-1)
  const [done, setDone] = useState<Record<string, boolean>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void api.listCases().then((result) => {
      if (!result.ok) return
      const order = { HOLD: 0, VERIFY: 1, PASS: 2 } as const
      const sorted = [...result.data].sort((a, b) => order[a.band] - order[b.band])
      setCases(sorted)
      setCaseId((current) => current ?? preferredCaseId ?? sorted[0]?.case_id ?? null)
    })
  }, [preferredCaseId])

  // Type the sections one after another.
  useEffect(() => {
    if (!pack || typingIndex < 0 || typingIndex >= pack.sections.length) return
    const length = pack.sections[typingIndex].body.length
    const timer = window.setTimeout(() => setTypingIndex((i) => i + 1), Math.min(2600, 400 + length * 8))
    return () => window.clearTimeout(timer)
  }, [pack, typingIndex])

  const remaining = leftAt ? GOLDEN_HOUR_S - (now - leftAt) / 1000 : null
  const selected = useMemo(() => cases.find((c) => c.case_id === caseId) ?? null, [cases, caseId])

  async function write(): Promise<void> {
    if (!caseId || !api.reportPack) return
    setWriting(true)
    setError(null)
    try {
      const result = await api.reportPack(caseId, {
        utr: /^[A-Za-z0-9]{6,30}$/.test(utr) ? utr : undefined,
        money_left_at: leftAt ? new Date(leftAt).toISOString() : undefined,
      })
      if (!result.ok) {
        setError(result.error)
        return
      }
      setPack(result.data)
      setDone({})
      setTypingIndex(0)
    } finally {
      setWriting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Section
        title="Golden hour"
        description="If money already left, report fast: the bank can only hold money that has not moved on."
        action={
          remaining !== null ? (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-bold tabular-nums text-white"
              style={{ backgroundColor: remaining > 15 * 60 ? tone.amber : tone.coral }}
            >
              <Clock3 size={14} aria-hidden="true" />
              {remaining > 0 ? `${clock(remaining)} left` : 'Past the golden hour — still report'}
            </span>
          ) : undefined
        }
      >
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
          <label className="text-[12px]">
            <span className={surface.muted}>Which payment?</span>
            <select
              className={`mt-1 w-full rounded-[10px] border px-2 py-2 text-[13px] ${surface.line} ${surface.card}`}
              value={caseId ?? ''}
              onChange={(e) => {
                setCaseId(e.target.value || null)
                setPack(null)
              }}
            >
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.title} · {c.band}
                </option>
              ))}
            </select>
          </label>
          <div className="text-[12px]">
            <span className={surface.muted}>When did it leave?</span>
            <button
              type="button"
              className={`${leftAt ? button.outline : button.danger} mt-1 w-full`}
              onClick={() => setLeftAt(Date.now())}
            >
              <Clock3 size={14} aria-hidden="true" />
              {leftAt ? `Left at ${new Date(leftAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'It left just now'}
            </button>
          </div>
          <label className="text-[12px]">
            <span className={surface.muted}>UTR (from your bank statement)</span>
            <input
              className={`mt-1 w-full rounded-[10px] border px-2 py-2 text-[13px] uppercase ${surface.line} ${surface.card}`}
              style={{ fontFamily: FONT_MONO }}
              placeholder="e.g. FAKEUTR123456"
              value={utr}
              onChange={(e) => setUtr(e.target.value.replace(/[^A-Za-z0-9]/g, '').slice(0, 30).toUpperCase())}
            />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" className={button.primary} disabled={!caseId || writing} onClick={() => void write()} style={{ backgroundColor: tone.write }}>
            <PenLine size={14} aria-hidden="true" />
            {writing ? 'Writing…' : pack ? 'Rewrite the pack' : 'Write my report pack'}
          </button>
          {selected ? <BandBadge band={selected.band} /> : null}
          {error ? <span className="text-[12px]" style={{ color: tone.coral }}>{error}</span> : null}
        </div>
        <div
          className="mt-4 flex items-start gap-3 rounded-[14px] border px-4 py-3"
          style={{ borderColor: `${tone.amber}40`, backgroundColor: `${tone.amber}10` }}
        >
          <ShieldCheck size={17} className="mt-0.5 shrink-0" style={{ color: tone.amber }} aria-hidden="true" />
          <p className="text-[12.5px] leading-relaxed">
            <b>Drafts only. Nothing has been sent.</b> There is no public 1930/NCRP API and the portal needs your own
            OTP login, so Satya prepares the words and the hashes and you press Submit.
          </p>
        </div>
      </Section>

      {pack ? (
        <div className="space-y-3">
          {pack.sections.map((section, index) =>
            index <= Math.max(typingIndex, 0) || typingIndex >= pack.sections.length ? (
              <SectionCard
                key={section.id}
                section={section}
                index={index}
                typing={index === typingIndex}
                done={Boolean(done[section.id])}
                onDone={(value) => setDone((d) => ({ ...d, [section.id]: value }))}
              />
            ) : null,
          )}
          <p className={`flex items-center gap-2 text-[12px] ${surface.muted}`}>
            <Lock size={13} aria-hidden="true" />
            Manual submission only, by design. Every line shows where it came from.
          </p>
        </div>
      ) : (
        <Section>
          <Empty
            icon={FileText}
            title="No report pack yet"
            body="Pick the payment, tap “It left just now”, add the UTR if you have it, and Satya writes five drafts: 1930 script, bank email, NCRP field helper, CERT-In email and the BSA §63 Part A hash list."
          />
        </Section>
      )}
    </div>
  )
}
