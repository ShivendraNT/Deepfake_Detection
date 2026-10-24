import { useEffect, useState } from 'react'

import type { Pose } from '../../../shared/contracts'

export const BLINK_MS = 140
const MIN_DELAY_MS = 2500
const MAX_DELAY_MS = 6000
const DOUBLE_CHANCE = 0.2

function randomDelay(): number {
  return MIN_DELAY_MS + Math.random() * (MAX_DELAY_MS - MIN_DELAY_MS)
}

export function useBlink(pose: Pose, reducedMotion: boolean): number {
  const [blinkKey, setBlinkKey] = useState(0)

  useEffect(() => {
    if (pose === 'sleep' || pose === 'off' || reducedMotion) return

    let cancelled = false
    let timer = 0
    let followUp = 0

    const schedule = (delay: number) => {
      timer = window.setTimeout(() => {
        if (cancelled) return
        setBlinkKey((key) => key + 1)

        if (Math.random() < DOUBLE_CHANCE) {
          followUp = window.setTimeout(() => {
            if (cancelled) return
            setBlinkKey((key) => key + 1)
            schedule(randomDelay())
          }, BLINK_MS * 2)
        } else {
          schedule(randomDelay())
        }
      }, delay)
    }

    schedule(randomDelay())

    return () => {
      cancelled = true
      window.clearTimeout(timer)
      window.clearTimeout(followUp)
    }
  }, [pose, reducedMotion])

  return blinkKey
}
