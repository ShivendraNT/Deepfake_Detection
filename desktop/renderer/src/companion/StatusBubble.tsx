import { motion, useReducedMotion } from 'framer-motion'
import { ClipboardCheck, ExternalLink, Eye, EyeOff, MonitorPlay, Square } from 'lucide-react'

import type { Band, CompanionMode, ConnectionStatus } from '../../../shared/contracts'
import { DEMO_REPLAY_LABEL } from '../../../shared/contracts'
import SpeechBubble from './SpeechBubble'

export interface StatusBubbleProps {
  mode: CompanionMode
  modeLabel: string
  monitoring: boolean
  sourceLabel: string | null
  demo: boolean
  band: Band | null
  connection: ConnectionStatus
  headline?: string
  explanation?: string
  busy: boolean
  onStart: () => void
  onStop: () => void
  onDemo: () => void
  onWorkspace: () => void
  onCheckClipboard: () => void
}

export default function StatusBubble({
  mode,
  modeLabel,
  monitoring,
  sourceLabel,
  demo,
  band,
  connection,
  headline,
  explanation,
  busy,
  onStart,
  onStop,
  onDemo,
  onWorkspace,
  onCheckClipboard,
}: StatusBubbleProps) {
  const reduced = useReducedMotion()

  if (mode === 'DISABLED') {
    return (
      <SpeechBubble
        tone="slate"
        eyebrow="Disabled"
        title="Companion disabled"
        footer={
          <button type="button" className="action-primary" onClick={onStart}>
            Enable and choose a source
          </button>
        }
      >
        Capture and session resources are released. Satya is out of the way.
      </SpeechBubble>
    )
  }

  if (mode === 'INVESTIGATING') {
    return (
      <SpeechBubble
        tone="mint"
        eyebrow="Investigating"
        title={headline ?? 'Checking only the evidence you submitted'}
        footer={
          <button type="button" className="action-outline" onClick={onStop} disabled={busy}>
            <Square size={12} /> Cancel and stop
          </button>
        }
      >
        {explanation || 'No hidden screen scraping. The source and time range stay visible.'}
        <span className="mt-1 flex gap-1">
          {[0, 1, 2].map((index) => (
            <motion.span
              key={index}
              className="h-1 w-1 rounded-full bg-mint-300"
              animate={reduced ? undefined : { opacity: [0.2, 1, 0.2], y: [0, -2, 0] }}
              transition={{ duration: 1.1, delay: index * 0.16, repeat: Infinity }}
            />
          ))}
        </span>
      </SpeechBubble>
    )
  }

  if (mode === 'ACTIVE') {
    return (
      <SpeechBubble
        tone={monitoring ? 'mint' : 'slate'}
        eyebrow={monitoring ? 'Watching' : 'Ready'}
        title={monitoring ? `Watching: ${sourceLabel ?? 'selected source'}` : 'Ready for the source you chose'}
        footer={
          <>
            <div className="flex gap-1.5">
              <button type="button" className="action-outline" onClick={onStop} disabled={busy}>
                <Square size={12} /> Stop watching
              </button>
              <button type="button" className="action-outline" onClick={onCheckClipboard}>
                <ClipboardCheck size={12} /> Clipboard
              </button>
            </div>
            <button type="button" className="action-ghost w-full" onClick={onWorkspace}>
              <ExternalLink size={12} /> View details
            </button>
          </>
        }
      >
        <div className="mb-1.5 flex flex-wrap gap-1">
          <span className="pill">
            {monitoring ? <Eye size={10} className="text-mint-300" /> : <EyeOff size={10} />}
            {monitoring ? 'MONITORING ON' : 'NO CAPTURE'}
          </span>
          {demo && <span className="pill">{DEMO_REPLAY_LABEL}</span>}
          {band && <span className="pill">Band: {band}</span>}
        </div>
        Only the source you chose is processed. Audio stays in a short in-memory buffer unless you
        explicitly preserve evidence.
      </SpeechBubble>
    )
  }

  if (mode === 'SCRIBE') {
    return (
      <SpeechBubble
        tone="slate"
        eyebrow="Scribe"
        title="Drafting from selected evidence only"
        footer={
          <button type="button" className="action-outline" onClick={onWorkspace}>
            <ExternalLink size={12} /> Review in details
          </button>
        }
      >
        Capture is paused by default. Nothing is submitted, dialled or filed.
      </SpeechBubble>
    )
  }

  return (
    <SpeechBubble
      tone="mint"
      eyebrow={modeLabel}
      title="I'm asleep. Nothing is being watched."
      footer={
        <>
          <button type="button" className="action-primary" onClick={onStart}>
            <Eye size={14} /> Choose a source
          </button>
          <div className="flex gap-1.5">
            <button type="button" className="action-outline" onClick={onDemo} disabled={busy}>
              <MonitorPlay size={13} /> Run labeled replay
            </button>
            <button type="button" className="action-outline" onClick={onWorkspace}>
              <ExternalLink size={13} /> Details
            </button>
          </div>
        </>
      }
    >
      Satya starts in Sleep / DND. Pick exactly one source and see the scope before monitoring can
      begin. No money moves from here.
      {!connection.connected && (
        <span className="mt-2 block text-[10px] text-white/35">
          {connection.mock
            ? 'Local replay fixtures — backend not running. Everything is labelled.'
            : `Backend offline (${connection.backendUrl}). Start it with make run.`}
        </span>
      )}
    </SpeechBubble>
  )
}
