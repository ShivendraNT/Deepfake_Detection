import { AlertTriangle, CheckCircle2, PauseCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { Band } from '../../../../shared/contracts'
import { BAND_WORD } from '../lib/format'
import { tone } from './theme'

interface BandConfig {
  label: string
  color: string
  Icon: LucideIcon
}

const BANDS: Record<Band, BandConfig> = {
  PASS: { label: BAND_WORD.PASS, color: tone.green, Icon: CheckCircle2 },
  VERIFY: { label: BAND_WORD.VERIFY, color: tone.amber, Icon: AlertTriangle },
  HOLD: { label: BAND_WORD.HOLD, color: tone.coral, Icon: PauseCircle },
}

export interface BandBadgeProps {
  band: Band
  size?: 'sm' | 'md'
  className?: string
}

/**
 * Words, never scores. The band already comes from satyapan.policy; this component only paints it.
 */
export default function BandBadge({ band, size = 'md', className = '' }: BandBadgeProps): JSX.Element {
  const config = BANDS[band]
  const Icon = config.Icon
  const compact = size === 'sm'

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border font-semibold ${
        compact ? 'px-2 py-0.5 text-[12px]' : 'px-2.5 py-1 text-[13px]'
      } ${className}`}
      style={{
        color: config.color,
        backgroundColor: `${config.color}14`,
        borderColor: `${config.color}40`,
      }}
      data-band={band}
      title={band}
    >
      <Icon size={compact ? 12 : 14} strokeWidth={2.2} aria-hidden="true" />
      <span>{config.label}</span>
    </span>
  )
}
