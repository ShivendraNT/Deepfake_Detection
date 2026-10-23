/**
 * Video-call liveness tips. Real-time face swaps tend to break on profile views and when a hand
 * passes in front of the face. This is a nudge, not a detector: passing proves nothing, which
 * is why the card ends by pointing back to verifying the payment.
 */

import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface LivenessCardProps {
  card: Extract<BubbleCard, { kind: 'liveness' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function LivenessCard({ card, lang = 'en', tail = 'left', onAction, onClose }: LivenessCardProps): JSX.Element {
  return (
    <CardShell
      title={t('liveness.title', lang)}
      accentColor={color.write}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={(id) => t(`action.${id}`, lang)}
    >
      <p className="m-0 text-[13px] text-slate-600 dark:text-[#A8A0B8]">{t('liveness.body', lang)}</p>
      <ol className="mb-0 mt-2 space-y-1.5 pl-0">
        {['liveness.1', 'liveness.2', 'liveness.3'].map((key, index) => (
          <li key={key} className="flex list-none items-center gap-2 text-[13px] text-[#2A2238] dark:text-[#EDE8F5]">
            <span
              className="grid h-5 w-5 flex-shrink-0 place-items-center rounded-full text-[11px] font-bold text-white"
              style={{ backgroundColor: color.write }}
            >
              {index + 1}
            </span>
            {t(key, lang)}
          </li>
        ))}
      </ol>
      <p className="mb-0 mt-2 text-[12px] font-medium text-slate-500 dark:text-[#A8A0B8]">{t('liveness.note', lang)}</p>
    </CardShell>
  )
}
