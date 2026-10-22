import {
  ArrowRight,
  AudioLines,
  CheckCircle2,
  FileCheck2,
  Laptop,
  Lock,
  MicOff,
  PhoneCall,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import type { CompanionState, SealStatus } from '../../../../shared/contracts'
import { ASK_LABELS } from '../../../../shared/contracts'
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

function coverageColor(coverage: LiveSnapshot['coverage']): string {
  if (coverage === 'usable') return tone.green
  if (coverage === 'degraded') return tone.amber
  return tone.slate
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

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const inCall = live.callId !== null || live.callStartedAt !== null
  const elapsed = live.callStartedAt ? secondsSince(live.callStartedAt, now) : 0
  const watching =
    live.callId !== null || state?.monitoring === true || state?.mode === 'ACTIVE'
  const seal = sealCopy(live.seal)
  const SealIcon = seal.Icon
  const alert = live.lastAlert

  return (
    <div className="space-y-4">
      <Section
        title="Live monitoring"
        description={
          watching
            ? 'Satya is watching the source you chose. He asks before he listens to a call.'
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
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="inline-flex items-center gap-1.5 text-[14px] font-semibold">
                <PhoneCall size={15} style={{ color: tone.watch }} aria-hidden="true" />
                Live call
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
                  No payment tricks heard yet. Satya only notes asks; he does not judge the voice.
                </span>
              )}
            </div>

            <div
              className={`mt-4 flex items-center gap-2 rounded-[10px] border px-3 py-2 text-[12px] ${surface.line} ${surface.inset}`}
            >
              <SealIcon size={14} style={{ color: seal.color }} aria-hidden="true" />
              <span>{seal.label}</span>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3">
            <div
              className={`grid h-10 w-10 shrink-0 place-items-center rounded-full border ${surface.line} ${inset}`}
            >
              <PhoneCall size={17} className={surface.muted} aria-hidden="true" />
            </div>
            <div>
              <p className="text-[14px] font-medium">
                {watching ? 'No call right now.' : 'Sleeping. I am not listening.'}
              </p>
              <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>
                {watching
                  ? 'When a call starts, Satya shows a small card and waits for your yes before listening.'
                  : 'Wake Satya from the mascot menu when you want him to watch for payment tricks.'}
              </p>
            </div>
          </div>
        )}
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
              style={{ backgroundColor: `${tone.coral}12` }}
            >
              <ShieldAlert size={17} style={{ color: tone.coral }} aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-semibold">{alert.headline}</p>
              <p className={`mt-1 text-[12px] ${surface.muted}`}>
                Raised {relativeTime(alert.at, now)}. Satya never changes this band on his own.
              </p>
            </div>
            <button
              type="button"
              onClick={() => onOpenCase(alert.caseId)}
              className={`${button.outline} shrink-0`}
            >
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
