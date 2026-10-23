import type { Band, BubbleCard } from '../../../../../shared/contracts'
import { t, translateHeadline, translateReason, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface ResultCardProps {
  card: Extract<BubbleCard, { kind: 'result' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

const BAND_ACCENT: Record<Band, string> = {
  PASS: color.good,
  VERIFY: color.verify,
  HOLD: color.hold,
}

export default function ResultCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
}: ResultCardProps): JSX.Element {
  const accent = BAND_ACCENT[card.band] ?? '#FFB020'
  const title = translateHeadline(card.headline || '', lang, card.band)

  function resolveLabel(actionId: string): string {
    return t(`action.${actionId}`, lang)
  }

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
      {card.reasons.length > 0 && (
        <ul className="space-y-1.5 text-[13px] text-slate-600 dark:text-[#A8A0B8]">
          {card.reasons.map((reason, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400 dark:bg-white/40" />
              <span>{translateReason(reason, lang)}</span>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  )
}

