/**
 * "Can I keep watch?" — consent with switchable scopes. Each scope is shown in plain words and
 * can be turned off before starting. What Satya never does is said up front.
 */

import { useState } from 'react'

import { DEFAULT_SCOPES, type BubbleCard, type Scopes } from '../../../../../shared/contracts'
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

const SCOPE_ROWS: Array<{ key: keyof Scopes; label: string }> = [
  { key: 'meetings', label: 'consent.scope.meetings' },
  { key: 'listen', label: 'consent.scope.listen_yes' },
  { key: 'screen', label: 'consent.scope.screen' },
  { key: 'files', label: 'consent.scope.files_v2' },
  { key: 'video', label: 'consent.scope.video' },
]

/** "start_watching:11011" — the scope switches in SCOPE_ROWS order. */
export function encodeScopes(scopes: Scopes): string {
  return SCOPE_ROWS.map((row) => (scopes[row.key] ? '1' : '0')).join('')
}

export function decodeScopes(bits: string | undefined): Scopes {
  // Four bits = a card from before the video scope existed: video keeps its default.
  if (!bits || !/^[01]{4,5}$/.test(bits)) return { ...DEFAULT_SCOPES }
  const out = { ...DEFAULT_SCOPES }
  SCOPE_ROWS.forEach((row, index) => {
    if (index < bits.length) out[row.key] = bits[index] === '1'
  })
  return out
}

export default function ConsentCard({ card, lang = 'en', tail = 'left', onAction, onClose }: ConsentCardProps): JSX.Element {
  const [scopes, setScopes] = useState<Scopes>({ ...DEFAULT_SCOPES })

  return (
    <CardShell
      title={t('consent.title', lang)}
      accentColor={color.watch}
      tail={tail}
      actions={card.actions}
      onAction={(id) => onAction?.(id === 'start_watching' ? `start_watching:${encodeScopes(scopes)}` : id)}
      onClose={onClose}
      resolveActionLabel={(id) => t(`action.${id}`, lang)}
    >
      <p className="m-0 text-[13.5px] leading-[1.45] text-slate-600 dark:text-[#A8A0B8]">{t('consent.body.v2', lang)}</p>
      <ul className="mb-0 mt-3 flex flex-col gap-1.5 pl-0">
        {SCOPE_ROWS.map((row) => {
          const on = scopes[row.key]
          return (
            <li key={row.key} className="list-none">
              <button
                type="button"
                role="switch"
                aria-checked={on}
                onClick={() => setScopes((current) => ({ ...current, [row.key]: !current[row.key] }))}
                className="flex w-full items-center gap-2.5 rounded-lg px-1.5 py-1 text-left text-[12.5px] text-[#2A2238] hover:bg-black/[0.04] dark:text-[#EDE8F5] dark:hover:bg-white/[0.05]"
              >
                <span
                  className="relative inline-flex h-[18px] w-[30px] flex-shrink-0 rounded-full transition-colors"
                  style={{ backgroundColor: on ? color.watch : 'rgba(120,120,140,0.35)' }}
                >
                  <span
                    className="absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white shadow transition-all"
                    style={{ left: on ? 14 : 2 }}
                  />
                </span>
                <span className={on ? '' : 'opacity-50'}>{t(row.label, lang)}</span>
              </button>
            </li>
          )
        })}
      </ul>
      <p className="mb-0 mt-2 text-[12px] text-slate-500 dark:text-[#A8A0B8]">{t('consent.never', lang)}</p>
    </CardShell>
  )
}
