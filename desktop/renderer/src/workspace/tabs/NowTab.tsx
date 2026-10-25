/**
 * Now — what Satya is doing this minute, in plain words.
 *
 * - Live monitoring: the call's full captions (memory only) with the asks highlighted, the chips,
 *   the exact quotes and the band the policy relayed. Or, when idle, the next safe actions.
 * - Ready for a live call?: an honest checklist from /companion/health. Nothing here claims a
 *   detector is running unless the engine says so.
 */

import {
  ArrowRight,
  AudioLines,
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  FileCheck2,
  Headphones,
  Laptop,
  Lock,
  MicOff,
  PhoneOff,
  PlayCircle,
  ScanSearch,
  Shield,
  ShieldAlert,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import type {
  CaptionLine,
  CompanionState,
  CueCode,
  HealthInfo,
  Scopes,
} from '../../../../shared/contracts'
import { ASK_LABELS, CUE_LABELS, DEFAULT_SCOPES } from '../../../../shared/contracts'
import Caption from '../../companion/bubble/Caption'
import { api } from '../../shared/api'
import { formatDuration, relativeTime, secondsSince } from '../lib/format'
import type { LiveSnapshot } from '../lib/live'
import BandBadge from '../ui/BandBadge'
import Empty from '../ui/Empty'
import Qr from '../ui/Qr'
import Section from '../ui/Section'
import { button, inset, surface, tone } from '../ui/theme'

export interface NowTabProps {
  state: CompanionState | null
  live: LiveSnapshot
  onOpenCase: (caseId: string | null) => void
  captions?: CaptionLine[]
  health?: HealthInfo | null
}

const BAND_TONE = { PASS: tone.watch, VERIFY: tone.amber, HOLD: tone.coral } as const

function CheckRow({
  ok,
  optional = false,
  title,
  detail,
  fix,
}: {
  ok: boolean | null
  optional?: boolean
  title: string
  detail: string
  fix?: string
}): JSX.Element {
  const Icon = ok === null ? CircleDashed : ok ? CheckCircle2 : CircleAlert
  const color = ok === null ? tone.slate : ok ? tone.green : optional ? tone.amber : tone.coral
  return (
    <li className="flex items-start gap-3 py-2">
      <Icon size={17} style={{ color }} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-[13px] font-medium">{title}</p>
        <p className={`text-[12px] leading-relaxed ${surface.muted}`}>{detail}</p>
        {fix && ok === false ? (
          <code className={`mt-1 inline-block rounded-md px-1.5 py-0.5 text-[11.5px] ${inset}`}>{fix}</code>
        ) : null}
      </div>
    </li>
  )
}

function ConsentInline({ onDone }: { onDone: () => void }): JSX.Element {
  const [scopes, setScopes] = useState<Scopes>({ ...DEFAULT_SCOPES })
  const [busy, setBusy] = useState(false)
  const rows: Array<[keyof Scopes, string]> = [
    ['meetings', 'Notice when a meeting starts (window names only)'],
    ['listen', 'Listen to a call only after I say yes'],
    ['screen', 'Glance at on-screen text for payment tricks'],
    ['files', 'Check files I hand over'],
  ]
  return (
    <div className={`${inset} p-3`}>
      <p className="text-[13px] font-medium">Can Satya keep watch?</p>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {rows.map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-[12.5px]">
            <input
              type="checkbox"
              checked={scopes[key]}
              onChange={(e) => setScopes((s) => ({ ...s, [key]: e.target.checked }))}
            />
            {label}
          </label>
        ))}
      </div>
      <p className={`mt-2 text-[12px] ${surface.muted}`}>
        Never: the microphone, recordings, or anything leaving this laptop.
      </p>
      <button
        type="button"
        disabled={busy}
        className={`${button.primary} mt-3`}
        onClick={async () => {
          setBusy(true)
          try {
            await api.setUserMode('WATCHING', scopes)
            onDone()
          } finally {
            setBusy(false)
          }
        }}
      >
        Start watching
      </button>
    </div>
  )
}

export default function NowTab({ state, live, onOpenCase, captions = [], health = null }: NowTabProps): JSX.Element {
  const [now, setNow] = useState(() => Date.now())
  const [showConsent, setShowConsent] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [captions.length])

  const inCall = live.callId !== null
  const watching = inCall || state?.mode === 'ACTIVE' || state?.mode === 'ALERT' || state?.monitoring === true
  const elapsed = live.callStartedAt ? secondsSince(live.callStartedAt, now) : 0
  const alert = live.lastAlert
  const band = live.callBand
  const accent = band ? BAND_TONE[band] : tone.watch
  const cues = useMemo(
    () =>
      Array.from(new Set(captions.flatMap((line) => line.spans.filter((s) => s.kind === 'cue').map((s) => s.code)))) as CueCode[],
    [captions],
  )

  async function run(id: string, work: () => Promise<{ ok: boolean; error?: string } | undefined>): Promise<void> {
    setBusy(id)
    setNote(null)
    try {
      const result = await work()
      if (result && !result.ok) setNote(result.error ?? 'That did not work.')
    } finally {
      setBusy(null)
    }
  }

  const asr = health?.asr ?? null
  const asrOk = health ? Boolean(asr && asr.ready && !asr.error) : null

  return (
    <div className="space-y-4">
      <Section
        title="Live monitoring"
        description={
          inCall
            ? 'Listening to this call only. Captions live in memory and vanish when it ends.'
            : watching
              ? 'Watching. I notice calls and ask before I listen.'
              : 'Satya is asleep. Nothing is being watched.'
        }
        action={
          inCall ? (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium tabular-nums ${surface.line}`}
            >
              <span className="h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: accent }} />
              {formatDuration(elapsed)}
            </span>
          ) : undefined
        }
      >
        {inCall ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[14px] font-semibold">
                <Headphones size={16} style={{ color: accent }} aria-hidden="true" />
                {band ? <BandBadge band={band} /> : <span className={surface.muted}>Nothing risky asked so far</span>}
              </div>
              <button type="button" className={button.outline} onClick={() => void run('stop', async () => api.stopCall?.())}>
                <PhoneOff size={14} aria-hidden="true" />
                Stop listening
              </button>
            </div>
            <div ref={listRef} className={`${inset} max-h-[260px] space-y-2 overflow-y-auto p-3`}>
              {captions.length === 0 ? (
                <p className={`text-[12.5px] italic ${surface.muted}`}>Waiting for the other person to speak…</p>
              ) : (
                captions.map((line) => (
                  <div key={line.id} className="flex gap-3">
                    <span className={`w-10 shrink-0 pt-0.5 text-right font-mono text-[11px] ${surface.muted}`}>
                      {formatDuration(Math.round(line.t_start_s))}
                    </span>
                    <div className="min-w-0 flex-1">
                      <Caption line={line} accent={accent} />
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {live.chips.map((chip) => (
                <span
                  key={chip.code}
                  className="rounded-full px-2.5 py-1 text-[12px] font-semibold"
                  style={{ backgroundColor: `${accent}22`, color: tone.ink }}
                >
                  {ASK_LABELS[chip.code]}
                </span>
              ))}
              {cues.map((cue) => (
                <span
                  key={cue}
                  className={`rounded-full border border-dashed px-2.5 py-1 text-[12px] ${surface.line} ${surface.muted}`}
                  title="Context only. It never changes the decision."
                >
                  {CUE_LABELS[cue] ?? cue}
                </span>
              ))}
            </div>
          </div>
        ) : watching ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" className={button.primary} disabled={busy !== null} onClick={() => void run('listen', async () => api.startCall?.('loopback'))}>
              <Headphones size={14} aria-hidden="true" />
              Listen to a call now
            </button>
            <button type="button" className={button.outline} disabled={busy !== null} onClick={() => void run('replay', async () => api.startCall?.('replay'))}>
              <PlayCircle size={14} aria-hidden="true" />
              Play the demo call (replay)
            </button>
            <button type="button" className={button.outline} disabled={busy !== null} onClick={() => void run('scan', async () => api.scanScreen?.())}>
              <ScanSearch size={14} aria-hidden="true" />
              Scan my screen
            </button>
            <button type="button" className={button.ghost} onClick={() => void run('sleep', async () => api.setUserMode('SLEEPING'))}>
              Sleep
            </button>
          </div>
        ) : showConsent ? (
          <ConsentInline onDone={() => setShowConsent(false)} />
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[14px] font-medium">Sleeping. I am not listening.</p>
            <button type="button" className={button.primary} onClick={() => setShowConsent(true)}>
              Wake Satya
            </button>
          </div>
        )}
        {note ? <p className="mt-2 text-[12px]" style={{ color: tone.coral }}>{note}</p> : null}
      </Section>

      <Section
        title="Ready for a live call?"
        description="Checked on this laptop. Fix anything red before the call."
        action={
          <button type="button" className={button.ghost} onClick={() => void api.getHealth?.()}>
            <AudioLines size={14} aria-hidden="true" />
            Recheck
          </button>
        }
      >
        <div className="grid gap-4 md:grid-cols-[1fr_auto]">
          <ul className="divide-y divide-[rgba(42,34,56,0.08)]">
            <CheckRow
              ok={health ? health.backend : null}
              title="Local engine"
              detail={health?.backend ? 'Connected on 127.0.0.1:8000. Bands come only from the policy engine.' : 'Not reachable.'}
              fix="make run"
            />
            <CheckRow
              ok={asrOk}
              title="Ears (speech to text, on this laptop)"
              detail={
                asr && asr.engine !== 'none'
                  ? `${asr.engine} · ${asr.model}${asr.ready ? ' · ready' : asr.loading ? ' · loading…' : ''}${
                      asr.last_latency_ms ? ` · last sentence ${Math.round(asr.last_latency_ms)} ms` : ''
                    }${asr.error ? ` · ${asr.error}` : ''}`
                  : 'No speech engine installed: I could not hear what a caller asks.'
              }
              fix="make asr && make run"
            />
            <CheckRow
              ok={health ? health.voice_model : null}
              optional
              title="Voice-clone detector (optional)"
              detail={
                health?.voice_model
                  ? 'Installed. It can only raise the band, never lower it.'
                  : 'Not installed, so I do not judge voices. I still check what is asked and the payment itself.'
              }
            />
            <CheckRow
              ok={health ? Boolean(health.video?.ready) : null}
              optional
              title="Face check for video calls (optional)"
              detail={
                health?.video?.ready
                  ? `Installed (${health.video.model ?? 'model'}). Looks at the caller's face only after you say yes; it can only raise the band.${
                      health.video.calibrated ? '' : ' Not yet calibrated on our own webcam calls.'
                    }`
                  : `Not installed${health?.video?.error ? ` (${health.video.error})` : ''}. Calls are still listened to.`
              }
              fix="uv sync --extra video && make video-models"
            />
            <CheckRow
              ok={health ? health.vendors > 0 : null}
              title="Vendor master"
              detail={health ? `${health.vendors} vendors loaded (trusted floor for every payment).` : 'Unknown.'}
            />
          </ul>
          {health?.oob_url ? (() => {
            const base = health.oob_url.replace(/\/oob\/?$/, '')
            const phones = [
              { label: "Approver", url: `${base}/oob` },
              { label: "Scam check", url: `${base}/check` },
              { label: "Satya live", url: `${base}/mobile` },
            ]
            return (
              <div className="space-y-2">
                <p className="text-[12px] font-medium">On your phone (same Wi-Fi)</p>
                <div className="grid grid-cols-3 gap-2">
                  {phones.map((phone) => (
                    <div
                      key={phone.label}
                      className={`${inset} flex flex-col items-center gap-1.5 p-2 text-center`}
                    >
                      <Qr value={phone.url} size={84} />
                      <p className="text-[11px] font-medium">{phone.label}</p>
                      <p className={`max-w-[110px] break-all font-mono text-[9px] ${surface.muted}`}>
                        {phone.url}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )
          })() : null}
        </div>
      </Section>

      <Section
        title="Last alert"
        description="A band is a policy decision. Satya raises it; you decide what happens next."
        action={alert ? <BandBadge band={alert.band} /> : undefined}
      >
        {alert ? (
          <div className="flex items-start gap-3">
            <div
              className={`grid h-10 w-10 shrink-0 place-items-center rounded-full border ${surface.line}`}
              style={{ backgroundColor: `${BAND_TONE[alert.band]}18` }}
            >
              <ShieldAlert size={18} style={{ color: BAND_TONE[alert.band] }} aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold">{alert.headline}</p>
              <p className={`mt-1 text-[12px] ${surface.muted}`}>
                Raised {relativeTime(alert.at, now)}. Evidence can only raise the band, never lower it.
              </p>
            </div>
            <button type="button" onClick={() => onOpenCase(alert.caseId)} className={`${button.outline} shrink-0`}>
              Open case
              <ArrowRight size={14} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <Empty
            icon={CheckCircle2}
            title="No alerts yet"
            body="If a payment starts to look risky, Satya pauses you before money moves. Nothing is sent anywhere."
          />
        )}
      </Section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Section title="What Satya can see">
          <ul className="space-y-2 text-[12px]">
            <li className="flex items-start gap-2">
              <CheckCircle2 size={14} style={{ color: tone.green }} aria-hidden="true" />
              <span>The other side of a call you said yes to — never the microphone.</span>
            </li>
            <li className="flex items-start gap-2">
              <FileCheck2 size={14} style={{ color: tone.green }} aria-hidden="true" />
              <span>Files you hand over, hashed before they are opened.</span>
            </li>
            <li className="flex items-start gap-2">
              <Laptop size={14} style={{ color: tone.green }} aria-hidden="true" />
              <span>The vendor master and the payment you entered.</span>
            </li>
          </ul>
        </Section>

        <Section title="What he never does">
          <ul className="space-y-2 text-[12px]">
            <li className="flex items-start gap-2">
              <MicOff size={14} style={{ color: tone.slate }} aria-hidden="true" />
              <span>He never opens your microphone.</span>
            </li>
            <li className="flex items-start gap-2">
              <Lock size={14} style={{ color: tone.slate }} aria-hidden="true" />
              <span>Call audio stays in memory unless you keep it.</span>
            </li>
            <li className="flex items-start gap-2">
              <Shield size={14} style={{ color: tone.slate }} aria-hidden="true" />
              <span>He never submits a report or files anything.</span>
            </li>
          </ul>
        </Section>
      </div>
    </div>
  )
}
