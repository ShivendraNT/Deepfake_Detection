import type { Pose } from '../../../shared/contracts'

export type EyeKind = 'open' | 'wide' | 'sleep' | 'happy'
export type MouthKind = 'smile' | 'happy' | 'rest' | 'straight' | 'firm' | 'o' | 'tiny'
export type BrowKind = 'none' | 'think' | 'alert'
export type PoseLoop = 'breathe' | 'sway' | null

export interface PoseSpec {
  eyes: EyeKind
  mouth: MouthKind
  brows: BrowKind
  blush: boolean
  glasses: boolean
  rings: boolean
  aura: boolean
  paws: boolean
  look: { x: number; y: number } | null
  track: boolean
  loop: PoseLoop
  hop: boolean
  stretch: number
}

export const POSES: Record<Pose, PoseSpec> = {
  sleep: {
    eyes: 'sleep',
    mouth: 'rest',
    brows: 'none',
    blush: false,
    glasses: false,
    rings: false,
    aura: false,
    paws: false,
    look: null,
    track: false,
    loop: null,
    hop: false,
    stretch: 1,
  },
  idle: {
    eyes: 'open',
    mouth: 'smile',
    brows: 'none',
    blush: false,
    glasses: false,
    rings: false,
    aura: false,
    paws: false,
    look: null,
    track: true,
    loop: 'breathe',
    hop: false,
    stretch: 1,
  },
  listen: {
    eyes: 'open',
    mouth: 'smile',
    brows: 'none',
    blush: false,
    glasses: false,
    rings: true,
    aura: false,
    paws: false,
    look: null,
    track: true,
    loop: 'breathe',
    hop: false,
    stretch: 1,
  },
  think: {
    eyes: 'open',
    mouth: 'straight',
    brows: 'think',
    blush: false,
    glasses: false,
    rings: false,
    aura: false,
    paws: false,
    look: { x: 3, y: -3 },
    track: false,
    loop: 'sway',
    hop: false,
    stretch: 1,
  },
  alert: {
    eyes: 'open',
    mouth: 'firm',
    brows: 'alert',
    blush: false,
    glasses: false,
    rings: false,
    aura: true,
    paws: false,
    look: null,
    track: false,
    loop: null,
    hop: true,
    stretch: 1,
  },
  relief: {
    eyes: 'happy',
    mouth: 'happy',
    brows: 'none',
    blush: true,
    glasses: false,
    rings: false,
    aura: false,
    paws: false,
    look: null,
    track: false,
    loop: null,
    hop: false,
    stretch: 1,
  },
  write: {
    eyes: 'open',
    mouth: 'tiny',
    brows: 'none',
    blush: false,
    glasses: true,
    rings: false,
    aura: false,
    paws: false,
    look: { x: 0, y: 3 },
    track: false,
    loop: null,
    hop: false,
    stretch: 1,
  },
  catch: {
    eyes: 'wide',
    mouth: 'o',
    brows: 'none',
    blush: false,
    glasses: false,
    rings: false,
    aura: false,
    paws: true,
    look: null,
    track: false,
    loop: null,
    hop: false,
    stretch: 1.08,
  },
  wave: {
    eyes: 'happy',
    mouth: 'happy',
    brows: 'none',
    blush: true,
    glasses: false,
    rings: false,
    aura: false,
    paws: false,
    look: null,
    track: false,
    loop: null,
    hop: false,
    stretch: 1,
  },
  off: {
    eyes: 'sleep',
    mouth: 'rest',
    brows: 'none',
    blush: false,
    glasses: false,
    rings: false,
    aura: false,
    paws: false,
    look: null,
    track: false,
    loop: null,
    hop: false,
    stretch: 1,
  },
}
