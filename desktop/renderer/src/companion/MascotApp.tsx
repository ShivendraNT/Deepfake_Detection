/**
 * MascotApp — the mascot window (`?view=companion`). F07 (Saarika) replaces this shell with
 * the radial menu and drag hooks. Until then it hosts the existing Companion shell so nothing
 * that T25 checks regresses. In browser mock mode, cards from `api.showCard` render inline in a
 * `<div>` instead of a second window.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

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

  const isDown = useRef(false)
  const hasDragged = useRef(false)
  const downPos = useRef({ x: 0, y: 0 })
  const lastScreenPos = useRef({ x: 0, y: 0 })

  useEffect(() => {
    if (!isMockBridge) return
    return api.onCard((next, side) => {
      setCard(next)
      setTail(side)
    })
  }, [])

  const handlePointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return
    isDown.current = true
    hasDragged.current = false
    downPos.current = { x: e.screenX, y: e.screenY }
    lastScreenPos.current = { x: e.screenX, y: e.screenY }
    api.setClickThrough(false)
    try {
      ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
    } catch {}
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDown.current) return
    const totalDist = Math.hypot(e.screenX - downPos.current.x, e.screenY - downPos.current.y)
    if (!hasDragged.current && totalDist > 4) {
      hasDragged.current = true
    }
    if (hasDragged.current) {
      const dx = e.screenX - lastScreenPos.current.x
      const dy = e.screenY - lastScreenPos.current.y
      lastScreenPos.current = { x: e.screenX, y: e.screenY }
      api.dragBy(dx, dy)
    }
  }

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!isDown.current) return
    isDown.current = false
    try {
      ;(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId)
    } catch {}

    if (hasDragged.current) {
      api.dragEnd()
      hasDragged.current = false
    }
  }

  const handleDoubleClick = () => {
    void api.openWorkspace()
  }

  return (
    <div className="relative h-full w-full select-none">
      {companion ?? (
        <div className="grid h-full w-full place-items-center">
          <div
            className="flex h-[176px] w-[176px] cursor-grab items-center justify-center active:cursor-grabbing"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
            onDoubleClick={handleDoubleClick}
            onPointerEnter={() => api.setClickThrough(false)}
            onPointerLeave={() => {
              if (!isDown.current) api.setClickThrough(true)
            }}
          >
            <Mascot mood="attentive" size={176} />
          </div>
        </div>
      )}
      <AnimatePresence mode="wait">
        {isMockBridge && card ? (
          <motion.div
            key={card.id}
            initial={{ opacity: 0, scale: 0.88, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 6 }}
            transition={{ type: 'spring', stiffness: 420, damping: 24, mass: 0.8 }}
            className="absolute bottom-2 right-2 z-20"
          >
            <BubbleCardView
              card={card}
              tail={tail}
              onAction={(actionId) => api.cardAction(card.id, actionId)}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
