/**
 * MascotApp — the mascot window (`?view=companion`). F07 (Saarika) replaces this shell with
 * the radial menu and drag hooks. Until then it hosts the existing Companion shell so nothing
 * that T25 checks regresses. In browser mock mode, cards from `api.showCard` render inline in a
 * `<div>` instead of a second window.
 */

import { useEffect, useState, type ReactNode } from 'react'

import type { BubbleCard } from '../../../shared/contracts'
import { api, isMockBridge } from '../shared/api'
import Mascot from './Mascot'
import BubbleCardView from './bubble/BubbleCardView'

export interface MascotAppProps {
  companion?: ReactNode
}

export default function MascotApp({ companion }: MascotAppProps): JSX.Element {
  const [card, setCard] = useState<BubbleCard | null>(null)
  const [tail, setTail] = useState<'left' | 'right'>('left')

  useEffect(() => {
    if (!isMockBridge) return
    return api.onCard((next, side) => {
      setCard(next)
      setTail(side)
    })
  }, [])

  return (
    <div className="relative h-full w-full">
      {companion ?? (
        <div className="grid h-full w-full place-items-center">
          <Mascot mood="attentive" size={176} />
        </div>
      )}
      {isMockBridge && card ? (
        <div className="absolute bottom-2 right-2 z-20">
          <BubbleCardView
            card={card}
            tail={tail}
            onAction={(actionId) => api.cardAction(card.id, actionId)}
          />
        </div>
      ) : null}
    </div>
  )
}
