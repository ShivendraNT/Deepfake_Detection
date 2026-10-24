/**
 * CardShell — the canonical frame for all Satya bubble cards (MASCOT_SPEC §7).
 *
 * Geometry & Anti-slop constraints:
 * - 340 px width (within the 360 px transparent bubble window).
 * - Radius 18 px, 16 px padding.
 * - Solid theme background (no gradients, no glassmorphism blur).
 * - 12 px triangle tail facing Satya (left or right).
 * - Top header: accent state dot (8 px) + title (15 px / 600) + optional 28 px ghost '×'.
 * - Body: 13.5 px / 1.45.
 * - Stacked action buttons (max 3, 36 px tall, 10 px radius, primary first).
 * - Reports rendered height via ResizeObserver to `api.resizeBubble(h)`.
 */

import { useRef, type ReactNode } from 'react'
import { motion } from 'framer-motion'

import type { CardAction } from '../../../../shared/contracts'
import { motion as motionTokens } from '../../shared/tokens'

export interface CardShellProps {
  title: string
  accentColor?: string
  tail?: 'left' | 'right' | 'none'
  onClose?: () => void
  actions?: CardAction[]
  onAction?: (actionId: string) => void
  resolveActionLabel?: (actionId: string) => string
  children?: ReactNode
  /** Small element at the right of the title (timer, label). */
  badge?: ReactNode
  /** "row" puts up to three compact buttons side by side (passive cards). */
  actionsLayout?: 'stack' | 'row'
}

export default function CardShell({
  title,
  accentColor = '#1FB5A3',
  tail = 'left',
  onClose,
  actions = [],
  onAction,
  resolveActionLabel = (id) => id.replace(/_/g, ' '),
  children,
  badge,
  actionsLayout = 'stack',
}: CardShellProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement | null>(null)

  // Limit to max 3 actions per MASCOT_SPEC §7
  const displayActions = actions.slice(0, 3)

  return (
    <motion.div
      ref={containerRef}
      initial={{ opacity: 0, scale: 0.94, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, y: -6 }}
      transition={motionTokens.snappy}
      className="relative w-[340px] select-none rounded-[18px] border border-black/[0.08] dark:border-white/[0.10] bg-[#FFFCF7]/95 dark:bg-[#1C1828]/95 p-4 shadow-[0_12px_32px_rgba(20,16,40,0.22)]"
      style={{
        boxShadow: '0 12px 32px rgba(20,16,40,0.22)',
      }}
    >
      {/* 12px Directional Tail pointing toward Satya */}
      {tail === 'left' && (
        <div
          aria-hidden="true"
          className="absolute -left-[10px] top-6 h-0 w-0 border-y-[8px] border-r-[10px] border-y-transparent border-r-[#FFFCF7] dark:border-r-[#1C1828]"
        />
      )}
      {tail === 'right' && (
        <div
          aria-hidden="true"
          className="absolute -right-[10px] top-6 h-0 w-0 border-y-[8px] border-l-[10px] border-y-transparent border-l-[#FFFCF7] dark:border-l-[#1C1828]"
        />
      )}

      {/* Header Row: State Dot + Title + Optional Ghost Close '×' */}
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <span
            className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full"
            style={{ backgroundColor: accentColor }}
            aria-hidden="true"
          />
          <h2 className="min-w-0 flex-1 break-words text-[15px] font-semibold leading-snug text-[#2A2238] dark:text-[#EDE8F5]">
            {title}
          </h2>
        </div>

        {badge ? <div className="mt-0.5 flex-shrink-0">{badge}</div> : null}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-black/5 hover:text-slate-600 dark:text-[#A8A0B8] dark:hover:bg-white/5 dark:hover:text-white transition-colors"
          >
            <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M3 3 L13 13 M13 3 L3 13" />
            </svg>
          </button>
        )}
      </header>

      {/* Card Content Body */}
      {children && (
        <div className="mt-2 text-[13.5px] leading-[1.45] text-[#2A2238]/90 dark:text-[#EDE8F5]/90">
          {children}
        </div>
      )}

      {/* Stacked Actions (Max 3, Primary first, 36px tall, 10px radius) */}
      {displayActions.length > 0 && actionsLayout === 'row' && (
        <footer className="mt-3 flex gap-2">
          {displayActions.map((action) => (
            <button
              key={action.id}
              type="button"
              onClick={() => onAction?.(action.id)}
              style={action.variant === 'primary' ? { backgroundColor: accentColor } : undefined}
              className={
                action.variant === 'primary'
                  ? 'flex h-8 flex-1 items-center justify-center rounded-[10px] px-2 text-[12.5px] font-semibold text-white active:scale-[0.98]'
                  : 'flex h-8 flex-1 items-center justify-center rounded-[10px] border border-slate-300 px-2 text-[12.5px] font-medium text-[#2A2238] hover:bg-black/5 active:scale-[0.98] dark:border-white/20 dark:text-[#EDE8F5] dark:hover:bg-white/5'
              }
            >
              {resolveActionLabel(action.id)}
            </button>
          ))}
        </footer>
      )}

      {displayActions.length > 0 && actionsLayout === 'stack' && (
        <footer className="mt-4 flex flex-col gap-2">
          {displayActions.map((action) => {
            const label = resolveActionLabel(action.id)
            if (action.variant === 'primary') {
              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => onAction?.(action.id)}
                  style={{ backgroundColor: accentColor }}
                  className="flex h-9 w-full items-center justify-center rounded-[10px] px-3 text-[13px] font-semibold text-white transition-transform active:scale-[0.98] shadow-sm"
                >
                  {label}
                </button>
              )
            }
            if (action.variant === 'outline') {
              return (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => onAction?.(action.id)}
                  className="flex h-9 w-full items-center justify-center rounded-[10px] border border-slate-300 dark:border-white/20 bg-transparent px-3 text-[13px] font-medium text-[#2A2238] dark:text-[#EDE8F5] transition-colors hover:bg-black/5 dark:hover:bg-white/5 active:scale-[0.98]"
                >
                  {label}
                </button>
              )
            }
            return (
              <button
                key={action.id}
                type="button"
                onClick={() => onAction?.(action.id)}
                className="flex h-9 w-full items-center justify-center rounded-[10px] bg-transparent px-3 text-[13px] font-medium text-slate-500 dark:text-[#A8A0B8] transition-colors hover:bg-black/5 dark:hover:bg-white/5 hover:text-[#2A2238] dark:hover:text-white active:scale-[0.98]"
              >
                {label}
              </button>
            )
          })}
        </footer>
      )}
    </motion.div>
  )
}
