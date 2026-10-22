/** The bubble window (`?view=bubble`): exactly one card, placed beside Satya by main. */

import { useEffect, useRef, useState } from 'react'

import type { BubbleCard } from '../../../../shared/contracts'
import { api } from '../../shared/api'
import { SCENARIO_LIST } from '../../shared/mockScenario'
import BubbleCardView from './BubbleCardView'

const CARD_KINDS = new Set([
  'consent',
  'call_ask',
  'file_ask',
  'live',
  'result',
  'alert',
  'oob_wait',
  'oob_result',
  'scribe',
  'toast',
])

/** QA helper from MASCOT_SPEC §9: `?view=bubble&card=alert` renders that card offline. */
function cardFromQuery(): BubbleCard | null {
  const kind = new URLSearchParams(window.location.search).get('card')
  if (!kind || !CARD_KINDS.has(kind)) return null
  for (const scenario of SCENARIO_LIST) {
    for (const step of scenario.steps) {
      if (step.card && step.card.kind === kind) return step.card
    }
  }
  return null
}

export default function BubbleApp(): JSX.Element {
  const [card, setCard] = useState<BubbleCard | null>(() => cardFromQuery())
  const [tail, setTail] = useState<'left' | 'right'>('left')
  const hostRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const off = api.onCard((next, side) => {
      setCard(next)
      setTail(side)
    })
    return off
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') api.hideBubble()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const node = hostRef.current
    if (!node) return
    const observer = new ResizeObserver((entries) => {
      const height = Math.ceil(entries[0]?.contentRect.height ?? 0)
      if (height > 0) api.resizeBubble(height)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [card])

  return (
    <div className="flex min-h-screen w-full items-start justify-center p-1.5">
      <div ref={hostRef}>
        {card ? (
          <BubbleCardView
            card={card}
            tail={tail}
            onAction={(actionId) => api.cardAction(card.id, actionId)}
          />
        ) : null}
      </div>
    </div>
  )
}
