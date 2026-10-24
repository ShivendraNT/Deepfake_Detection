/**
 * Bubble placement maths. Pure functions only: no Electron, no screen access, easy to unit test.
 *
 * Satya sits in a 280×280 click-through window. The bubble opens on the side of the screen with
 * more room: left of Satya when he is on the right half, right of him otherwise. The returned
 * `tail` is the side of the *card* that points back at Satya.
 */

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export interface Size {
  width: number
  height: number
}

export interface BubblePlacement {
  x: number
  y: number
  tail: 'left' | 'right'
}

export const BUBBLE_GAP = 8
export const SNAP_THRESHOLD = 24

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function clampInside(value: number, start: number, span: number, size: number): number {
  const max = start + span - size
  return Math.round(clamp(value, start, Math.max(start, max)))
}

export function placeBubble(
  mascot: Rect,
  workArea: Rect,
  bubble: Size,
  gap: number = BUBBLE_GAP,
): BubblePlacement {
  const mascotCentre = mascot.x + mascot.width / 2
  const onRightHalf = mascotCentre >= workArea.x + workArea.width / 2
  const rawX = onRightHalf
    ? mascot.x - bubble.width - gap
    : mascot.x + mascot.width + gap
  const rawY = mascot.y + mascot.height / 2 - bubble.height / 2

  return {
    x: clampInside(rawX, workArea.x, workArea.width, bubble.width),
    y: clampInside(rawY, workArea.y, workArea.height, bubble.height),
    tail: onRightHalf ? 'right' : 'left',
  }
}

/**
 * Drag release: snap to a screen edge when within `threshold` px, then keep the whole window
 * inside the work area. The Docks and menu bar are respected because `workArea` excludes them.
 */
export function snapToEdges(rect: Rect, workArea: Rect, threshold: number = SNAP_THRESHOLD): Rect {
  let x = rect.x
  let y = rect.y

  if (Math.abs(x - workArea.x) <= threshold) {
    x = workArea.x
  } else if (Math.abs(x + rect.width - (workArea.x + workArea.width)) <= threshold) {
    x = workArea.x + workArea.width - rect.width
  }

  if (Math.abs(y - workArea.y) <= threshold) {
    y = workArea.y
  } else if (Math.abs(y + rect.height - (workArea.y + workArea.height)) <= threshold) {
    y = workArea.y + workArea.height - rect.height
  }

  return {
    ...rect,
    x: clampInside(x, workArea.x, workArea.width, rect.width),
    y: clampInside(y, workArea.y, workArea.height, rect.height),
  }
}

/** Used when a card grows: keep the current position but never off-screen. */
export function clampToWorkArea(rect: Rect, workArea: Rect): Rect {
  return {
    ...rect,
    x: clampInside(rect.x, workArea.x, workArea.width, rect.width),
    y: clampInside(rect.y, workArea.y, workArea.height, rect.height),
  }
}
