/** A plain note from Satya (setup problems, "the call ended"). Title/body may be copy keys. */

import type { BubbleCard } from '../../../../../shared/contracts'
import { t, tx, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface NoticeCardProps {
  card: Extract<BubbleCard, { kind: 'notice' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function NoticeCard({ card, lang = 'en', tail = 'left', onAction, onClose }: NoticeCardProps): JSX.Element {
  const accent = card.tone === 'good' ? color.good : card.tone === 'warn' ? color.verify : color.sleep
  const [titleKey, titleVars] = card.title.split('|')
  const [bodyKey, bodyVars] = card.body.split('|')
  const vars = (raw?: string): Record<string, string> | undefined =>
    raw ? (Object.fromEntries(new URLSearchParams(raw)) as Record<string, string>) : undefined
  return (
    <CardShell
      title={tx(titleKey, lang, vars(titleVars))}
      accentColor={accent}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={(id) => t(`action.${id}`, lang)}
    >
      {bodyKey ? (
        <p className="m-0 whitespace-pre-line text-[13px] leading-[1.45] text-slate-600 dark:text-[#A8A0B8]">
          {tx(bodyKey, lang, vars(bodyVars))}
        </p>
      ) : null}
    </CardShell>
  )
}
