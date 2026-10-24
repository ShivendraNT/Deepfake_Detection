/**
 * The live call card: what the other person just said (captions with highlights), the ask chips,
 * grey context cues, and the policy band relayed in plain words. Passive: it never steals focus
 * from the call window.
 */

import { useEffect, useState } from 'react'

import type { Band, BubbleCard, CueCode } from '../../../../../shared/contracts'
import { t, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import Caption from '../Caption'
import CardShell from '../CardShell'

export interface LiveCardProps {
  card: Extract<BubbleCard, { kind: 'live' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onAction?: (actionId: string) => void
  onClose?: () => void
}

const BAND_ACCENT: Record<Band, string> = {
  PASS: color.watch,
  VERIFY: color.verify,
  HOLD: color.hold,
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function useElapsed(startedAt: string | null | undefined, fallback: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  if (!startedAt) return fallback
  const started = Date.parse(startedAt)
  return Number.isFinite(started) ? Math.max(0, (now - started) / 1000) : fallback
}

export default function LiveCard({ card, lang = 'en', tail = 'left', onAction, onClose }: LiveCardProps): JSX.Element {
  const band = card.band ?? 'PASS'
  const accent = BAND_ACCENT[band]
  const lines = (card.lines ?? []).slice(-3)
  const elapsed = useElapsed(card.started_at, card.elapsed_s)
  const cues = Array.from(
    new Set(lines.flatMap((line) => line.spans.filter((s) => s.kind === 'cue').map((s) => s.code))),
  ) as CueCode[]

  return (
    <CardShell
      title={card.status ? t('notice.asr_missing.title', lang) : t('live.title', lang)}
      accentColor={card.status ? color.verify : accent}
      tail={tail}
      onClose={onClose}
      actions={[
        { id: 'stop_listening', variant: 'outline' },
        { id: 'open_notebook', variant: 'outline' },
      ]}
      actionsLayout="row"
      onAction={onAction}
      resolveActionLabel={(id) => t(`action.${id}`, lang)}
      badge={
        <span className="flex items-center gap-1.5 rounded-full bg-black/[0.05] px-2 py-0.5 font-mono text-[11.5px] text-slate-600 dark:bg-white/[0.08] dark:text-[#A8A0B8]">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ backgroundColor: accent }} />
            <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: accent }} />
          </span>
          {formatElapsed(elapsed)}
        </span>
      }
    >
      {card.demo ? (
        <p className="mb-2 rounded-md bg-amber-500/15 px-2 py-1 text-center text-[11px] font-semibold tracking-wide text-amber-700 dark:text-amber-300">
          {t('live.demo', lang)}
        </p>
      ) : null}

      {card.status ? (
        <p className="m-0 text-[12.5px] text-slate-600 dark:text-[#A8A0B8]">{t('notice.asr_missing.body', lang)}</p>
      ) : (
        <div
          className="rounded-xl px-3 py-2 text-[#2A2238] dark:text-[#EDE8F5]"
          style={{ backgroundColor: `${accent}12`, border: `1px solid ${accent}30` }}
        >
          <p className="mb-1 text-[12px] font-semibold" style={{ color: accent }}>
            {t(`live.band.${band}`, lang)}
          </p>
          {lines.length === 0 ? (
            <p className="m-0 text-[12.5px] italic text-slate-500 dark:text-[#A8A0B8]">{t('live.waiting', lang)}</p>
          ) : (
            <div className="space-y-1">
              {lines.map((line, index) => (
                <Caption key={line.id} line={line} accent={accent} lang={lang} faded={index < lines.length - 1} />
              ))}
            </div>
          )}
          {card.transcribing ? (
            <span className="mt-1 inline-flex gap-1" aria-label="writing that down">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
                  style={{ animationDelay: `${i * 0.12}s` }}
                />
              ))}
            </span>
          ) : null}
        </div>
      )}

      {card.chips.length > 0 || cues.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {card.chips.map((chip) => (
            <span
              key={chip.code}
              className="rounded-full px-2.5 py-1 text-[12px] font-semibold text-[#2A2238] dark:text-white"
              style={{ backgroundColor: `${accent}26` }}
            >
              {t(`ask.${chip.code}`, lang)}
            </span>
          ))}
          {cues.map((cue) => (
            <span
              key={cue}
              className="rounded-full border border-dashed border-slate-400/70 px-2.5 py-1 text-[12px] text-slate-600 dark:text-[#A8A0B8]"
            >
              {t(`cue.${cue}`, lang)}
            </span>
          ))}
        </div>
      ) : null}

      <p className="mb-0 mt-2 text-[11.5px] text-slate-500 dark:text-[#A8A0B8]">
        {card.coverage === 'degraded' || card.coverage === 'incomplete' ? t('coverage.degraded', lang) : t('live.note', lang)}
      </p>
    </CardShell>
  )
}
