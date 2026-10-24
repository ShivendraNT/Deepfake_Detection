/**
 * Tiny damped spring, integrated with semi-implicit Euler in fixed sub-steps.
 *
 * Every animated value in Satya's rig is a spring chasing a target. Springs give the
 * overshoot-and-settle "jelly" feel of a living character without keyframing every move.
 */

export interface SpringConfig {
  /** Stiffness: higher snaps faster. */
  k: number
  /** Damping: lower wobbles more. */
  c: number
}

export const SOFT: SpringConfig = { k: 120, c: 14 }
export const SNAPPY: SpringConfig = { k: 320, c: 22 }
export const JELLY: SpringConfig = { k: 240, c: 11 }
export const LAZY: SpringConfig = { k: 40, c: 11 }
export const QUICK: SpringConfig = { k: 600, c: 40 }

export class Spring {
  value: number
  velocity = 0
  target: number
  config: SpringConfig

  constructor(value: number, config: SpringConfig = SOFT) {
    this.value = value
    this.target = value
    this.config = config
  }

  set(target: number, config?: SpringConfig): void {
    this.target = target
    if (config) this.config = config
  }

  /** Jump without animation (used for reduced motion and first frame). */
  snap(value: number): void {
    this.value = value
    this.target = value
    this.velocity = 0
  }

  step(dt: number): number {
    const { k, c } = this.config
    const steps = dt > 1 / 120 ? Math.ceil(dt * 120) : 1
    const h = dt / steps
    for (let i = 0; i < steps; i += 1) {
      const accel = k * (this.target - this.value) - c * this.velocity
      this.velocity += accel * h
      this.value += this.velocity * h
    }
    return this.value
  }
}

export function clamp(value: number, min: number, max: number): number {
  return value < min ? min : value > max ? max : value
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

/** Smooth 0→1→0 bump over p in [0, 1]. */
export function bump(p: number): number {
  return p <= 0 || p >= 1 ? 0 : Math.sin(Math.PI * p)
}

/** Ease-out cubic. */
export function easeOut(p: number): number {
  const q = 1 - clamp(p, 0, 1)
  return 1 - q * q * q
}

/** Ease-in-out sine. */
export function easeInOut(p: number): number {
  return 0.5 - 0.5 * Math.cos(Math.PI * clamp(p, 0, 1))
}

/** Map p from [a, b] to [0, 1], clamped. */
export function phase(p: number, a: number, b: number): number {
  return clamp((p - a) / (b - a), 0, 1)
}
