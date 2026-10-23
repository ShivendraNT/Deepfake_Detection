/**
 * MascotApp — the mascot window (`?view=companion`).
 *
 * Satya lives in a 280×280 transparent window that is click-through except over him or an open
 * petal. The pure reducer (satyaMachine) owns his state; this shell wires gestures, the radial
 * menu, quips and the living sprite. Pet him by rubbing the pointer over him; drop a file on him
 * to have it checked; click for the menu; double-click for the Notebook.
 */

import { useRef, useState, type DragEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import type { Pose } from '../../../shared/contracts'
import type { SatyaPose } from '../satya/engine'
import SatyaSprite, { type SatyaHandle } from '../satya/SatyaSprite'
import { api, isMockBridge } from '../shared/api'
import BubbleCardView from './bubble/BubbleCardView'
import RadialMenu, { menuEdgeFromWindow, type MenuEdge } from './RadialMenu'
import type { SatyaState } from './satyaMachine'
import { useDrag } from './useDrag'
import { useHitArea } from './useHitArea'
import { useSatya } from './useSatya'

/** Contract pose + context → the richer set of poses the sprite can act out. */
export function spritePose(state: Pick<SatyaState, 'pose' | 'card' | 'lastBand' | 'userMode'>): SatyaPose {
  const pose: Pose = state.pose
  if (state.userMode === 'OFF') return 'off'
  if (pose === 'alert') {
    if (state.card?.kind === 'oob_wait') return 'verify'
    if (state.lastBand === 'HOLD' || (state.card?.kind === 'alert' && state.card.band === 'HOLD')) return 'hold'
    return 'alert'
  }
  return pose
}

export default function MascotApp(): JSX.Element {
  const sprite = useRef<SatyaHandle | null>(null)
  const satya = useSatya({ onEmote: (emote) => sprite.current?.play(emote) })
  const reduced = useReducedMotion() ?? false
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuEdge, setMenuEdge] = useState<MenuEdge>('none')
  const fileInput = useRef<HTMLInputElement | null>(null)
  const rub = useRef({ lastX: 0, dir: 0, flips: 0, at: 0 })

  const drag = useDrag({
    onClick: () => {
      if (menuOpen) {
        setMenuOpen(false)
        return
      }
      sprite.current?.play('boop')
      setMenuEdge(menuEdgeFromWindow())
      setMenuOpen(true)
    },
    onDoubleClick: () => {
      setMenuOpen(false)
      satya.onMenu('notebook')
    },
  })

  const hit = useHitArea(menuOpen || drag.dragging)
  const velocity = drag.velocity.get()

  /** Rubbing back and forth over Satya pets him (hearts, giggles). */
  function handleHoverMove(event: ReactPointerEvent<HTMLElement>): void {
    if (drag.dragging || event.buttons !== 0) return
    const r = rub.current
    const dx = event.clientX - r.lastX
    r.lastX = event.clientX
    if (Math.abs(dx) < 2) return
    const dir = Math.sign(dx)
    const now = performance.now()
    if (now - r.at > 600) r.flips = 0
    if (dir !== r.dir) {
      r.flips += 1
      r.dir = dir
      r.at = now
    }
    if (r.flips >= 3) {
      sprite.current?.pet()
      satya.onPet()
    }
  }

  function handleDragOver(event: DragEvent<HTMLElement>): void {
    event.preventDefault()
    satya.onFileHover(true)
  }

  function handleDragLeave(event: DragEvent<HTMLElement>): void {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
    satya.onFileHover(false)
  }

  function handleDrop(event: DragEvent<HTMLElement>): void {
    event.preventDefault()
    satya.onFileHover(false)
    const file = event.dataTransfer.files?.[0]
    if (file) satya.onFileDrop(file)
  }

  const pose = spritePose(satya.state)

  return (
    <div className="relative h-full w-full select-none overflow-visible bg-transparent">
      <input
        ref={fileInput}
        type="file"
        className="hidden"
        accept=".pdf,.eml,.msg,.mbox,.txt,.md,.csv,.json,.log,.wav,.mp3,.m4a,.ogg,.opus,.webm,image/*"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) satya.onFileDrop(file)
          event.target.value = ''
        }}
      />

      <div className="absolute left-1/2 top-[56%] h-[150px] w-[150px] -translate-x-1/2 -translate-y-1/2">
        <div
          className="grid h-full w-full cursor-grab touch-none place-items-center active:cursor-grabbing"
          role="button"
          tabIndex={0}
          aria-label="Satya. Click for the menu, double-click for the Notebook, or drop a file on him."
          {...drag.handlers}
          onPointerEnter={hit.onPointerEnter}
          onPointerLeave={hit.onPointerLeave}
          onPointerMove={(event) => {
            drag.handlers.onPointerMove(event)
            handleHoverMove(event)
          }}
          onDragEnter={handleDragOver}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              setMenuEdge(menuEdgeFromWindow())
              setMenuOpen((open) => !open)
            }
          }}
        >
          <SatyaSprite
            ref={sprite}
            pose={pose}
            size={128}
            level={satya.level}
            look={satya.look}
            talking={Boolean(satya.quip) && !satya.state.callId}
            dragging={drag.dragging}
            dragVelocity={velocity}
            reducedMotion={reduced}
          />
        </div>
      </div>

      <RadialMenu
        open={menuOpen}
        edge={menuEdge}
        userMode={satya.state.userMode}
        inCall={Boolean(satya.state.callId)}
        onAction={(action) => {
          if (action === 'check') {
            fileInput.current?.click()
            return
          }
          satya.onMenu(action)
        }}
        onClose={() => setMenuOpen(false)}
        onPointerEnter={hit.onPointerEnter}
        onPointerLeave={hit.onPointerLeave}
      />

      <AnimatePresence>
        {satya.quip && !menuOpen ? (
          <motion.div
            key={satya.quip.id}
            initial={{ opacity: 0, y: 8, scale: 0.8 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 520, damping: 26 }}
            className="pointer-events-none absolute left-1/2 top-2 z-40 max-w-[250px] -translate-x-1/2"
          >
            <div className="relative rounded-2xl border border-black/10 bg-white px-3 py-1.5 text-center text-[12.5px] font-semibold leading-snug text-[#1B2F38] shadow-[0_6px_18px_rgba(10,30,45,0.25)]">
              {satya.quip.text}
              <span className="absolute -bottom-[6px] left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-black/10 bg-white" />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {isMockBridge && satya.state.card ? (
          <motion.div
            key={satya.state.card.id}
            initial={{ opacity: 0, scale: 0.88, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 6 }}
            transition={{ type: 'spring', stiffness: 420, damping: 24, mass: 0.8 }}
            className="absolute bottom-1 right-1 z-20 w-[280px]"
          >
            <BubbleCardView
              card={satya.state.card}
              tail="right"
              lang={satya.lang}
              onAction={(actionId) => api.cardAction(satya.state.card!.id, actionId)}
              onClose={() => api.cardAction(satya.state.card!.id, 'dismiss')}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
