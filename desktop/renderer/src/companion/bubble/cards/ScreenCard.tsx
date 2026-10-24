/** Screen Guard / clipboard finding: what was noticed, in the exact words, and one next step. */

import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface ScreenCardProps {
  card: Extract<BubbleCard, { kind: 'screen' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function ScreenCard({ card, lang = 'en', tail = 'left', onAction, onClose }: ScreenCardProps): JSX.Element {
  const f = card.finding
  const accent = f.suspicious ? color.verify : color.good
  const title = !f.suspicious
    ? t('screen.clear', lang)
    : card.source === 'clipboard'
      ? t('screen.title.clipboard', lang)
      : t('screen.title', lang)
  const unknown = f.vendors.length > 0 && f.unknown_accounts_masked.length > 0

  return (
    <CardShell
      title={title}
      accentColor={accent}
      tail={tail}
      actions={card.actions}
      onAction={onAction}
      onClose={onClose}
      resolveActionLabel={(id) => t(`action.${id}`, lang)}
      badge={
        f.app ? (
          <span className="rounded-full bg-black/[0.05] px-2 py-0.5 text-[11px] text-slate-600 dark:bg-white/[0.08] dark:text-[#A8A0B8]">
            {f.app}
          </span>
        ) : null
      }
    >
      {unknown ? (
        <p
          className="m-0 rounded-lg px-2.5 py-1.5 text-[13px] font-medium text-[#2A2238] dark:text-[#EDE8F5]"
          style={{ backgroundColor: `${color.hold}18`, borderLeft: `3px solid ${color.hold}` }}
        >
          {t('screen.unknown_account', lang, {
            vendor: f.vendors[0],
            accounts: f.unknown_accounts_masked.join(', '),
          })}
        </p>
      ) : null}
      {f.asks.length > 0 ? (
        <div className="mt-2 space-y-1.5">
          <p className="m-0 text-[12px] font-semibold text-slate-500 dark:text-[#A8A0B8]">{t('screen.asks', lang)}</p>
          {f.asks.slice(0, 3).map((quote) => (
            <div
              key={quote.code}
              className="flex items-start gap-2 rounded-lg px-2.5 py-1.5"
              style={{ backgroundColor: `${accent}14`, borderLeft: `3px solid ${accent}` }}
            >
              <span className="min-w-0 flex-1 text-[13px] italic leading-snug">“{quote.text}”</span>
              <span className="mt-0.5 flex-shrink-0 whitespace-nowrap rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-semibold dark:bg-black/30">
                {t(`ask.${quote.code}`, lang)}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {f.suspicious ? (
        <p className="mb-0 mt-2 text-[11.5px] text-slate-500 dark:text-[#A8A0B8]">{t('screen.note', lang)}</p>
      ) : null}
    </CardShell>
  )
}
