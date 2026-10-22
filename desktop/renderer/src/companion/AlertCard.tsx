import { motion, useReducedMotion } from 'framer-motion'
import {
  AlertTriangle,
  Copy,
  ExternalLink,
  FileText,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'

import type { Band, NextAction } from '../../../shared/contracts'
import { DEMO_REPLAY_LABEL } from '../../../shared/contracts'
import { BAND_COPY, reasonLabel } from './reasonLabels'
import { useTypewriter } from './useTypewriter'

const ICONS: Record<Band, typeof ShieldCheck> = {
  PASS: ShieldCheck,
  VERIFY: AlertTriangle,
  HOLD: ShieldAlert,
}

const EYEBROW: Record<Band, string> = {
  PASS: 'No blocking finding',
  VERIFY: 'Independent verification needed',
  HOLD: 'Pause this payment',
}

export interface AlertCardProps {
  band: Band
  headline: string
  explanation: string
  reasonCodes: string[]
  evidenceIds: string[]
  actions: NextAction[]
  demo: boolean
  onAction: (id: string) => void
  onCopy: () => void
  onDismiss: () => void
}

export default function AlertCard({
  band,
  headline,
  explanation,
  reasonCodes,
  evidenceIds,
  actions,
  demo,
  onAction,
  onCopy,
  onDismiss,
}: AlertCardProps) {
  const reduced = useReducedMotion()
  const tone = BAND_COPY[band] ?? BAND_COPY.VERIFY
  const Icon = ICONS[band]
  const typed = useTypewriter(explanation, 16, 8)
  const primary = actions.find((action) => action.variant === 'primary') ?? actions[0]
  const secondary = actions.filter((action) => action.id !== primary?.id)

  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 14, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.98 }}
      transition={{ duration: reduced ? 0 : 0.34, ease: [0.22, 1, 0.36, 1] }}
      className={`relative overflow-hidden rounded-[22px] border bg-ink-900/90 p-3.5 backdrop-blur-2xl ${tone.border}`}
    >
      <motion.div
        className="pointer-events-none absolute inset-x-0 -top-16 h-24 bg-gradient-to-b from-white/[0.06] to-transparent"
        animate={reduced ? undefined : { opacity: [0.4, 0.9, 0.4] }}
        transition={{ duration: 3.8, repeat: Infinity }}
      />

      <div className="relative flex items-start gap-2">
        <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full border ${tone.border} ${tone.text} ${tone.bg}`}>
          <Icon size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white/45">
              {EYEBROW[band]}
            </p>
            <span className={`rounded-full border px-1.5 py-0.5 text-[9px] font-bold ${tone.border} ${tone.text} ${tone.bg}`}>
              {tone.label}
            </span>
            {demo && (
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[8px] font-semibold tracking-wide text-white/45">
                REPLAY
              </span>
            )}
          </div>
          <h2 className="mt-0.5 text-balance text-[13.5px] font-semibold leading-snug text-white/95">
            {headline}
          </h2>
        </div>
        <button type="button" onClick={onDismiss} className="action-ghost -mr-1 -mt-1 shrink-0">
          Not now
        </button>
      </div>

      <p className="relative mt-2 max-h-[92px] overflow-y-auto whitespace-pre-line text-[11px] leading-relaxed text-white/62 scrollbar-thin">
        {typed}
        {typed.length < explanation.length && (
          <motion.span
            className="ml-0.5 inline-block h-3 w-1 translate-y-0.5 bg-mint-300/80"
            animate={reduced ? undefined : { opacity: [1, 0] }}
            transition={{ duration: 0.7, repeat: Infinity }}
          />
        )}
      </p>

      {reasonCodes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {reasonCodes.slice(0, 6).map((code) => (
            <span key={code} className="chip" title={code}>
              {reasonLabel(code)}
            </span>
          ))}
        </div>
      )}

      {evidenceIds.length > 0 && (
        <p className="mt-1.5 truncate font-mono text-[9px] text-white/30">
          evidence: {evidenceIds.join(' · ')}
        </p>
      )}

      <div className="mt-3 space-y-1.5">
        {primary && (
          <button
            type="button"
            className={band === 'PASS' ? 'action-primary' : 'action-primary'}
            onClick={() => onAction(primary.id)}
          >
            <ShieldCheck size={14} />
            {primary.label}
          </button>
        )}
        <div className="flex gap-1.5">
          {secondary.map((action) => (
            <button
              key={action.id}
              type="button"
              className="action-outline"
              onClick={() => onAction(action.id)}
            >
              {action.id === 'open_scribe' ? <FileText size={13} /> : <ExternalLink size={13} />}
              {action.label}
            </button>
          ))}
        </div>
        <button type="button" className="action-ghost w-full" onClick={onCopy}>
          <Copy size={12} /> Copy a refusal script (discloses nothing)
        </button>
      </div>

      {demo && (
        <p className="mt-2 text-center text-[8.5px] font-semibold tracking-[0.14em] text-white/30">
          {DEMO_REPLAY_LABEL}
        </p>
      )}
    </motion.section>
  )
}
