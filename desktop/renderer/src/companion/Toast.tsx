import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'

export interface ToastProps {
  toast: { text: string; tone: 'info' | 'warn' | 'error' } | null
}

const STYLES = {
  info: 'border-mint-400/25 text-mint-100',
  warn: 'border-amber-400/30 text-amber-100',
  error: 'border-rose-400/35 text-rose-100',
}

const ICONS = {
  info: CheckCircle2,
  warn: AlertTriangle,
  error: Info,
}

export default function Toast({ toast }: ToastProps) {
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8 }}
          className={`absolute inset-x-3 bottom-9 z-40 flex items-start gap-2 rounded-2xl border bg-ink-950/95 px-3 py-2 text-[10.5px] leading-snug shadow-glass backdrop-blur-xl ${STYLES[toast.tone]}`}
          role="status"
          aria-live="polite"
        >
          {(() => {
            const Icon = ICONS[toast.tone]
            return <Icon size={13} className="mt-0.5 shrink-0" />
          })()}
          <span>{toast.text}</span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
