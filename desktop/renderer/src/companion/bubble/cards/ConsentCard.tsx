import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface ConsentCardProps {
  card: Extract<BubbleCard, { kind: 'consent' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function ConsentCard({
  card,
  lang = 'en',
  tail = 'left',
  onAction,
  onClose,
}: ConsentCardProps): JSX.Element {
  const scopeKeys: Record<string, string> = {
    'Notice calls (no recording)': 'consent.scope.notice',
    'Listen to a call when you say yes': 'consent.scope.listen',
    'Check files you give me': 'consent.scope.files',
  }

  function resolveScope(scope: string): string {
    const key = scopeKeys[scope]
    return key ? t(key, lang) : scope
  }

  function resolveLabel(actionId: string): string {
    const key = `action.${actionId}`
    return t(key, lang)
  }

  return (
    <CardShell
      title={t('consent.title', lang)}
      accentColor={color.watch}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={resolveLabel}
    >
      <p className="text-[13.5px] leading-[1.45] text-slate-600 dark:text-[#A8A0B8]">
        {t('consent.body', lang)}
      </p>

      {card.scopes.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {card.scopes.map((scope) => (
            <li
              key={scope}
              className="flex items-center gap-2 text-[12.5px] text-[#2A2238] dark:text-[#EDE8F5]"
            >
              <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-[#1FB5A3]/15 text-[#1FB5A3]">
                <svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3.5 8.5 L6.5 11.5 L12.5 4.5" />
                </svg>
              </span>
              <span>{resolveScope(scope)}</span>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  )
}

