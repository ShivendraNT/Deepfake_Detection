/**
 * One caption line with its highlights: asks are filled in the card's accent colour (they became
 * signals the policy engine weighed), cues are dotted-underlined in grey (context only).
 */

import type { CaptionLine, TranscriptHighlight } from '../../../../shared/contracts'
import { t, type Lang } from '../../shared/copy'

interface Piece {
  text: string
  span: TranscriptHighlight | null
}

/** Split `text` into plain and highlighted pieces. Overlaps keep the first span. */
export function splitCaption(text: string, spans: TranscriptHighlight[]): Piece[] {
  const ordered = [...spans]
    .filter((s) => s.end > s.start && s.start >= 0 && s.end <= text.length)
    .sort((a, b) => a.start - b.start)
  const pieces: Piece[] = []
  let cursor = 0
  for (const span of ordered) {
    if (span.start < cursor) continue
    if (span.start > cursor) pieces.push({ text: text.slice(cursor, span.start), span: null })
    pieces.push({ text: text.slice(span.start, span.end), span })
    cursor = span.end
  }
  if (cursor < text.length) pieces.push({ text: text.slice(cursor), span: null })
  return pieces
}

export default function Caption({
  line,
  accent,
  lang = 'en',
  faded = false,
}: {
  line: CaptionLine
  accent: string
  lang?: Lang
  faded?: boolean
}): JSX.Element {
  return (
    <p className={`m-0 text-[13px] leading-[1.5] ${faded ? 'opacity-55' : ''}`}>
      {splitCaption(line.text, line.spans).map((piece, index) =>
        piece.span === null ? (
          <span key={index}>{piece.text}</span>
        ) : piece.span.kind === 'ask' ? (
          <mark
            key={index}
            title={t(`ask.${piece.span.code}`, lang)}
            className="rounded-[5px] px-[3px] py-[1px] font-semibold text-[#2A2238] dark:text-white"
            style={{ backgroundColor: `${accent}38`, boxShadow: `inset 0 -2px 0 ${accent}` }}
          >
            {piece.text}
          </mark>
        ) : (
          <span
            key={index}
            title={t(`cue.${piece.span.code}`, lang)}
            className="underline decoration-slate-400 decoration-dotted decoration-2 underline-offset-[3px]"
          >
            {piece.text}
          </span>
        ),
      )}
    </p>
  )
}
