import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface OobWaitCardProps {
  card: Extract<BubbleCard, { kind: 'oob_wait' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function OobWaitCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
}: OobWaitCardProps): JSX.Element {
  const title = t('oob.wait', lang, { approver: card.approver_name })

  function resolveLabel(actionId: string): string {
    return t(`action.${actionId}`, lang)
  }

  return (
    <CardShell
      title={title}
      accentColor={color.verify}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={resolveLabel}
    >
      <div className="flex items-center gap-2 text-[12.5px] text-slate-500 dark:text-[#A8A0B8]">
        <span
          className="inline-block h-2 w-2 animate-pulse rounded-full"
          style={{ backgroundColor: color.verify }}
        />
        <span>{t('oob.wait.badge', lang)}</span>
      </div>
    </CardShell>
  )
}

