import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface CallAskCardProps {
  card: Extract<BubbleCard, { kind: 'call_ask' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function CallAskCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
}: CallAskCardProps): JSX.Element {
  function resolveLabel(actionId: string): string {
    return t(`action.${actionId}`, lang)
  }

  return (
    <CardShell
      title={t('call.title', lang)}
      accentColor={color.watch}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={resolveLabel}
    >
      <p className="text-[13.5px] leading-[1.45] text-slate-600 dark:text-[#A8A0B8]">
        {t('call.body', lang)}
      </p>
    </CardShell>
  )
}

