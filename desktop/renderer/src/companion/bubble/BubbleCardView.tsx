/**
 * BubbleCardView — switches and renders exactly ONE `BubbleCard` (MASCOT_SPEC §7).
 *
 * Anti-slop constraints:
 * - 340 px frame width.
 * - Trilingual voice (EN, Hinglish, हिन्दी).
 * - Indian number formatting (₹48,50,000), masked accounts (••••4821).
 * - No emojis in UI text, no gradients, no raw score numbers.
 */

import type { BubbleCard } from '../../../../shared/contracts'
import type { Lang } from '../../shared/copy'
import AlertCard from './cards/AlertCard'
import CallAskCard from './cards/CallAskCard'
import ConsentCard from './cards/ConsentCard'
import FileAskCard from './cards/FileAskCard'
import LiveCard from './cards/LiveCard'
import LivenessCard from './cards/LivenessCard'
import NoticeCard from './cards/NoticeCard'
import OobResultCard from './cards/OobResultCard'
import OobWaitCard from './cards/OobWaitCard'
import ResultCard from './cards/ResultCard'
import ScreenCard from './cards/ScreenCard'
import ScribeCard from './cards/ScribeCard'
import ToastCard from './cards/ToastCard'

export interface BubbleCardViewProps {
  card: BubbleCard
  tail?: 'left' | 'right' | 'none'
  lang?: Lang
  onAction?: (actionId: string) => void
  onClose?: () => void
}

export default function BubbleCardView({
  card,
  tail = 'left',
  lang = 'en',
  onAction = () => undefined,
  onClose,
}: BubbleCardViewProps): JSX.Element {
  switch (card.kind) {
    case 'toast':
      return <ToastCard card={card} tail={tail} lang={lang} onClose={onClose} />
    case 'consent':
      return <ConsentCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'call_ask':
      return <CallAskCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'file_ask':
      return <FileAskCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'result':
      return <ResultCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'live':
      return <LiveCard card={card} tail={tail} lang={lang} onAction={onAction} />
    case 'alert':
      return <AlertCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'oob_wait':
      return <OobWaitCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'oob_result':
      return <OobResultCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'scribe':
      return <ScribeCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'screen':
      return <ScreenCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'notice':
      return <NoticeCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
    case 'liveness':
      return <LivenessCard card={card} tail={tail} lang={lang} onAction={onAction} onClose={onClose} />
  }
}
