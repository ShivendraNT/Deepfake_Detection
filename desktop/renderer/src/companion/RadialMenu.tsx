/**
 * RadialMenu — five petals around Satya (MASCOT_SPEC §5).
 *
 * Presentational only: no API calls and no reducer. Near a screen edge the fan becomes a 180°
 * arc facing inward so the petals stay on screen and the bubble has room.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { BookOpen, Eye, FileSearch, FileText, Headphones, LogOut, Moon, PhoneOff, Power, ScanSearch } from 'lucide-react'

import type { UserMode } from '../../../shared/contracts'
import { api } from '../shared/api'

export type MenuEdge = 'none' | 'left' | 'right' | 'top' | 'bottom'
export type MenuAction =
  | 'watch'
  | 'sleep'
  | 'check'
  | 'notebook'
  | 'off'
  | 'guard'
  | 'quit'
  | 'listen'
  | 'stop_listening'
  | 'scan'
  | 'report'

export interface RadialMenuProps {
  open: boolean
  edge?: MenuEdge
  userMode?: UserMode
  /** A call is being listened to: the listen petal becomes "Stop listening". */
  inCall?: boolean
  onAction: (action: MenuAction) => void
  onClose: () => void
  onPointerEnter?: () => void
  onPointerLeave?: () => void
}

const RADIUS = 78
const CENTRE = 140
const EDGE_MARGIN = 96

const FULL_ANGLES = [-90, -30, 30, 90, 150, 210]

export function anglesForEdge(edge: MenuEdge, count = 6): number[] {
  if (count <= 1) return [-90]
  switch (edge) {
    case 'left': {
      const step = 180 / (count - 1)
      return Array.from({ length: count }, (_, i) => -90 + i * step)
    }
    case 'right': {
      const step = 180 / (count - 1)
      return Array.from({ length: count }, (_, i) => 90 + i * step)
    }
    case 'top': {
      const step = 180 / (count - 1)
      return Array.from({ length: count }, (_, i) => 0 + i * step)
    }
    case 'bottom': {
      const step = 180 / (count - 1)
      return Array.from({ length: count }, (_, i) => 180 + i * step)
    }
    default: {
      const step = 360 / count
      return Array.from({ length: count }, (_, i) => -90 + i * step)
    }
  }
}

export function menuEdgeFromWindow(): MenuEdge {
  if (typeof window === 'undefined') return 'none'
  const screen = window.screen as Screen & { availLeft?: number; availTop?: number }
  const availLeft = screen.availLeft ?? 0
  const availTop = screen.availTop ?? 0
  const left = window.screenX - availLeft
  const top = window.screenY - availTop
  const right = availLeft + screen.availWidth - (window.screenX + window.outerWidth)
  const bottom = availTop + screen.availHeight - (window.screenY + window.outerHeight)
  const distances: Array<[MenuEdge, number]> = [
    ['left', left],
    ['right', right],
    ['top', top],
    ['bottom', bottom],
  ]
  const nearest = distances.reduce((best, item) => (item[1] < best[1] ? item : best), distances[0])
  return nearest[1] < EDGE_MARGIN ? nearest[0] : 'none'
}

interface PetalItem {
  action: MenuAction
  label: string
  Icon: typeof Eye
}

function point(angle: number): { x: number; y: number } {
  const radians = (angle * Math.PI) / 180
  return { x: CENTRE + RADIUS * Math.cos(radians), y: CENTRE + RADIUS * Math.sin(radians) }
}

export default function RadialMenu({
  open,
  edge = 'none',
  userMode,
  inCall = false,
  onAction,
  onClose,
  onPointerEnter,
  onPointerLeave,
}: RadialMenuProps): JSX.Element {
  const reduced = useReducedMotion()
  const menuRef = useRef<HTMLDivElement | null>(null)
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [watching, setWatching] = useState(false)

  useEffect(() => {
    let cancelled = false
    const off = api.onEvent((event) => {
      const mode = event.payload.user_mode
      if (mode) setWatching(mode === 'WATCHING')
      else if (event.type === 'session.started') setWatching(true)
      else if (event.type === 'session.stopped') setWatching(false)
    })
    void api
      .getState()
      .then((result) => {
        if (!cancelled && result.ok) setWatching(result.data.mode === 'ACTIVE')
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      off()
    }
  }, [])

  const effectiveMode: UserMode = userMode ?? (watching ? 'WATCHING' : 'SLEEPING')

  const petals: PetalItem[] = useMemo(() => {
    if (effectiveMode === 'OFF') {
      return [
        { action: 'watch', label: 'Turn on', Icon: Power },
        { action: 'notebook', label: 'Notebook', Icon: BookOpen },
        { action: 'quit', label: 'Quit Satya', Icon: LogOut },
      ]
    }

    if (effectiveMode === 'WATCHING') {
      return [
        inCall
          ? { action: 'stop_listening', label: 'Stop listening', Icon: PhoneOff }
          : { action: 'listen', label: 'Listen to a call', Icon: Headphones },
        { action: 'check', label: 'Check a file', Icon: FileSearch },
        { action: 'scan', label: 'Scan my screen', Icon: ScanSearch },
        { action: 'report', label: 'Money left? Report', Icon: FileText },
        { action: 'notebook', label: 'Notebook', Icon: BookOpen },
        { action: 'sleep', label: 'Sleep', Icon: Moon },
      ]
    }

    // Sleeping: keep it simple.
    return [
      { action: 'watch', label: 'Wake up', Icon: Eye },
      { action: 'notebook', label: 'Notebook', Icon: BookOpen },
      { action: 'off', label: 'Turn off', Icon: Power },
    ]
  }, [effectiveMode, inCall])

  const angles = useMemo(() => anglesForEdge(edge, petals.length), [edge, petals.length])
  const tooltip = useMemo(() => {
    if (hovered === null) return null
    const { x, y } = point(angles[hovered])
    return {
      label: petals[hovered].label,
      left: Math.min(236, Math.max(44, CENTRE + (x - CENTRE) * 1.34)),
      top: Math.min(248, Math.max(32, CENTRE + (y - CENTRE) * 1.34)),
    }
  }, [angles, hovered, petals])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    const onOutsidePointerDown = (event: PointerEvent): void => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) onClose()
    }
    document.addEventListener('pointerdown', onOutsidePointerDown)
    return () => document.removeEventListener('pointerdown', onOutsidePointerDown)
  }, [open, onClose])

  useEffect(() => {
    if (open) return
    setHovered(null)
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = null
  }, [open])

  useEffect(
    () => () => {
      if (hoverTimer.current) clearTimeout(hoverTimer.current)
    },
    [],
  )

  function enter(index: number): void {
    onPointerEnter?.()
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = setTimeout(() => setHovered(index), 400)
  }

  function leave(): void {
    onPointerLeave?.()
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = null
    setHovered(null)
  }

  return (
    <div ref={menuRef} className="pointer-events-none absolute inset-0 z-30" aria-hidden={!open}>
      <AnimatePresence>
        {open
          ? petals.map((petal, index) => {
              const { x, y } = point(angles[index])
              return (
                <motion.div
                  key={petal.action}
                  className="absolute"
                  style={{ left: x, top: y, translate: '-50% -50%' }}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  transition={
                    reduced
                      ? { duration: 0 }
                      : {
                          type: 'spring',
                          stiffness: 420,
                          damping: 24,
                          delay: index * 0.035,
                        }
                  }
                >
                  <button
                    type="button"
                    aria-label={petal.label}
                    title={petal.label}
                    onPointerEnter={() => enter(index)}
                    onPointerLeave={leave}
                    onClick={() => {
                      leave()
                      onClose()
                      if (petal.action === 'sleep' || petal.action === 'off') setWatching(false)
                      if (petal.action === 'watch') setWatching(true)
                      onAction(petal.action)
                    }}
                    className="pointer-events-auto grid h-10 w-10 place-items-center rounded-full border border-white/70 bg-[rgba(255,252,247,0.97)] text-[#2A2238] shadow-[0_8px_20px_rgba(20,16,40,0.24)] outline-none focus-visible:ring-2 focus-visible:ring-[#1FB5A3]"
                  >
                    <petal.Icon size={18} strokeWidth={1.8} aria-hidden />
                  </button>
                </motion.div>
              )
            })
          : null}
      </AnimatePresence>

      <AnimatePresence>
        {tooltip ? (
          <motion.span
            key={tooltip.label}
            initial={{ opacity: 0, y: 2 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.12 }}
            className="pointer-events-none absolute z-40 whitespace-nowrap rounded-md bg-[rgba(28,24,40,0.94)] px-2 py-1 text-[12px] font-medium text-[#EDE8F5]"
            style={{ left: tooltip.left, top: tooltip.top, translate: '-50% -50%' }}
          >
            {tooltip.label}
          </motion.span>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
