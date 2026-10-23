import type { Band, BubbleCard } from '../../../../../shared/contracts'
import { t, translateHeadline, translateReason, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface AlertCardProps {
  card: Extract<BubbleCard, { kind: 'alert' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
  approverName?: string
}

const BAND_ACCENT: Record<Band, string> = {
  HOLD: color.hold,
  VERIFY: color.verify,
  PASS: color.good,
}

export default function AlertCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
  approverName = 'Approver',
}: AlertCardProps): JSX.Element {
  const accent = BAND_ACCENT[card.band] ?? '#FF6B5E'

  // Format chips string for body text if present
  const chipsText = card.chips.map((c) => t(`ask.${c.code}`, lang)).join(', ')
  const fallbackChips = t('alert.chips_fallback', lang)
  const bodyText = t('alert.body', lang, {
    chips: chipsText || fallbackChips,
    approver: approverName,
  })

  function resolveLabel(actionId: string): string {
    if (actionId === 'verify' || actionId === 'verify_with_approver' || actionId === 'oob_verify') {
      return t('action.verify', lang, { approver: approverName })
    }
    if (actionId === 'copy_safe_reply') {
      return t('action.copy_reply', lang)
    }
    return t(`action.${actionId}`, lang)
  }

  const title = translateHeadline(card.headline || '', lang, card.band)

  return (
    <CardShell
      title={title}
      accentColor={accent}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={resolveLabel}
    >
      <div className="space-y-3">
        <p className="text-[13.5px] leading-[1.45] text-slate-600 dark:text-[#A8A0B8]">
          {bodyText}
        </p>

        {/* Chips Row: MASCOT_SPEC §7 all chips same accent color at 14% opacity */}
        {card.chips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {card.chips.map((chip, idx) => (
              <span
                key={`${chip.code}-${idx}`}
                style={{
                  backgroundColor: `${accent}24`,
                  color: '#2A2238',
                }}
                className="rounded-full px-2.5 py-1 text-[12px] font-medium dark:!text-[#EDE8F5]"
              >
                {t(`ask.${chip.code}`, lang)}
              </span>
            ))}
          </div>
        )}

        {card.reasons.length > 0 && (
          <ul className="space-y-1 text-[12.5px] text-slate-500 dark:text-[#A8A0B8]">
            {card.reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-slate-400 dark:bg-white/40" />
                <span>{translateReason(reason, lang)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </CardShell>
  )
}

