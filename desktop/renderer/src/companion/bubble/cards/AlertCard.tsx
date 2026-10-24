/**
 * "Pause before you pay." — the one alert that matters. It quotes the exact words that raised it,
 * says plainly that this does not prove who is speaking, and offers ONE safe next step: verify the
 * transaction with the real approver on their own phone (OOB-Confirm).
 */

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
}

const BAND_ACCENT: Record<Band, string> = {
  HOLD: color.hold,
  VERIFY: color.verify,
  PASS: color.good,
}

const HIDDEN_REASONS = new Set(['FLOOR_NONE'])

export default function AlertCard({ card, lang = 'en', tail = 'left', onAction, onClose }: AlertCardProps): JSX.Element {
  const accent = BAND_ACCENT[card.band] ?? color.hold
  const approver = card.approver ?? 'the approver'
  const quotes = card.quotes ?? []
  const quotedCodes = new Set(quotes.map((q) => q.code))
  const extraChips = card.chips.filter((chip) => !quotedCodes.has(chip.code))
  const reasons = card.reasons.filter((r) => !HIDDEN_REASONS.has(r) && !r.startsWith('ASK_'))

  function resolveLabel(actionId: string): string {
    if (actionId === 'verify' || actionId === 'verify_with_approver' || actionId === 'oob_verify') {
      return t('action.verify', lang, { approver })
    }
    if (actionId === 'copy_reply' || actionId === 'copy_safe_reply') return t('action.copy_reply', lang)
    return t(`action.${actionId}`, lang)
  }

  const title = card.context === 'call' || !card.headline ? t('alert.title', lang) : translateHeadline(card.headline, lang, card.band)

  return (
    <CardShell
      title={title}
      accentColor={accent}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={resolveLabel}
      badge={
        <span
          className="rounded-full px-2 py-0.5 text-[11.5px] font-semibold text-white"
          style={{ backgroundColor: accent }}
        >
          {t(`result.${card.band}`, lang).replace(/[.।]$/, '')}
        </span>
      }
    >
      {quotes.length > 0 ? (
        <div className="space-y-1.5">
          <p className="m-0 text-[12px] font-semibold text-slate-500 dark:text-[#A8A0B8]">{t('alert.said', lang)}</p>
          {quotes.slice(0, 3).map((quote) => (
            <div
              key={quote.code}
              className="flex items-start gap-2 rounded-lg px-2.5 py-1.5"
              style={{ backgroundColor: `${accent}14`, borderLeft: `3px solid ${accent}` }}
            >
              <span className="min-w-0 flex-1 text-[13px] italic leading-snug text-[#2A2238] dark:text-[#EDE8F5]">
                “{quote.text}”
              </span>
              <span className="mt-0.5 flex-shrink-0 whitespace-nowrap rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-semibold text-[#2A2238] dark:bg-black/30 dark:text-white">
                {t(`ask.${quote.code}`, lang)}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {extraChips.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {extraChips.map((chip) => (
            <span
              key={chip.code}
              className="rounded-full px-2.5 py-1 text-[12px] font-medium text-[#2A2238] dark:text-[#EDE8F5]"
              style={{ backgroundColor: `${accent}24` }}
            >
              {t(`ask.${chip.code}`, lang)}
            </span>
          ))}
        </div>
      ) : null}

      <p className="mb-0 mt-2.5 text-[13px] leading-[1.45] text-slate-600 dark:text-[#A8A0B8]">
        {card.approver ? t('alert.body.v2', lang, { approver }) : t('alert.body.personal', lang)}
      </p>

      {reasons.length > 0 ? (
        <ul className="mb-0 mt-2 space-y-1 pl-0 text-[12.5px] text-slate-500 dark:text-[#A8A0B8]">
          {reasons.slice(0, 3).map((reason) => (
            <li key={reason} className="flex list-none items-start gap-1.5">
              <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-slate-400 dark:bg-white/40" />
              <span>{translateReason(reason, lang)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </CardShell>
  )
}
