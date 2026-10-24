import type { BubbleCard } from '../../../../../shared/contracts'
import { t, translateSectionTitle, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface ScribeCardProps {
  card: Extract<BubbleCard, { kind: 'scribe' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function ScribeCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
}: ScribeCardProps): JSX.Element {
  const allDone = card.sections.length > 0 && card.sections.every((s) => s.status === 'done')
  const title = allDone ? t('scribe.done', lang) : t('scribe.writing', lang)
  const bodyText = allDone ? t('scribe.body.done', lang) : t('scribe.body.writing', lang)

  function resolveLabel(actionId: string): string {
    return t(`action.${actionId}`, lang)
  }

  function resolveStatusLabel(status: 'pending' | 'writing' | 'done'): string {
    if (status === 'done') return t('scribe.status.ready', lang)
    if (status === 'writing') return t('scribe.status.writing', lang)
    return t('scribe.status.pending', lang)
  }

  return (
    <CardShell
      title={title}
      accentColor={color.write}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={resolveLabel}
    >
      <div className="space-y-2">
        <p className="text-[13px] text-slate-600 dark:text-[#A8A0B8]">
          {bodyText}
        </p>

        {card.sections.length > 0 && (
          <ul className="space-y-1.5 pt-1">
            {card.sections.map((section) => (
              <li
                key={section.id}
                className="flex items-center justify-between text-[12px] text-[#2A2238] dark:text-[#EDE8F5]"
              >
                <span>{translateSectionTitle(section.title, lang)}</span>
                <span className="font-mono text-[11px] text-slate-400 dark:text-white/40">
                  {resolveStatusLabel(section.status)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </CardShell>
  )
}

