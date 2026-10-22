import type { ReactNode } from 'react'

import { card, surface } from './theme'

export interface SectionProps {
  title?: string
  description?: string
  action?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

/** A calm paper card with an optional header row. */
export default function Section({
  title,
  description,
  action,
  children,
  className = '',
  bodyClassName = 'p-4',
}: SectionProps): JSX.Element {
  const hasHeader = Boolean(title || description || action)

  return (
    <section className={`${card} min-w-0 overflow-hidden ${className}`}>
      {hasHeader ? (
        <header
          className={`flex items-start justify-between gap-4 border-b px-4 py-3 ${surface.line}`}
        >
          <div className="min-w-0">
            {title ? (
              <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{title}</h2>
            ) : null}
            {description ? (
              <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>{description}</p>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}
