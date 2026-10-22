/**
 * useDrag — pointer physics for Satya (MASCOT_SPEC §5).
 *
 * - 4 px threshold: below it the gesture is a click, not a drag.
 * - One requestAnimationFrame flush per frame, sending `dragBy(dx, dy)` to main.
 * - Tilt = clamp(vx × 0.4, −8°, 8°), then a spring back on release.
 * - Click (<4 px and <250 ms) opens the menu; a second click within 300 ms opens the Notebook.
 */

import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { animate, useMotionValue, type MotionValue } from 'framer-motion'

import { api } from '../shared/api'

const THRESHOLD_PX = 4
const CLICK_MS = 250
const DOUBLE_CLICK_MS = 300
const CLICK_DELAY_MS = 240

export interface DragOptions {
  onClick: () => void
  onDoubleClick: () => void
  disabled?: boolean
}

export interface DragHandlers {
  onPointerDown: (event: ReactPointerEvent<HTMLElement>) => void
  onPointerMove: (event: ReactPointerEvent<HTMLElement>) => void
  onPointerUp: (event: ReactPointerEvent<HTMLElement>) => void
  onPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void
}

export interface DragController {
  handlers: DragHandlers
  tilt: MotionValue<number>
  dragging: boolean
  pressed: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function useDrag({ onClick, onDoubleClick, disabled = false }: DragOptions): DragController {
  const tilt = useMotionValue(0)
  const [dragging, setDragging] = useState(false)
  const [pressed, setPressed] = useState(false)

  const down = useRef(false)
  const draggingRef = useRef(false)
  const downAt = useRef(0)
  const downPoint = useRef({ x: 0, y: 0 })
  const lastPoint = useRef({ x: 0, y: 0 })
  const lastTime = useRef(0)
  const pending = useRef<{ x: number; y: number } | null>(null)
  const frame = useRef<number | null>(null)
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastClickAt = useRef(0)
  const handlersRef = useRef({ onClick, onDoubleClick })
  handlersRef.current = { onClick, onDoubleClick }
  const disabledRef = useRef(disabled)
  disabledRef.current = disabled

  const flush = useCallback(() => {
    frame.current = null
    if (!pending.current) return
    const now = performance.now()
    const point = pending.current
    pending.current = null
    const dx = point.x - lastPoint.current.x
    const dy = point.y - lastPoint.current.y
    const dt = Math.max(8, now - lastTime.current)
    lastPoint.current = point
    lastTime.current = now
    if (dx === 0 && dy === 0) return
    api.dragBy(dx, dy)
    const velocityPerFrame = (dx / dt) * 16.67
    tilt.set(clamp(velocityPerFrame * 0.4, -8, 8))
  }, [tilt])

  const cancelFrame = useCallback(() => {
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current)
      frame.current = null
    }
    pending.current = null
  }, [])

  const clearClickTimer = useCallback(() => {
    if (clickTimer.current) clearTimeout(clickTimer.current)
    clickTimer.current = null
  }, [])

  const finish = useCallback(
    (event: ReactPointerEvent<HTMLElement>, allowClick: boolean) => {
      if (!down.current) return
      down.current = false
      setPressed(false)
      try {
        event.currentTarget.releasePointerCapture?.(event.pointerId)
      } catch {
        // The pointer may already have been released by the OS.
      }
      const elapsed = performance.now() - downAt.current

      if (draggingRef.current) {
        flush()
        cancelFrame()
        draggingRef.current = false
        setDragging(false)
        api.dragEnd()
        animate(tilt, 0, { type: 'spring', stiffness: 220, damping: 18 })
        return
      }

      cancelFrame()
      animate(tilt, 0, { type: 'spring', stiffness: 220, damping: 18 })
      if (!allowClick || elapsed > CLICK_MS) return

      const now = performance.now()
      if (now - lastClickAt.current < DOUBLE_CLICK_MS) {
        lastClickAt.current = 0
        clearClickTimer()
        handlersRef.current.onDoubleClick()
        return
      }
      lastClickAt.current = now
      clearClickTimer()
      clickTimer.current = setTimeout(() => {
        lastClickAt.current = 0
        clickTimer.current = null
        handlersRef.current.onClick()
      }, CLICK_DELAY_MS)
    },
    [cancelFrame, clearClickTimer, flush, tilt],
  )

  const onPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      if (disabledRef.current || event.button !== 0) return
      down.current = true
      draggingRef.current = false
      downAt.current = performance.now()
      downPoint.current = { x: event.screenX, y: event.screenY }
      lastPoint.current = { x: event.screenX, y: event.screenY }
      lastTime.current = downAt.current
      setPressed(true)
      api.setClickThrough(false)
      try {
        event.currentTarget.setPointerCapture?.(event.pointerId)
      } catch {
        // Some synthetic pointers cannot be captured; dragging still works through moves.
      }
    },
    [],
  )

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      if (!down.current) return
      pending.current = { x: event.screenX, y: event.screenY }
      if (!draggingRef.current) {
        const distance = Math.hypot(
          event.screenX - downPoint.current.x,
          event.screenY - downPoint.current.y,
        )
        if (distance <= THRESHOLD_PX) return
        draggingRef.current = true
        setDragging(true)
      }
      if (frame.current === null) frame.current = requestAnimationFrame(flush)
    },
    [flush],
  )

  const onPointerUp = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => finish(event, true),
    [finish],
  )

  const onPointerCancel = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => finish(event, false),
    [finish],
  )

  useEffect(
    () => () => {
      cancelFrame()
      clearClickTimer()
    },
    [cancelFrame, clearClickTimer],
  )

  return {
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel },
    tilt,
    dragging,
    pressed,
  }
}
