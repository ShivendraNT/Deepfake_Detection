/**
 * MascotApp — the mascot window (`?view=companion`).
 *
 * Satya is drawn at 96 px in a 280×280 transparent window. The window is click-through except
 * while the pointer is over Satya or an open petal. One pure reducer owns his mood; this shell
 * only wires gestures, the menu and the bridge.
 */

import { useRef, useState, type DragEvent, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import type { MascotMood, Pose } from '../../../shared/contracts'
import { api, isMockBridge } from '../shared/api'
import Mascot from './Mascot'
import BubbleCardView from './bubble/BubbleCardView'
import RadialMenu, { menuEdgeFromWindow, type MenuAction, type MenuEdge } from './RadialMenu'
import { useDrag } from './useDrag'
import { useHitArea } from './useHitArea'
import { useSatya } from './useSatya'

export interface MascotAppProps {
  companion?: ReactNode
}

const MOOD: Record<Pose, MascotMood> = {
  sleep: 'sleepy',
  idle: 'attentive',
  listen: 'attentive',
  think: 'focused',
  alert: 'calm_alert',
  relief: 'attentive',
  write: 'writing',
  catch: 'attentive',
  wave: 'attentive',
  off: 'off',
}

interface CompatMascotProps {
  pose: Pose
  mood: MascotMood
  audioLevel: number
  look: { dx: number; dy: number; near: boolean }
  size: number
  reducedMotion?: boolean
}

// F06 owns Mascot.tsx. The cast lets this shell pass the finale props while the older F06 preview
// component still reads `mood`; a landed F06 simply ignores the extra prop.
const SatyaFigure = Mascot as unknown as (props: CompatMascotProps) => JSX.Element

export default function MascotApp({ companion }: MascotAppProps): JSX.Element {
  const satya = useSatya()
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuEdge, setMenuEdge] = useState<MenuEdge>('none')
  const fileInput = useRef<HTMLInputElement | null>(null)

  const drag = useDrag({
    onClick: () => {
      if (menuOpen) {
        setMenuOpen(false)
        return
      }
      setMenuEdge(menuEdgeFromWindow())
      setMenuOpen(true)
    },
    onDoubleClick: () => {
      setMenuOpen(false)
      void api.openWorkspace('now')
    },
  })

  const hit = useHitArea(menuOpen || drag.dragging)

  function handleMenu(action: MenuAction): void {
    if (action === 'check') {
      fileInput.current?.click()
      return
    }
    satya.onMenu(action)
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

  return (
    <div className="relative h-full w-full select-none overflow-visible bg-transparent">
      <input
        ref={fileInput}
        type="file"
        className="hidden"
        accept=".eml,.msg,.pdf,.txt,.md,.csv,.wav,.m4a,.mp3,.ogg,.opus,.aac,.flac,image/*"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) satya.onFileDrop(file)
          event.target.value = ''
        }}
      />

      {companion ?? (
        <div className="absolute left-1/2 top-1/2 h-[132px] w-[132px] -translate-x-1/2 -translate-y-1/2">
          <div
            className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
            role="button"
            tabIndex={0}
            aria-label="Satya. Click for the menu, double-click for the Notebook, or drop a file."
            {...drag.handlers}
            onPointerEnter={hit.onPointerEnter}
            onPointerLeave={hit.onPointerLeave}
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
            <motion.div
              className="grid h-full w-full place-items-center drop-shadow-[0_4px_10px_rgba(20,16,40,0.25)]"
              style={{ rotate: drag.tilt }}
              animate={{ scaleY: drag.dragging ? 0.96 : drag.pressed ? 0.94 : 1 }}
              transition={{ type: 'spring', stiffness: 420, damping: 24 }}
            >
              <SatyaFigure
                pose={satya.state.pose}
                mood={MOOD[satya.state.pose]}
                audioLevel={0}
                look={satya.look}
                size={128}
              />
            </motion.div>
          </div>
        </div>
      )}

      <RadialMenu
        open={menuOpen}
        edge={menuEdge}
        onAction={handleMenu}
        onClose={() => setMenuOpen(false)}
        onPointerEnter={hit.onPointerEnter}
        onPointerLeave={hit.onPointerLeave}
      />

      <AnimatePresence>
        {satya.notice ? (
          <motion.div
            key="notice"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute left-1/2 top-1.5 z-40 w-[260px] -translate-x-1/2 rounded-[10px] bg-[rgba(28,24,40,0.94)] px-3 py-2 text-center text-[12px] leading-snug text-[#EDE8F5]"
          >
            {satya.notice}
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
              onAction={(actionId) => api.cardAction(satya.state.card!.id, actionId)}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
