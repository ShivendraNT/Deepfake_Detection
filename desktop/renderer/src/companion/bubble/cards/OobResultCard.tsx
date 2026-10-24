import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface OobResultCardProps {
  card: Extract<BubbleCard, { kind: 'oob_result' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function OobResultCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
}: OobResultCardProps): JSX.Element {
  const isApproved = card.outcome === 'approved'
  const accent = isApproved ? color.good : color.hold
  const text = t(`oob.${card.outcome}`, lang, { approver: card.approver_name })
  const title = t(isApproved ? 'oob.title.approved' : 'oob.title.notice', lang)

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
      <p className="text-[13.5px] leading-[1.45] text-slate-700 dark:text-[#EDE8F5]">
        {text}
      </p>
    </CardShell>
  )
}

