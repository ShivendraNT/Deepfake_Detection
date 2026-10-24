import type { BubbleCard } from '../../../../../shared/contracts'
import { translateToast, type Lang } from '../../../shared/copy'
import { color } from '../../../shared/tokens'
import CardShell from '../CardShell'

export interface ToastCardProps {
  card: Extract<BubbleCard, { kind: 'toast' }>
  lang?: Lang
  tail?: 'left' | 'right' | 'none'
  onClose?: () => void
}

export default function ToastCard({
  card,
  lang = 'en',
  tail = 'left',
  onClose,
}: ToastCardProps): JSX.Element {
  const accent =
    card.tone === 'good'
      ? color.good
      : card.tone === 'warn'
      ? color.verify
      : color.sleep

  const message = translateToast(card.text_key, lang)

  return (
    <CardShell
      title={message}
      accentColor={accent}
      tail={tail}
      onClose={onClose}
    />
  )
}

