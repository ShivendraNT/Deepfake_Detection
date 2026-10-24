import { motion, useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'

export interface SpeechBubbleProps {
  eyebrow?: string
  title: string
  children?: ReactNode
  footer?: ReactNode
  tone?: 'mint' | 'amber' | 'rose' | 'slate'
  onDismiss?: () => void
  dismissLabel?: string
}

const TONES = {
  mint: 'border-mint-400/20 shadow-[0_18px_50px_-30px_rgba(94,233,184,0.6)]',
  amber: 'border-amber-400/25 shadow-[0_18px_50px_-30px_rgba(255,195,92,0.6)]',
  rose: 'border-rose-400/25 shadow-[0_18px_50px_-30px_rgba(255,138,138,0.55)]',
  slate: 'border-white/10',
}

const DOTS = {
  mint: 'bg-mint-400',
  amber: 'bg-amber-400',
  rose: 'bg-rose-400',
  slate: 'bg-white/40',
}

export default function SpeechBubble({
  eyebrow,
  title,
  children,
  footer,
  tone = 'mint',
  onDismiss,
  dismissLabel = 'Not now',
}: SpeechBubbleProps) {
  const reduced = useReducedMotion()
  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ duration: reduced ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
      className={`relative w-full rounded-[22px] border bg-ink-900/85 p-3.5 backdrop-blur-2xl ${TONES[tone]}`}
    >
      <div className="flex items-start gap-2">
        <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${DOTS[tone]}`} />
        <div className="min-w-0 flex-1">
          {eyebrow && (
            <p className="mb-0.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-white/40">
              {eyebrow}
            </p>
          )}
          <h2 className="text-balance text-[13.5px] font-semibold leading-snug text-white/95">
            {title}
          </h2>
        </div>
        {onDismiss && (
          <button type="button" onClick={onDismiss} className="action-ghost -mr-1 -mt-1 shrink-0">
            {dismissLabel}
          </button>
        )}
      </div>

      {children && <div className="mt-2 text-[11.5px] leading-relaxed text-white/60">{children}</div>}
      {footer && <div className="mt-3 space-y-1.5">{footer}</div>}
    </motion.section>
  )
}
