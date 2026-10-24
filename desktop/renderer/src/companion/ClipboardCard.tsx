import { ClipboardCheck, ExternalLink, X } from 'lucide-react'

import type { ClipboardCheck as ClipboardResult } from '../../../shared/contracts'
import SpeechBubble from './SpeechBubble'

export interface ClipboardCardProps {
  check: ClipboardResult
  onDismiss: () => void
  onWorkspace: () => void
}

export default function ClipboardCard({ check, onDismiss, onWorkspace }: ClipboardCardProps) {
  return (
    <SpeechBubble
      tone={check.suspicious ? 'amber' : 'slate'}
      eyebrow="Clipboard check"
      title={check.suspicious ? 'This text has risk patterns' : 'No strong pattern found'}
      onDismiss={onDismiss}
      dismissLabel="Close"
      footer={
        <button type="button" className="action-outline" onClick={onWorkspace}>
          <ExternalLink size={12} /> Check a payment in details
        </button>
      }
    >
      <div className="mb-1.5 flex flex-wrap gap-1">
        {(check.matches.length ? check.matches : ['Nothing flagged']).map((match: string) => (
          <span key={match} className="chip">
            <ClipboardCheck size={10} className="mr-1" />
            {match}
          </span>
        ))}
      </div>
      <p className="max-h-16 overflow-y-auto rounded-lg border border-white/10 bg-black/20 p-1.5 font-mono text-[9.5px] text-white/45 scrollbar-thin">
        {check.preview || 'Clipboard is empty.'}
      </p>
      <p className="mt-1 text-[9.5px] text-white/35">{check.note}</p>
    </SpeechBubble>
  )
}

export function AlertStrip({
  band,
  onReview,
  onDismiss,
}: {
  band: string
  onReview: () => void
  onDismiss: () => void
}) {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-amber-400/25 bg-amber-400/[0.07] px-3 py-2 text-[11px] text-amber-100/90">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-300" />
      <span className="min-w-0 flex-1 truncate">Alert kept in the case timeline — band {band}</span>
      <button type="button" className="action-ghost" onClick={onReview}>
        Review
      </button>
      <button type="button" className="action-ghost px-1" onClick={onDismiss} aria-label="Dismiss">
        <X size={12} />
      </button>
    </div>
  )
}
