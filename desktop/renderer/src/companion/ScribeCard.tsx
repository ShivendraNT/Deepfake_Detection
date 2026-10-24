import { motion, useReducedMotion } from 'framer-motion'
import { ExternalLink, FileText, Lock } from 'lucide-react'

import type { DraftArtifact } from '../../../shared/contracts'

export interface ScribeCardProps {
  draft: DraftArtifact | null
  busy: boolean
  onDraft: (kind: 'section63' | 'helpline_1930') => void
  onOpenWorkspace: () => void
}

export default function ScribeCard({ draft, busy, onDraft, onOpenWorkspace }: ScribeCardProps) {
  const reduced = useReducedMotion()

  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: reduced ? 0 : 0.3 }}
      className="rounded-[22px] border border-violet-400/25 bg-ink-900/88 p-3.5 backdrop-blur-2xl"
    >
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-full border border-violet-400/30 bg-violet-400/10 text-violet-200">
          <FileText size={15} />
        </span>
        <div>
          <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white/40">
            The Scribe
          </p>
          <h2 className="text-[13px] font-semibold text-white/95">
            {draft ? 'Draft ready — human review required' : 'Preparing an editable draft'}
          </h2>
        </div>
      </div>

      {draft ? (
        <>
          <div className="mt-2 flex flex-wrap gap-1">
            <span className="chip text-amber-200">{draft.kind === 'section63' ? 'Section 63' : 'Helpline 1930'}</span>
            <span className="chip">{draft.status.replaceAll('_', ' ')}</span>
            <span className="chip text-mint-200">{draft.submission}</span>
          </div>
          <div className="mt-2 max-h-[92px] space-y-1 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2 font-mono text-[9.5px] text-white/50 scrollbar-thin">
            {Object.entries(draft.fields)
              .slice(0, 6)
              .map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <span className="w-1/3 shrink-0 truncate text-white/35">{key}</span>
                  <span className="min-w-0 flex-1 truncate">{String(value ?? '—')}</span>
                </div>
              ))}
          </div>
          <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-snug text-white/45">
            <Lock size={11} className="mt-0.5 shrink-0 text-mint-300" />
            {draft.disclaimers[0]}
          </p>
          <button type="button" className="action-outline mt-2" onClick={onOpenWorkspace}>
            <ExternalLink size={13} /> Review in details
          </button>
        </>
      ) : (
        <p className="mt-2 text-[11px] leading-relaxed text-white/55">
          Capture is paused. I will build the draft only from the evidence you selected. Nothing is
          submitted anywhere.
        </p>
      )}

      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <button
          type="button"
          className="action-ghost border border-white/10 py-2"
          disabled={busy}
          onClick={() => onDraft('section63')}
        >
          Section 63
        </button>
        <button
          type="button"
          className="action-ghost border border-white/10 py-2"
          disabled={busy}
          onClick={() => onDraft('helpline_1930')}
        >
          1930 call aid
        </button>
      </div>
    </motion.section>
  )
}
