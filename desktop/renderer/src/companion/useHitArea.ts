/**
 * useHitArea — makes almost all of the 280×280 mascot window click-through.
 *
 * A counter (not a boolean) keeps the window clickable while the pointer moves between Satya and
 * menu petals. `forceActive` is used while the menu is open or a drag is captured.
 */

import { useCallback, useEffect, useRef } from 'react'

import { api } from '../shared/api'

export interface HitAreaHandlers {
  onPointerEnter: () => void
  onPointerLeave: () => void
}

export function useHitArea(forceActive: boolean): HitAreaHandlers {
  const depth = useRef(0)
  const forceRef = useRef(forceActive)
  forceRef.current = forceActive

  const sync = useCallback(() => {
    api.setClickThrough(depth.current === 0 && !forceRef.current)
  }, [])

  const onPointerEnter = useCallback(() => {
    depth.current += 1
    sync()
  }, [sync])

  const onPointerLeave = useCallback(() => {
    depth.current = Math.max(0, depth.current - 1)
    sync()
  }, [sync])

  useEffect(() => {
    sync()
  }, [forceActive, sync])

  useEffect(
    () => () => {
      api.setClickThrough(true)
    },
    [],
  )

  return { onPointerEnter, onPointerLeave }
}
