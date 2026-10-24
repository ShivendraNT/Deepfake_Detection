import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

import { api } from '../../shared/api'
import { shortHash } from '../lib/format'
import { FONT_MONO, focusRing, surface } from './theme'

export interface HashProps {
  value: string
  label?: string
  head?: number
  className?: string
}

/**
 * A short monospace hash with a copy button. The full value is copied, never shown as a score.
 */
export default function Hash({ value, label, head = 10, className = '' }: HashProps): JSX.Element {
  const [copied, setCopied] = useState(false)

  async function copy(): Promise<void> {
    const result = await api.copyText(value)
    if (!result.ok) return
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 ${className}`}>
      {label ? <span className={`text-[12px] ${surface.muted}`}>{label}</span> : null}
      <code
        className="rounded-[6px] bg-[rgba(42,34,56,0.05)] px-1.5 py-0.5 text-[12px] text-[#2A2238] dark:bg-[rgba(237,232,245,0.07)] dark:text-[#EDE8F5]"
        style={{ fontFamily: FONT_MONO }}
        title={value}
      >
        {shortHash(value, head)}
      </code>
      <button
        type="button"
        onClick={() => void copy()}
        aria-label={copied ? 'Hash copied' : 'Copy hash'}
        title={copied ? 'Copied' : 'Copy full hash'}
        className={`${focusRing} grid h-6 w-6 shrink-0 place-items-center rounded-[6px] ${surface.muted} transition ${surface.hover}`}
      >
        {copied ? (
          <Check size={12} aria-hidden="true" />
        ) : (
          <Copy size={12} aria-hidden="true" />
        )}
      </button>
    </span>
  )
}
