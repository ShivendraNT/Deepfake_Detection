import { motion } from 'framer-motion'
import { Eye, EyeOff, ShieldCheck, Volume2, VolumeX } from 'lucide-react'

import type { Band, CompanionMode, ConnectionStatus } from '../../../shared/contracts'
import { DEMO_REPLAY_LABEL } from '../../../shared/contracts'

const MODE_TONE: Record<CompanionMode, string> = {
  SLEEP: 'text-white/50 border-white/10 bg-white/[0.04]',
  ACTIVE: 'text-mint-300 border-mint-400/30 bg-mint-400/10',
  INVESTIGATING: 'text-sky-300 border-sky-400/30 bg-sky-400/10',
  ALERT: 'text-amber-300 border-amber-400/30 bg-amber-400/10',
  SCRIBE: 'text-violet-300 border-violet-400/30 bg-violet-400/10',
  DISABLED: 'text-white/35 border-white/10 bg-white/[0.02]',
}

const BAND_TONE: Record<Band, string> = {
  PASS: 'text-mint-300 border-mint-400/30 bg-mint-400/10',
  VERIFY: 'text-amber-300 border-amber-400/30 bg-amber-400/10',
  HOLD: 'text-rose-300 border-rose-400/30 bg-rose-400/10',
}

export interface StatusBarProps {
  mode: CompanionMode
  modeLabel: string
  monitoring: boolean
  demo: boolean
  band: Band | null
  connection: ConnectionStatus
  soundOn: boolean
  onToggleSound: () => void
  onHide: () => void
  onWorkspace: () => void
}

export default function StatusBar({
  mode,
  modeLabel,
  monitoring,
  demo,
  band,
  connection,
  soundOn,
  onToggleSound,
  onHide,
  onWorkspace,
}: StatusBarProps) {
  const dot = connection.mock
    ? 'bg-amber-400'
    : connection.connected
      ? 'bg-mint-400'
      : 'bg-rose-400'

  return (
    <header className="drag flex flex-col gap-1 px-3 pb-1 pt-2.5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onWorkspace}
          className="no-drag flex items-center gap-1.5 text-left"
          title="Open case details"
        >
          <span className="grid h-6 w-6 place-items-center rounded-full border border-mint-400/30 bg-mint-400/10 text-mint-300">
            <ShieldCheck size={12} />
          </span>
          <span className="text-[12px] font-semibold tracking-tight text-white/90">Satya</span>
        </button>

        <span className={`pill ${MODE_TONE[mode]}`}>
          <motion.span
            className={`h-1.5 w-1.5 rounded-full ${monitoring ? 'bg-mint-400' : dot}`}
            animate={monitoring ? { opacity: [1, 0.35, 1] } : undefined}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
          {modeLabel}
        </span>

        {band && <span className={`pill ${BAND_TONE[band]}`}>{band}</span>}

        <div className="no-drag ml-auto flex items-center gap-1">
          <button
            type="button"
            className="icon-button"
            onClick={onToggleSound}
            title={soundOn ? 'Mute cues' : 'Enable soft cues'}
          >
            {soundOn ? <Volume2 size={13} /> : <VolumeX size={13} />}
          </button>
          <button type="button" className="icon-button" onClick={onHide} title="Hide (stops capture)">
            {monitoring ? <Eye size={13} /> : <EyeOff size={13} />}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 overflow-hidden">
        <span className={`h-1 w-1 shrink-0 rounded-full ${dot}`} />
        <span className="truncate text-[8.5px] uppercase tracking-[0.14em] text-white/30">
          {connection.mock ? 'Local replay — not live' : `Local engine · ${connection.backendUrl}`}
        </span>
        {demo && (
          <span className="ml-auto shrink-0 rounded-full border border-amber-400/25 bg-amber-400/[0.07] px-1.5 py-0.5 text-[7.5px] font-semibold tracking-wide text-amber-200/80">
            {DEMO_REPLAY_LABEL}
          </span>
        )}
      </div>
    </header>
  )
}
