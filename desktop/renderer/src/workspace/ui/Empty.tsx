import { Inbox } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { surface } from './theme'

export interface EmptyProps {
  icon?: LucideIcon
  title: string
  body?: string
  action?: ReactNode
  className?: string
}

/** A quiet empty state. No illustrations, no emoji, no invented content. */
export default function Empty({
  icon: Icon = Inbox,
  title,
  body,
  action,
  className = '',
}: EmptyProps): JSX.Element {
  return (
    <div className={`grid place-items-center px-6 py-10 text-center ${className}`}>
      <div
        className={`grid h-10 w-10 place-items-center rounded-full border ${surface.line} ${surface.inset}`}
      >
        <Icon size={18} className={surface.muted} aria-hidden="true" />
      </div>
      <p className="mt-3 text-[14px] font-medium">{title}</p>
      {body ? (
        <p className={`mt-1 max-w-[400px] text-[12px] leading-relaxed ${surface.muted}`}>{body}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
