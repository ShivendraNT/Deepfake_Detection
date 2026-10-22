import { motion, useReducedMotion } from 'framer-motion'
import { Check, Lock, Mic, MonitorPlay, Mail, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import type { CompanionSource } from '../../../shared/contracts'
import { SOURCE_LABELS } from '../../../shared/contracts'

const OPTIONS: Array<{
  source: CompanionSource
  icon: typeof Mic
  description: string
  monitoring: boolean
}> = [
  {
    source: 'demo_replay',
    icon: MonitorPlay,
    description: 'Generated fixtures. No microphone, no screen, no network capture.',
    monitoring: false,
  },
  {
    source: 'user_selected_loopback',
    icon: MonitorPlay,
    description: 'Only the Meet/Teams tab you pick. A short in-memory analysis buffer.',
    monitoring: true,
  },
  {
    source: 'user_selected_microphone',
    icon: Mic,
    description: 'Your microphone only while this session is on. Stop anytime.',
    monitoring: true,
  },
  {
    source: 'user_selected_email',
    icon: Mail,
    description: 'Only the text or email you paste or drop. Nothing is scanned in the background.',
    monitoring: false,
  },
]

export interface ConsentCardProps {
  value: CompanionSource
  onChange: (source: CompanionSource) => void
  onStart: (source: CompanionSource) => void
  onCancel: () => void
  busy: boolean
}

export default function ConsentCard({ value, onChange, onStart, onCancel, busy }: ConsentCardProps) {
  const reduced = useReducedMotion()
  const [acknowledged, setAcknowledged] = useState(false)
  const selected = OPTIONS.find((option) => option.source === value) ?? OPTIONS[0]

  return (
    <motion.div
      className="absolute inset-0 z-30 grid place-items-end bg-ink-950/55 p-2 backdrop-blur-md"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduced ? 0 : 0.2 }}
    >
      <motion.div
        initial={{ y: 24, opacity: 0, scale: 0.98 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        exit={{ y: 18, opacity: 0 }}
        transition={{ duration: reduced ? 0 : 0.32, ease: [0.22, 1, 0.36, 1] }}
        className="max-h-full w-full overflow-y-auto rounded-[24px] border border-mint-400/20 bg-ink-900/95 p-4 shadow-glass scrollbar-thin"
      >
        <div className="mb-2 flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-full border border-mint-400/30 bg-mint-400/10 text-mint-300">
            <ShieldCheck size={16} />
          </span>
          <div>
            <h2 className="text-[14px] font-semibold text-white">Before I watch</h2>
            <p className="text-[10px] text-white/45">You are in Sleep / DND right now.</p>
          </div>
        </div>

        <p className="mb-3 text-[11.5px] leading-relaxed text-white/60">
          I only process the source you choose. I never set a risk band, never capture your
          keyboard, and never submit anything to a bank or the police.
        </p>

        <div className="space-y-1.5">
          {OPTIONS.map((option) => {
            const Icon = option.icon
            const active = option.source === value
            return (
              <button
                key={option.source}
                type="button"
                onClick={() => onChange(option.source)}
                className={`w-full rounded-2xl border p-2.5 text-left transition ${
                  active
                    ? 'border-mint-400/45 bg-mint-400/[0.08]'
                    : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} className={active ? 'text-mint-300' : 'text-white/45'} />
                  <span className="text-[12px] font-medium text-white/90">
                    {SOURCE_LABELS[option.source]}
                  </span>
                  <span className="ml-auto rounded-full border border-white/10 px-1.5 py-0.5 text-[9px] text-white/45">
                    {option.monitoring ? 'MONITORING ON' : 'NO CAPTURE'}
                  </span>
                </div>
                <p className="mt-1 pl-6 text-[10.5px] leading-snug text-white/45">
                  {option.description}
                </p>
              </button>
            )
          })}
        </div>

        <ul className="mt-3 space-y-1 text-[10.5px] text-white/50">
          <li className="flex items-center gap-1.5">
            <Lock size={11} className="text-mint-300" /> No raw scores. Only reasons and evidence.
          </li>
          <li className="flex items-center gap-1.5">
            <Check size={11} className="text-mint-300" /> Stop watching in one click, always.
          </li>
        </ul>

        <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-xl border border-white/10 bg-white/[0.02] p-2.5">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
            className="mt-0.5 h-3.5 w-3.5 accent-emerald-400"
          />
          <span className="text-[10.5px] leading-snug text-white/55">
            I understand Satya is fallible, does not prove who is speaking, and that verification
            happens through a saved contact — not this call or message.
          </span>
        </label>

        <div className="mt-3 flex gap-2">
          <button type="button" className="action-outline" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="action-primary"
            disabled={!acknowledged || busy}
            onClick={() => onStart(selected.source)}
          >
            {busy ? 'Starting…' : selected.monitoring ? 'Start watching' : 'Use this source'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
