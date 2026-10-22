import {
  ArrowRight,
  AudioLines,
  CheckCircle2,
  FileCheck2,
  Laptop,
  Lock,
  MicOff,
  Pause,
  PhoneCall,
  Play,
  QrCode,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import type { CompanionState, SealStatus } from '../../../../shared/contracts'
import { ASK_LABELS } from '../../../../shared/contracts'
import { api } from '../../shared/api'
import { formatDuration, relativeTime, secondsSince } from '../lib/format'
import type { LiveSnapshot } from '../lib/live'
import BandBadge from '../ui/BandBadge'
import Empty from '../ui/Empty'
import Section from '../ui/Section'
import { button, inset, surface, tone } from '../ui/theme'

export interface NowTabProps {
  state: CompanionState | null
  live: LiveSnapshot
  onOpenCase: (caseId: string | null) => void
}

function coverageCopy(coverage: LiveSnapshot['coverage']): string {
  switch (coverage) {
    case 'usable':
      return 'Coverage: usable'
    case 'degraded':
      return 'Coverage: degraded'
    case 'incomplete':
      return 'Coverage: incomplete'
    default:
      return 'Coverage: waiting'
  }
}

function sealCopy(seal: SealStatus | null): {
  label: string
  color: string
  Icon: typeof Shield
} {
  if (seal === 'verified') {
    return { label: 'Voice verified by Seal', color: tone.green, Icon: ShieldCheck }
  }
  if (seal === 'not_verified') {
    return { label: 'Voice not verified by Seal', color: tone.amber, Icon: ShieldAlert }
  }
  if (seal === 'unavailable') {
    return { label: 'Seal unavailable on this device', color: tone.slate, Icon: Shield }
  }
  return { label: 'Seal check is idle', color: tone.slate, Icon: Shield }
}

export default function NowTab({ state, live, onOpenCase }: NowTabProps): JSX.Element {
  const [now, setNow] = useState(() => Date.now())
  const [simulating, setSimulating] = useState(false)
  const [switchingMode, setSwitchingMode] = useState(false)
  const [oobUrl, setOobUrl] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    void api.getConfig().then((cfg) => {
      if (cfg?.oob_url) setOobUrl(cfg.oob_url)
    })
  }, [])

  const watching =
    state?.monitoring === true ||
    state?.mode === 'ACTIVE' ||
    live.callId !== null ||
    live.callStartedAt !== null

  const inCall = live.callId !== null || live.callStartedAt !== null || watching
  const elapsed = live.callStartedAt ? secondsSince(live.callStartedAt, now) : 0
  const seal = sealCopy(live.seal)
  const SealIcon = seal.Icon
  const alert = live.lastAlert

  const handleSimulateScam = async () => {
    setSimulating(true)
    try {
      await api.command('demo.replay', { scenario: 'cfo_call' })
    } finally {
      setSimulating(false)
    }
  }

  const handleStartProtection = async () => {
    setSwitchingMode(true)
    try {
      await api.setUserMode('WATCHING')
    } finally {
      setSwitchingMode(false)
    }
  }

  const handlePauseProtection = async () => {
    setSwitchingMode(true)
    try {
      await api.setUserMode('SLEEPING')
    } finally {
      setSwitchingMode(false)
    }
  }

  return (
    <div className="space-y-4">
      <Section
        title="Live monitoring"
        description={
          watching
            ? 'Satya is actively protecting Google Meet & monitoring the screen. Voice asks and payment bypasses are relayed in real-time.'
            : 'Satya is asleep. Nothing is being watched.'
        }
        action={
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium ${surface.line} ${surface.muted}`}
          >
            <AudioLines size={12} strokeWidth={2} aria-hidden="true" />
            {coverageCopy(live.coverage)}
          </span>
        }
      >
        {inCall ? (
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="inline-flex items-center gap-2 text-[14px] font-semibold text-emerald-400">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <PhoneCall size={15} style={{ color: tone.watch }} aria-hidden="true" />
                  Live Call: Google Meet & Screen Protected
                </span>
                <span className={surface.muted} aria-hidden="true">
                  ·
                </span>
                <span
                  className="text-[14px] font-semibold tabular-nums"
                  aria-label={`Call duration ${formatDuration(elapsed)}`}
                >
                  {formatDuration(elapsed)}
                </span>
                <span className={surface.muted} aria-hidden="true">
                  ·
                </span>
                <span className={`text-[12px] ${surface.muted}`}>{coverageCopy(live.coverage)}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSimulateScam}
                  disabled={simulating}
                  className="inline-flex items-center gap-1.5 rounded-[8px] bg-amber-500/15 border border-amber-500/30 px-3 py-1.5 text-[12px] font-semibold text-amber-300 transition hover:bg-amber-500/25 active:scale-95 disabled:opacity-50"
                  title="Inject a realistic CFO Deepfake call to demonstrate live detection and OOB verification lockdown"
                >
                  <Zap size={13} className="text-amber-400 fill-amber-400" aria-hidden="true" />
                  {simulating ? 'Injecting Attack...' : '⚡ Simulate CFO Scam Attack'}
                </button>
                <button
                  type="button"
                  onClick={handlePauseProtection}
                  disabled={switchingMode}
                  className="inline-flex items-center gap-1.5 rounded-[8px] border px-2.5 py-1.5 text-[12px] font-medium text-slate-300 transition hover:bg-white/5 active:scale-95"
                  style={{ borderColor: 'rgba(255,255,255,0.1)' }}
                  title="Pause live monitoring and put Satya to sleep"
                >
                  <Pause size={12} aria-hidden="true" />
                  Pause
                </button>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {live.chips.length > 0 ? (
                live.chips.map((chip) => (
                  <span
                    key={`${chip.code}-${chip.at_s ?? 'na'}`}
                    className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium"
                    style={{
                      borderColor: `${tone.watch}33`,
                      backgroundColor: `${tone.watch}12`,
                      color: tone.ink,
                    }}
                  >
                    <AudioLines size={12} aria-hidden="true" />
                    {ASK_LABELS[chip.code]}
                  </span>
                ))
              ) : (
                <span className={`text-[12px] ${surface.muted}`}>
                  Actively monitoring call audio and screen text. No payment tricks or urgency detected yet.
                </span>
              )}
            </div>

            <div
              className={`mt-4 flex items-center justify-between gap-2 rounded-[10px] border px-3 py-2 text-[12px] ${surface.line} ${surface.inset}`}
            >
              <div className="flex items-center gap-2">
                <SealIcon size={14} style={{ color: seal.color }} aria-hidden="true" />
                <span>{seal.label}</span>
              </div>
              <span className="text-[11px] text-slate-400">
                macOS Screen Guard: <span className="text-emerald-400 font-medium">Active (Apple Vision OCR)</span>
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div
                className={`grid h-10 w-10 shrink-0 place-items-center rounded-full border ${surface.line} ${inset}`}
              >
                <PhoneCall size={17} className={surface.muted} aria-hidden="true" />
              </div>
              <div>
                <p className="text-[14px] font-medium">Sleeping. I am not listening.</p>
                <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>
                  Wake Satya to start live protection for Google Meet calls and on-screen invoices.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleStartProtection}
              disabled={switchingMode}
              className="inline-flex items-center gap-2 rounded-[10px] bg-emerald-500 px-4 py-2 text-[13px] font-semibold text-slate-950 transition hover:bg-emerald-400 active:scale-95 disabled:opacity-50"
            >
              <Play size={14} className="fill-slate-950" aria-hidden="true" />
              {switchingMode ? 'Starting...' : '🛡️ Start Live Call & Screen Protection'}
            </button>
          </div>
        )}
      </Section>

      <Section
        title="Last alert"
        description="A band is a policy decision. Satya raises it; you decide what happens next."
        action={alert ? <BandBadge band={alert.band} /> : undefined}
      >
        {alert ? (
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div
                className={`grid h-10 w-10 shrink-0 place-items-center rounded-full border ${surface.line}`}
                style={{ backgroundColor: `${tone.coral}12` }}
              >
                <ShieldAlert size={17} style={{ color: tone.coral }} aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-semibold">{alert.headline}</p>
                <p className={`mt-1 text-[12px] ${surface.muted}`}>
                  Raised {relativeTime(alert.at, now)}. Policy engine band:{' '}
                  <span className="font-bold text-rose-400">{alert.band}</span>. Satya never lowers this band.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {oobUrl ? (
                  <button
                    type="button"
                    onClick={() => window.open(oobUrl, '_blank')}
                    className="inline-flex items-center gap-1.5 rounded-[8px] bg-purple-500/15 border border-purple-500/30 px-3 py-1.5 text-[12px] font-semibold text-purple-300 transition hover:bg-purple-500/25 active:scale-95"
                    title="Open the Linked Mobile Verification Web App to simulate phone approval/lockdown"
                  >
                    <QrCode size={13} aria-hidden="true" />
                    📱 Open Phone Approver
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => onOpenCase(alert.caseId)}
                  className={`${button.outline} shrink-0`}
                >
                  Open case
                  <ArrowRight size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <Empty
            icon={CheckCircle2}
            title="No alerts yet"
            body="If a payment starts to look risky, Satya pauses you before money moves. Nothing is sent anywhere."
          />
        )}
      </Section>

      <div className="grid grid-cols-2 gap-4">
        <Section title="What Satya can see">
          <ul className="space-y-2 text-[12px]">
            <li className="flex items-start gap-2">
              <CheckCircle2 size={14} style={{ color: tone.green }} aria-hidden="true" />
              <span>Calls he is allowed to notice — never the microphone.</span>
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
