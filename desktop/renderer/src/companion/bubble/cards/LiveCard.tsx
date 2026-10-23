import type { BubbleCard } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface LiveCardProps {
  card: Extract<BubbleCard, { kind: 'live' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onClose?: () => void
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export default function LiveCard({
  card,
  lang = 'en',
  tail = 'left',
  onClose,
}: LiveCardProps): JSX.Element {
  const isCoverageDegraded = card.coverage === 'incomplete'
  const isSealVerified = card.seal === 'verified'

  return (
    <CardShell
      title={t('live.title', lang)}
      accentColor={color.watch}
      tail={tail}
      onClose={onClose}
    >
      <div className="space-y-2.5">
        <div className="flex items-center justify-between text-[12px] text-slate-500 dark:text-[#A8A0B8]">
          <span>{t('live.active_call', lang)}</span>
          <span className="font-mono">{formatElapsed(card.elapsed_s)}</span>
        </div>

        {/* Status Pills */}
        <div className="flex flex-col gap-1.5 text-[12.5px]">
          {isCoverageDegraded ? (
            <p className="text-amber-600 dark:text-amber-400">
              {t('coverage.degraded', lang)}
            </p>
          ) : (
            <p className="text-slate-600 dark:text-[#A8A0B8]">
              {t('coverage.usable', lang)}
            </p>
          )}

          <p className={isSealVerified ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-[#A8A0B8]'}>
            {isSealVerified ? t('seal.verified', lang) : t('seal.not_verified', lang)}
          </p>
        </div>

        {/* Asks Chips Row */}
        {card.chips.length > 0 && (
          <div className="mt-2 pt-2 border-t border-black/[0.06] dark:border-white/[0.08]">
            <div className="flex flex-wrap gap-1.5">
              {card.chips.map((chip, idx) => (
                <span
                  key={`${chip.code}-${idx}`}
                  className="rounded-full bg-[#1FB5A3]/15 px-2.5 py-1 text-[12px] font-medium text-[#2A2238] dark:text-[#EDE8F5]"
                >
                  {t(`ask.${chip.code}`, lang)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </CardShell>
  )
}
