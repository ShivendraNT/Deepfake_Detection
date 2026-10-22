import { describe, expect, it } from 'vitest'

import {
  clampToWorkArea,
  placeBubble,
  snapToEdges,
  type Rect,
} from '../main/placement'

const WORK_AREA: Rect = { x: 0, y: 0, width: 1440, height: 900 }
const MASCOT: { width: number; height: number } = { width: 280, height: 280 }
const BUBBLE = { width: 360, height: 200 }

function mascot(x: number, y: number): Rect {
  return { x, y, ...MASCOT }
}

describe('placeBubble', () => {
  it('opens to the right on the bottom-left corner', () => {
    expect(placeBubble(mascot(24, 596), WORK_AREA, BUBBLE)).toEqual({
      x: 312,
      y: 636,
      tail: 'left',
    })
  })

  it('opens to the left on the bottom-right corner', () => {
    expect(placeBubble(mascot(1136, 596), WORK_AREA, BUBBLE)).toEqual({
      x: 768,
      y: 636,
      tail: 'right',
    })
  })

  it('opens to the right on the top-left corner', () => {
    expect(placeBubble(mascot(24, 24), WORK_AREA, BUBBLE)).toEqual({
      x: 312,
      y: 64,
      tail: 'left',
    })
  })

  it('opens to the left on the top-right corner', () => {
    expect(placeBubble(mascot(1136, 24), WORK_AREA, BUBBLE)).toEqual({
      x: 768,
      y: 64,
      tail: 'right',
    })
  })

  it('shifts up to stay on screen near the bottom edge', () => {
    const placement = placeBubble(mascot(100, 850), WORK_AREA, BUBBLE)
    expect(placement.y).toBe(700)
    expect(placement.tail).toBe('left')
  })

  it('never places the card outside a tiny work area', () => {
    const tiny: Rect = { x: 0, y: 0, width: 320, height: 180 }
    expect(placeBubble(mascot(0, 0), tiny, BUBBLE)).toEqual({ x: 0, y: 0, tail: 'left' })
  })

  it('respects a work area that does not start at the origin', () => {
    const area: Rect = { x: 200, y: 100, width: 1000, height: 700 }
    const placement = placeBubble(mascot(950, 520), area, BUBBLE)
    expect(placement.tail).toBe('right')
    expect(placement.x).toBe(950 - 360 - 8)
    expect(placement.y).toBe(560)
  })
})

describe('snapToEdges', () => {
  it('snaps to the left and top edges within 24 px', () => {
    const snapped = snapToEdges({ x: 10, y: 12, width: 280, height: 280 }, WORK_AREA)
    expect(snapped).toEqual({ x: 0, y: 0, width: 280, height: 280 })
  })

  it('snaps to the right and bottom edges within 24 px', () => {
    const snapped = snapToEdges({ x: 1136, y: 600, width: 280, height: 280 }, WORK_AREA)
    expect(snapped).toEqual({ x: 1160, y: 620, width: 280, height: 280 })
  })

  it('leaves a window in the middle alone', () => {
    const rect: Rect = { x: 500, y: 300, width: 280, height: 280 }
    expect(snapToEdges(rect, WORK_AREA)).toEqual(rect)
  })

  it('clamps a window dragged past the right edge', () => {
    const snapped = snapToEdges({ x: 1400, y: 900, width: 280, height: 280 }, WORK_AREA)
    expect(snapped.x).toBe(1160)
    expect(snapped.y).toBe(620)
  })
})

describe('clampToWorkArea', () => {
  it('pulls an oversized window back inside the work area', () => {
    expect(clampToWorkArea({ x: -40, y: 950, width: 280, height: 280 }, WORK_AREA)).toEqual({
      x: 0,
      y: 620,
      width: 280,
      height: 280,
    })
  })
})
