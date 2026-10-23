/**
 * SatyaEngine — the "life" of the mascot, with no DOM and no React.
 *
 * Each frame it turns (pose, cursor, audio level, gestures, time) into a `RigFrame`: a flat bag of
 * numbers (positions, rotations, opacities) that `SatyaSprite` writes onto the SVG. Three layers
 * stack on top of each other:
 *
 *  1. Pose targets  — where every part *wants* to be in this pose (springs chase them).
 *  2. Behaviours    — continuous motion for the pose: breathing, nodding to speech, scanning with
 *                     the magnifier, writing, tapping a foot while waiting for the approver.
 *  3. Actions       — one-shot gestures with a timeline: blink, hop, startle, wave, yawn, boop,
 *                     celebrate… Idle fidgets are actions picked at random so he never freezes.
 *
 * Particles (Zzz, hearts, sparkles, confetti, puffs, notes) are simulated here too.
 * Everything is deterministic given the RNG seed, so the rig is unit-testable.
 */

import { bump, clamp, easeInOut, easeOut, JELLY, LAZY, phase, QUICK, SNAPPY, SOFT, Spring, type SpringConfig } from './spring'

export type SatyaPose =
  | 'sleep'
  | 'idle'
  | 'listen'
  | 'think'
  | 'alert'
  | 'hold'
  | 'verify'
  | 'relief'
  | 'write'
  | 'catch'
  | 'wave'
  | 'off'

export const SATYA_POSES: SatyaPose[] = [
  'sleep',
  'idle',
  'listen',
  'think',
  'alert',
  'hold',
  'verify',
  'relief',
  'write',
  'catch',
  'wave',
  'off',
]

export type Emote =
  | 'blink'
  | 'hop'
  | 'startle'
  | 'celebrate'
  | 'wave'
  | 'yawn'
  | 'wake'
  | 'lookAround'
  | 'wiggle'
  | 'capTip'
  | 'stretch'
  | 'boop'
  | 'giggle'
  | 'nod'
  | 'shake'
  | 'notice'
  | 'gulp'
  | 'land'
  | 'bye'
  | 'appear'
  | 'perk'

export const ACCENT = {
  none: '#22C7DC',
  watch: '#22C7DC',
  verify: '#FFB020',
  hold: '#FF5E57',
  write: '#9C8CFF',
  good: '#3CCB7F',
  sleep: '#8C96AA',
} as const

export type AccentName = keyof typeof ACCENT

/** Springed channels. Names are short because the renderer reads them every frame. */
const CHANNELS = [
  'bodyY',
  'bodySX',
  'bodySY',
  'bodyRot',
  'capX',
  'capY',
  'capRot',
  'eyeOpen',
  'eyeScale',
  'lowerLid',
  'pupilX',
  'pupilY',
  'gOpen',
  'gHappy',
  'gClosed',
  'gHeart',
  'browY',
  'browTilt',
  'browOp',
  'mSmile',
  'mGrin',
  'mO',
  'mFlat',
  'mWavy',
  'mFrown',
  'mCat',
  'mTongue',
  'mouthOpen',
  'cheek',
  'pawLX',
  'pawLY',
  'pawLR',
  'pawRX',
  'pawRY',
  'pawRR',
  'pHeadphones',
  'pMagnifier',
  'pShield',
  'pGlasses',
  'pQuill',
  'pPaper',
  'pPhone',
  'pWaves',
  'pDots',
  'pExclaim',
  'pQuestion',
  'pSweat',
  'pStop',
  'aura',
  'emblem',
  'scale',
  'alpha',
] as const

export type Channel = (typeof CHANNELS)[number]
export type Targets = Record<Channel, number>

/** Additive (non-springed) offsets layered on top of the springs every frame. */
const ADDITIVE = [
  'bodyX',
  'bodyY',
  'bodyRot',
  'bodySX',
  'bodySY',
  'faceX',
  'faceY',
  'capY',
  'capRot',
  'pawLX',
  'pawLY',
  'pawLR',
  'pawRX',
  'pawRY',
  'pawRR',
  'pupilX',
  'pupilY',
  'eyeClose',
  'mouthOpen',
  'propRot',
  'scale',
] as const

export type AddChannel = (typeof ADDITIVE)[number]
export type Additive = Record<AddChannel, number>

export const REST = {
  pawL: { x: 80, y: 174, r: 0 },
  pawR: { x: 120, y: 174, r: 0 },
} as const

const DEFAULTS: Targets = {
  bodyY: 0,
  bodySX: 1,
  bodySY: 1,
  bodyRot: 0,
  capX: 0,
  capY: 0,
  capRot: 0,
  eyeOpen: 1,
  eyeScale: 1,
  lowerLid: 0,
  pupilX: 0,
  pupilY: 0,
  gOpen: 1,
  gHappy: 0,
  gClosed: 0,
  gHeart: 0,
  browY: 0,
  browTilt: 0,
  browOp: 1,
  mSmile: 1,
  mGrin: 0,
  mO: 0,
  mFlat: 0,
  mWavy: 0,
  mFrown: 0,
  mCat: 0,
  mTongue: 0,
  mouthOpen: 1,
  cheek: 0.5,
  pawLX: REST.pawL.x,
  pawLY: REST.pawL.y,
  pawLR: REST.pawL.r,
  pawRX: REST.pawR.x,
  pawRY: REST.pawR.y,
  pawRR: REST.pawR.r,
  pHeadphones: 0,
  pMagnifier: 0,
  pShield: 0,
  pGlasses: 0,
  pQuill: 0,
  pPaper: 0,
  pPhone: 0,
  pWaves: 0,
  pDots: 0,
  pExclaim: 0,
  pQuestion: 0,
  pSweat: 0,
  pStop: 0,
  aura: 0,
  emblem: 0.25,
  scale: 1,
  alpha: 1,
}

/** Which springs use which feel. Everything else is SOFT. */
const SPRING_FEEL: Partial<Record<Channel, SpringConfig>> = {
  bodyY: JELLY,
  bodySX: JELLY,
  bodySY: JELLY,
  bodyRot: SOFT,
  capY: JELLY,
  capRot: SOFT,
  eyeOpen: QUICK,
  eyeScale: SNAPPY,
  lowerLid: SNAPPY,
  pupilX: { k: 260, c: 26 },
  pupilY: { k: 260, c: 26 },
  gOpen: QUICK,
  gHappy: QUICK,
  gClosed: QUICK,
  gHeart: QUICK,
  mSmile: QUICK,
  mGrin: QUICK,
  mO: QUICK,
  mFlat: QUICK,
  mWavy: QUICK,
  mFrown: QUICK,
  mCat: QUICK,
  mTongue: QUICK,
  mouthOpen: SNAPPY,
  pawLX: SNAPPY,
  pawLY: SNAPPY,
  pawLR: SNAPPY,
  pawRX: SNAPPY,
  pawRY: SNAPPY,
  pawRR: SNAPPY,
  pHeadphones: JELLY,
  pMagnifier: JELLY,
  pShield: JELLY,
  pGlasses: JELLY,
  pQuill: JELLY,
  pPaper: SNAPPY,
  pPhone: JELLY,
  pWaves: SOFT,
  pDots: SNAPPY,
  pExclaim: JELLY,
  pQuestion: JELLY,
  pSweat: SOFT,
  pStop: JELLY,
  aura: LAZY,
  emblem: SOFT,
  scale: JELLY,
  alpha: SOFT,
}

const EYE_GLYPHS: Channel[] = ['gOpen', 'gHappy', 'gClosed', 'gHeart']
const MOUTHS: Channel[] = ['mSmile', 'mGrin', 'mO', 'mFlat', 'mWavy', 'mFrown', 'mCat', 'mTongue']

export type ParticleKind = 'z' | 'heart' | 'spark' | 'confetti' | 'puff' | 'note' | 'tear'

export interface Particle {
  id: number
  kind: ParticleKind
  x: number
  y: number
  vx: number
  vy: number
  gravity: number
  age: number
  life: number
  rot: number
  spin: number
  size: number
  color: string
  wobble: number
}

export interface RigFrame extends Targets {
  bodyX: number
  faceX: number
  faceY: number
  propRot: number
  shadowScale: number
  shadowAlpha: number
  accent: string
  waveLevel: number
  time: number
  paperProgress: number
  lensX: number
  lensY: number
  particles: readonly Particle[]
}

export interface Look {
  dx: number
  dy: number
  near: boolean
}

interface ActionState {
  name: Emote
  start: number
  duration: number
  seed: number
}

interface ActionResult {
  targets?: Partial<Targets>
  add?: Partial<Additive>
}

type ActionFn = (p: number, a: ActionState, e: SatyaEngine) => ActionResult

/** Small deterministic RNG (mulberry32) so tests can pin behaviour. */
export function makeRng(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const DURATIONS: Record<Emote, number> = {
  blink: 0.15,
  hop: 0.55,
  startle: 0.75,
  celebrate: 1.5,
  wave: 1.4,
  yawn: 1.9,
  wake: 1.7,
  lookAround: 2.4,
  wiggle: 0.8,
  capTip: 1.3,
  stretch: 2.0,
  boop: 0.55,
  giggle: 0.9,
  nod: 0.7,
  shake: 0.8,
  notice: 1.4,
  gulp: 0.55,
  land: 0.5,
  bye: 1.5,
  appear: 0.7,
  perk: 0.9,
}

function hop(p: number, height: number): ActionResult {
  // anticipation squash -> airborne stretch -> landing squash
  const squash1 = bump(phase(p, 0, 0.18))
  const air = phase(p, 0.15, 0.78)
  const squash2 = bump(phase(p, 0.74, 1))
  return {
    add: {
      bodyY: -height * Math.sin(Math.PI * air) * (air > 0 && air < 1 ? 1 : 0) + squash1 * 2 + squash2 * 2,
      bodySY: -0.09 * squash1 + 0.07 * bump(air) - 0.08 * squash2,
      bodySX: 0.07 * squash1 - 0.04 * bump(air) + 0.07 * squash2,
    },
  }
}

const ACTIONS: Record<Emote, ActionFn> = {
  blink: (p) => ({ add: { eyeClose: bump(p) } }),

  hop: (p) => hop(p, 12),

  startle: (p) => {
    const base = hop(p, 16)
    return {
      targets: { eyeScale: 1.22, mO: 1, mSmile: 0, mFlat: 0, mFrown: 0, mouthOpen: 1.2, pExclaim: 1 },
      add: { ...base.add, capY: -12 * bump(phase(p, 0.05, 0.7)), capRot: 10 * bump(phase(p, 0.1, 0.8)) },
    }
  },

  celebrate: (p) => {
    const first = p < 0.5 ? hop(p / 0.5, 18).add ?? {} : {}
    const second = p >= 0.5 ? hop((p - 0.5) / 0.5, 12).add ?? {} : {}
    const wig = Math.sin(p * Math.PI * 10) * 18 * (1 - p)
    return {
      targets: {
        gHappy: 1,
        gOpen: 0,
        mGrin: 1,
        mSmile: 0,
        cheek: 1,
        pawLX: 52,
        pawLY: 112,
        pawRX: 148,
        pawRY: 112,
      },
      add: {
        bodyY: (first.bodyY ?? 0) + (second.bodyY ?? 0),
        bodySY: (first.bodySY ?? 0) + (second.bodySY ?? 0),
        bodySX: (first.bodySX ?? 0) + (second.bodySX ?? 0),
        pawLR: -wig,
        pawRR: wig,
      },
    }
  },

  wave: (p) => {
    const up = easeOut(phase(p, 0, 0.18)) * (1 - phase(p, 0.85, 1))
    return {
      targets: { pawRX: 156, pawRY: 116, lowerLid: 0.45, mGrin: 1, mSmile: 0, cheek: 0.9 },
      add: { pawRR: up * (Math.sin(p * Math.PI * 7) * 28 - 10), bodyRot: up * Math.sin(p * Math.PI * 3.5) * 2 },
    }
  },

  yawn: (p) => {
    const open = bump(phase(p, 0.05, 0.85))
    return {
      targets: {
        mO: 1,
        mSmile: 0,
        mFlat: 0,
        pawLX: 56,
        pawLY: 128,
        pawRX: 144,
        pawRY: 128,
      },
      add: {
        mouthOpen: open * 1.3,
        eyeClose: 0.85 * open,
        bodySY: 0.06 * open,
        bodySX: -0.03 * open,
        pawLR: -30 * open,
        pawRR: 30 * open,
      },
    }
  },

  wake: (p) => {
    const stretch = bump(phase(p, 0.1, 0.65))
    const closed = 1 - easeOut(phase(p, 0.2, 0.55))
    return {
      targets: { pawLX: 54, pawLY: 104, pawRX: 146, pawRY: 104, mO: stretch > 0.4 ? 1 : 0 },
      add: {
        eyeClose: closed * 0.95,
        bodySY: 0.08 * stretch,
        bodySX: -0.04 * stretch,
        pawLR: -35 * stretch,
        pawRR: 35 * stretch,
        bodyY: -6 * bump(phase(p, 0.75, 1)),
      },
    }
  },

  lookAround: (p) => {
    let x = 0
    if (p < 0.12) x = -easeInOut(p / 0.12)
    else if (p < 0.42) x = -1
    else if (p < 0.55) x = -1 + 2 * easeInOut((p - 0.42) / 0.13)
    else if (p < 0.85) x = 1
    else x = 1 - easeInOut((p - 0.85) / 0.15)
    return { targets: { pupilX: x * 0.9 }, add: { bodyRot: x * 3, faceX: x * 2 } }
  },

  wiggle: (p) => ({ add: { bodyRot: Math.sin(p * Math.PI * 4) * 5 * (1 - p), bodySX: 0.03 * bump(p) } }),

  capTip: (p) => {
    const reach = bump(phase(p, 0, 1))
    return {
      targets: { pawRX: 148, pawRY: 94, lowerLid: 0.3 },
      add: { capRot: 9 * bump(phase(p, 0.25, 0.85)), capY: -3 * bump(phase(p, 0.3, 0.8)), pawRR: -20 * reach },
    }
  },

  stretch: (p) => {
    const s = bump(p)
    return {
      targets: { pawLX: 58, pawLY: 98, pawRX: 142, pawRY: 98, gHappy: 1, gOpen: 0, mO: 1, mSmile: 0 },
      add: { bodySY: 0.1 * s, bodySX: -0.05 * s, mouthOpen: 0.5 * s },
    }
  },

  boop: (p) => {
    const squash = bump(phase(p, 0, 0.35))
    const rebound = bump(phase(p, 0.3, 1))
    return {
      targets: { gHappy: 1, gOpen: 0, mCat: 1, mSmile: 0, cheek: 1 },
      add: { bodySY: -0.13 * squash + 0.05 * rebound, bodySX: 0.1 * squash - 0.03 * rebound },
    }
  },

  giggle: (p) => ({
    targets: { gHappy: 1, gOpen: 0, mGrin: 1, mSmile: 0, cheek: 1 },
    add: { bodyRot: Math.sin(p * Math.PI * 10) * 3.5 * (1 - p), bodyY: -Math.abs(Math.sin(p * Math.PI * 5)) * 2 },
  }),

  nod: (p) => ({ add: { faceY: Math.sin(p * Math.PI * 4) * 3 * (1 - p), bodyY: Math.sin(p * Math.PI * 4) * 1.2 } }),

  shake: (p) => ({ add: { faceX: Math.sin(p * Math.PI * 6) * 4 * (1 - p), bodyRot: Math.sin(p * Math.PI * 6) * 3 * (1 - p) } }),

  notice: (p) => ({
    targets: { pQuestion: p < 0.85 ? 1 : 0, browY: -4, eyeScale: 1.1 },
    add: { bodyRot: 7 * bump(phase(p, 0, 0.9)), pupilX: 0.5 * bump(phase(p, 0, 0.9)) },
  }),

  gulp: (p) => {
    const s = bump(phase(p, 0.2, 0.7))
    return {
      targets: { mO: p < 0.3 ? 1 : 0, gHappy: p > 0.4 ? 1 : 0, gOpen: p > 0.4 ? 0 : 1 },
      add: { bodySY: -0.1 * s, bodySX: 0.08 * s, bodyY: 2 * s },
    }
  },

  land: (p) => {
    const s = bump(p)
    return { add: { bodySY: -0.14 * s, bodySX: 0.12 * s, bodyY: 3 * s } }
  },

  bye: (p) => {
    const waving = 1 - phase(p, 0.5, 0.6)
    const gone = easeInOut(phase(p, 0.5, 1))
    return {
      targets: { pawRX: 156, pawRY: 116, gHappy: 1, gOpen: 0, mGrin: 1, mSmile: 0 },
      add: {
        pawRR: waving * Math.sin(p * Math.PI * 9) * 26,
        scale: -gone,
        bodyRot: gone * 200,
        bodyY: -10 * gone,
      },
    }
  },

  appear: (p) => {
    const s = easeOut(p)
    return { add: { scale: -(1 - s) + Math.sin(p * Math.PI) * 0.12 } }
  },

  perk: (p) => ({
    targets: { eyeScale: 1.14, browY: -4 },
    add: { bodyY: -4 * bump(phase(p, 0, 0.6)), bodySY: 0.04 * bump(phase(p, 0, 0.6)) },
  }),
}

interface PoseSpec {
  targets: Partial<Targets>
  accent: AccentName
  /** Does the cursor steer his eyes in this pose? */
  look: boolean
  /** Does he blink in this pose? */
  blink: boolean
  /** Breathing period (s) and amplitude. */
  breath: [number, number]
  /** Gesture played when entering the pose. */
  enter?: Emote
}

const POSES: Record<SatyaPose, PoseSpec> = {
  sleep: {
    targets: {
      gOpen: 0,
      gClosed: 1,
      browOp: 0.35,
      browY: 3,
      mSmile: 0,
      mO: 1,
      mouthOpen: 0.42,
      cheek: 0.75,
      bodyY: 3,
      bodySY: 0.97,
      bodySX: 1.02,
      capRot: -11,
      capY: 5,
      capX: -3,
      pawLX: 84,
      pawLY: 176,
      pawRX: 116,
      pawRY: 176,
      emblem: 0,
    },
    accent: 'sleep',
    look: false,
    blink: false,
    breath: [4.6, 0.022],
    enter: 'yawn',
  },
  idle: { targets: {}, accent: 'none', look: true, blink: true, breath: [3.4, 0.014] },
  listen: {
    targets: {
      pHeadphones: 1,
      pWaves: 1,
      eyeOpen: 0.9,
      browY: -1.5,
      emblem: 0.75,
      aura: 0.16,
      cheek: 0.6,
    },
    accent: 'watch',
    look: true,
    blink: true,
    breath: [3.0, 0.012],
    enter: 'perk',
  },
  think: {
    targets: {
      pMagnifier: 1,
      pDots: 1,
      browTilt: 5,
      browY: 1,
      mSmile: 0,
      mWavy: 1,
      eyeOpen: 0.94,
      emblem: 0.5,
      aura: 0.1,
    },
    accent: 'watch',
    look: false,
    blink: true,
    breath: [3.0, 0.012],
  },
  alert: {
    targets: {
      pShield: 1,
      pExclaim: 1,
      eyeScale: 1.08,
      browTilt: -9,
      browY: -3,
      mSmile: 0,
      mFlat: 1,
      pawRX: 136,
      pawRY: 160,
      pawRR: -6,
      aura: 0.55,
      emblem: 1,
      cheek: 0.35,
    },
    accent: 'verify',
    look: true,
    blink: true,
    breath: [2.3, 0.012],
    enter: 'startle',
  },
  hold: {
    targets: {
      pShield: 1,
      pExclaim: 1,
      pStop: 1,
      pSweat: 1,
      eyeScale: 1.04,
      browTilt: 11,
      browY: 1,
      mSmile: 0,
      mFrown: 1,
      pawLX: 50,
      pawLY: 124,
      pawLR: -18,
      pawRX: 136,
      pawRY: 160,
      pawRR: -6,
      aura: 0.75,
      emblem: 1,
      cheek: 0.3,
    },
    accent: 'hold',
    look: true,
    blink: true,
    breath: [1.7, 0.012],
    enter: 'startle',
  },
  verify: {
    targets: {
      pPhone: 1,
      pDots: 1,
      browTilt: -4,
      mSmile: 0.6,
      mFlat: 0.4,
      pawLX: 50,
      pawLY: 128,
      pawLR: -10,
      aura: 0.35,
      emblem: 0.8,
    },
    accent: 'verify',
    look: false,
    blink: true,
    breath: [2.6, 0.012],
    enter: 'nod',
  },
  relief: {
    targets: {
      gOpen: 0,
      gHappy: 1,
      mSmile: 0,
      mGrin: 1,
      cheek: 1,
      browY: -3,
      pawLX: 64,
      pawLY: 150,
      pawLR: -20,
      pawRX: 136,
      pawRY: 150,
      pawRR: 20,
      aura: 0.5,
      emblem: 1,
    },
    accent: 'good',
    look: false,
    blink: false,
    breath: [2.6, 0.016],
    enter: 'celebrate',
  },
  write: {
    targets: {
      pGlasses: 1,
      pQuill: 1,
      pPaper: 1,
      browTilt: 3,
      mSmile: 0,
      mTongue: 1,
      pawLX: 84,
      pawLY: 178,
      aura: 0.2,
      emblem: 0.6,
    },
    accent: 'write',
    look: false,
    blink: true,
    breath: [3.2, 0.012],
  },
  catch: {
    targets: {
      eyeScale: 1.16,
      mSmile: 0,
      mGrin: 1,
      mouthOpen: 1.15,
      pawLX: 54,
      pawLY: 134,
      pawLR: -38,
      pawRX: 146,
      pawRY: 134,
      pawRR: 38,
      bodySY: 1.06,
      bodySX: 0.97,
      browY: -4,
      cheek: 0.85,
      emblem: 0.8,
    },
    accent: 'watch',
    look: true,
    blink: false,
    breath: [1.4, 0.01],
  },
  wave: {
    targets: { mSmile: 0, mGrin: 1, lowerLid: 0.4, cheek: 0.85 },
    accent: 'none',
    look: true,
    blink: true,
    breath: [3.0, 0.014],
    enter: 'hop',
  },
  off: {
    targets: { gOpen: 0, gHappy: 1, mSmile: 0, mGrin: 1 },
    accent: 'sleep',
    look: false,
    blink: false,
    breath: [3.4, 0.01],
    enter: 'bye',
  },
}

const IDLE_FIDGETS: Emote[] = ['lookAround', 'hop', 'wiggle', 'capTip', 'lookAround', 'giggle', 'stretch', 'nod']

export interface EngineOptions {
  seed?: number
  reducedMotion?: boolean
  pose?: SatyaPose
}

export class SatyaEngine {
  pose: SatyaPose
  private poseSince = 0
  private time = 0
  private readonly springs: Record<Channel, Spring>
  private actions: ActionState[] = []
  private particles: Particle[] = []
  private particleId = 0
  private rng: () => number
  private reducedMotion: boolean

  private look: Look = { dx: 0, dy: 0, near: false }
  private lookFarSince = 0
  private level = 0
  private levelSmooth = 0
  private talking = false
  private drag = { active: false, vx: 0, vy: 0 }
  private petting = 0
  private hiding = false

  private nextBlinkAt = 2
  private nextFidgetAt = 5
  private nextSaccadeAt = 1.5
  private saccade = { x: 0, y: 0 }
  private nextZAt = 0.5
  private nextHeartAt = 0
  private nextSparkAt = 0
  private nextNoteAt = 0
  private tiltSign = 1
  private nextTiltAt = 4

  constructor(options: EngineOptions = {}) {
    this.rng = makeRng(options.seed ?? 7)
    this.reducedMotion = options.reducedMotion ?? false
    this.pose = options.pose ?? 'sleep'
    const base = this.baseTargets(this.pose)
    this.springs = Object.fromEntries(
      CHANNELS.map((name) => [name, new Spring(base[name], SPRING_FEEL[name] ?? SOFT)]),
    ) as Record<Channel, Spring>
  }

  // ------------------------------------------------------------------ inputs

  setPose(pose: SatyaPose): void {
    if (pose === this.pose) return
    const previous = this.pose
    this.pose = pose
    this.poseSince = this.time
    // Clear gestures that belong to the old pose, keep blinks.
    this.actions = this.actions.filter((a) => a.name === 'blink')
    if (this.reducedMotion) return
    if (previous === 'off' && pose !== 'off') this.play('appear')
    if (previous === 'sleep' && pose !== 'sleep' && pose !== 'off') {
      this.play(pose === 'idle' ? 'wake' : (POSES[pose].enter ?? 'wake'))
      return
    }
    const enter = POSES[pose].enter
    if (enter) this.play(enter)
    if (pose === 'relief') this.burst('confetti', 16)
    if (pose === 'alert' || pose === 'hold') this.burst('spark', 4)
  }

  setLook(look: Look): void {
    if (look.near && !this.look.near && this.time - this.lookFarSince > 6 && this.pose === 'idle') {
      // He notices you coming back after a while.
      this.play('perk')
    }
    if (!look.near && this.look.near) this.lookFarSince = this.time
    this.look = look
  }

  /** 0..1 loudness of the call audio (local only). */
  setLevel(level: number): void {
    this.level = clamp(Number.isFinite(level) ? level : 0, 0, 1)
  }

  /** Mouth flaps while Satya "says" a quip. */
  setTalking(talking: boolean): void {
    this.talking = talking
  }

  setDrag(active: boolean, vx = 0, vy = 0): void {
    if (this.drag.active && !active && !this.reducedMotion) this.play('land')
    this.drag = { active, vx, vy }
  }

  /** Called while the pointer rubs over him. Decays on its own. */
  pet(): void {
    this.petting = Math.min(1.5, this.petting + 0.35)
  }

  setReducedMotion(reduced: boolean): void {
    this.reducedMotion = reduced
  }

  /** Play a one-shot gesture. Re-playing restarts it. */
  play(name: Emote): void {
    if (this.reducedMotion && name !== 'blink') return
    this.actions = this.actions.filter((a) => a.name !== name)
    this.actions.push({ name, start: this.time, duration: DURATIONS[name], seed: this.rng() })
    if (name === 'boop') this.spawn('heart', 100 + (this.rng() - 0.5) * 30, 82)
    if (name === 'bye') this.hiding = true
    if (name === 'appear') this.hiding = false
    if (name === 'celebrate') this.burst('spark', 5)
  }

  isPlaying(name: Emote): boolean {
    return this.actions.some((a) => a.name === name)
  }

  // ------------------------------------------------------------------ simulation

  private baseTargets(pose: SatyaPose): Targets {
    return { ...DEFAULTS, ...POSES[pose].targets }
  }

  tick(dtRaw: number): RigFrame {
    const dt = clamp(dtRaw, 0, 1 / 20)
    this.time += dt
    const t = this.time
    const since = t - this.poseSince
    const spec = POSES[this.pose]
    const targets = this.baseTargets(this.pose)
    const add: Additive = Object.fromEntries(ADDITIVE.map((k) => [k, 0])) as Additive

    this.levelSmooth += (this.level - this.levelSmooth) * (1 - Math.exp(-dt * 14))
    this.petting = Math.max(0, this.petting - dt * 0.9)

    const motion = !this.reducedMotion

    // ---- schedulers
    if (motion && spec.blink && t >= this.nextBlinkAt) {
      this.play('blink')
      const double = this.rng() < 0.2
      this.nextBlinkAt = t + (double ? 0.22 : 2.4 + this.rng() * 3.6)
    }
    if (motion && this.pose === 'idle' && since > 2 && t >= this.nextFidgetAt && !this.busy()) {
      const pick = IDLE_FIDGETS[Math.floor(this.rng() * IDLE_FIDGETS.length)]
      this.play(pick)
      this.nextFidgetAt = t + 4.5 + this.rng() * 5.5
    }
    if (t >= this.nextSaccadeAt) {
      this.saccade = { x: (this.rng() - 0.5) * 1.1, y: (this.rng() - 0.5) * 0.6 }
      this.nextSaccadeAt = t + 1.2 + this.rng() * 2.6
    }

    // ---- look-at (cursor) or wandering eyes
    let lookX = 0
    let lookY = 0
    if (spec.look) {
      if (this.look.near) {
        lookX = clamp(this.look.dx / 160, -1, 1)
        lookY = clamp(this.look.dy / 160, -1, 1)
      } else if (motion) {
        lookX = this.saccade.x
        lookY = this.saccade.y
      }
      targets.pupilX = lookX
      targets.pupilY = lookY
    }

    // ---- per-pose behaviour
    const [period, amp] = spec.breath
    const breath = motion ? Math.sin((2 * Math.PI * t) / period) : 0
    add.bodySY += amp * breath
    add.bodySX -= amp * 0.6 * breath
    let lensX = 132
    let lensY = 138
    let paperProgress = 0

    if (motion) {
      switch (this.pose) {
        case 'idle':
          add.bodyY += Math.sin(t * 1.3) * 0.9
          break
        case 'sleep':
          add.bodyRot += Math.sin(t * 0.42) * 1.6
          add.mouthOpen += breath * 0.12
          if (t >= this.nextZAt) {
            this.spawn('z', 134, 70)
            this.nextZAt = t + 1.5 + this.rng() * 0.5
          }
          break
        case 'listen': {
          const lv = this.levelSmooth
          // Nod along with the other person's speech; tilt the head now and then.
          add.faceY += Math.abs(Math.sin(t * Math.PI * 2.2)) * lv * 3.2
          add.bodyY += Math.abs(Math.sin(t * Math.PI * 2.2)) * lv * 1.4
          if (t >= this.nextTiltAt) {
            this.tiltSign = -this.tiltSign
            this.nextTiltAt = t + 4 + this.rng() * 3
          }
          targets.bodyRot = this.tiltSign * 3.5
          targets.emblem = 0.55 + lv * 0.45
          if (lv > 0.35 && t >= this.nextNoteAt) {
            this.spawn('note', this.rng() < 0.5 ? 42 : 158, 104)
            this.nextNoteAt = t + 0.9 + this.rng() * 0.8
          }
          break
        }
        case 'think': {
          // The magnifier sweeps a lazy figure-eight in front of his face; the eyes follow it.
          lensX = 128 + Math.sin(t * 1.7) * 20
          lensY = 132 + Math.sin(t * 3.4) * 7
          targets.pawRX = lensX + 14
          targets.pawRY = lensY + 18
          targets.pawRR = -18
          targets.pupilX = clamp((lensX - 100) / 34, -1, 1)
          targets.pupilY = clamp((lensY - 126) / 30, -1, 1)
          add.bodyRot += Math.sin(t * 1.7) * 2
          break
        }
        case 'alert':
          add.bodyY += Math.sin(t * 2.7) * 0.6
          if (since > 3) targets.pExclaim = 0.0
          break
        case 'hold':
          add.bodyY += Math.sin(t * 3.2) * 0.8
          add.pawLR += Math.sin(t * 3.2) * 4
          break
        case 'verify': {
          // Waiting for the approver: phone at the ear, tapping a foot, eyes up.
          targets.pupilX = -0.45
          targets.pupilY = -0.55
          add.bodyY += -Math.max(0, Math.sin(t * Math.PI * 3.2)) * 1.8
          const buzz = (t % 1.4) < 0.32 ? Math.sin(t * 90) * 4 : 0
          add.propRot += buzz
          break
        }
        case 'relief':
          if (t >= this.nextSparkAt && since < 2.6) {
            this.spawn('spark', 100 + (this.rng() - 0.5) * 120, 90 + (this.rng() - 0.5) * 80)
            this.nextSparkAt = t + 0.25
          }
          add.bodyRot += Math.sin(t * 3) * 2
          break
        case 'write': {
          // Quill scribbles small loops along a line, then carriage-returns.
          const line = (since * 0.7) % 1
          targets.pawRX = 108 + line * 22
          targets.pawRY = 170
          add.pawRX += Math.sin(t * 22) * 1.6
          add.pawRY += Math.cos(t * 22) * 1.4
          add.pawRR += Math.sin(t * 22) * 6
          targets.pupilX = clamp((targets.pawRX - 118) / 30, -0.6, 0.6)
          targets.pupilY = 0.75
          paperProgress = since * 0.7
          break
        }
        case 'catch':
          add.bodyY += Math.sin(t * 8) * 1.4
          targets.bodyRot = clamp(lookX * 8, -8, 8)
          break
        case 'wave': {
          // Keep waving hello while in this pose.
          const up = Math.min(1, since * 4)
          targets.pawRX = 156
          targets.pawRY = 114
          add.pawRR += up * (Math.sin(t * 11) * 26 - 8)
          add.bodyRot += Math.sin(t * 5.5) * 1.5
          break
        }
        case 'off':
          break
      }
    }
    if (this.pose === 'write') paperProgress = since * 0.7

    // ---- petting and drag
    if (this.petting > 0.2 && motion) {
      targets.gHappy = 1
      targets.gOpen = 0
      targets.cheek = 1
      if (!this.isTalkingMouth()) {
        for (const m of MOUTHS) targets[m] = 0
        targets.mCat = 1
      }
      add.bodyRot += Math.sin(t * 9) * 2.5 * Math.min(1, this.petting)
      if (t >= this.nextHeartAt) {
        this.spawn('heart', 100 + (this.rng() - 0.5) * 50, 78)
        this.nextHeartAt = t + 0.32
      }
    }
    if (this.drag.active && motion) {
      const vx = clamp(this.drag.vx, -40, 40)
      const vy = clamp(this.drag.vy, -40, 40)
      targets.bodyRot = clamp(-vx * 0.6, -16, 16)
      targets.bodySY = 1 + clamp(Math.abs(vy) * 0.004, 0, 0.12)
      targets.bodySX = 1 - clamp(Math.abs(vy) * 0.003, 0, 0.08)
      targets.eyeScale = 1.15
      for (const m of MOUTHS) targets[m] = 0
      targets.mGrin = 1
      // Paws dangle behind the motion.
      targets.pawLX = REST.pawL.x - 6 + vx * 0.5
      targets.pawRX = REST.pawR.x + 6 + vx * 0.5
      targets.pawLY = REST.pawL.y + 6 + vy * 0.3
      targets.pawRY = REST.pawR.y + 6 + vy * 0.3
      targets.pawLR = 20 + vx
      targets.pawRR = -20 + vx
    }

    // ---- active gestures
    const alive: ActionState[] = []
    for (const action of this.actions) {
      const p = (t - action.start) / action.duration
      if (p >= 1) {
        if (action.name === 'bye') this.burst('puff', 10)
        continue
      }
      alive.push(action)
      const result = ACTIONS[action.name](clamp(p, 0, 1), action, this)
      if (result.targets) {
        const touchesEyes = EYE_GLYPHS.some((g) => result.targets?.[g] !== undefined)
        const touchesMouth = MOUTHS.some((m) => result.targets?.[m] !== undefined)
        if (touchesEyes) for (const g of EYE_GLYPHS) targets[g] = 0
        if (touchesMouth) for (const m of MOUTHS) targets[m] = 0
        Object.assign(targets, result.targets)
      }
      if (result.add) {
        for (const key of Object.keys(result.add) as AddChannel[]) {
          add[key] += result.add[key] ?? 0
        }
      }
    }
    this.actions = alive

    // ---- talking mouth (quips): flap between open and closed shapes
    if (this.talking && motion) {
      const flap = 0.5 + 0.5 * Math.sin(t * 17) * Math.sin(t * 5.3 + 1)
      for (const m of MOUTHS) targets[m] = 0
      targets.mGrin = 1
      add.mouthOpen += flap * 0.6 - 0.35
    }

    // ---- integrate springs
    for (const name of CHANNELS) {
      const spring = this.springs[name]
      spring.target = targets[name]
      if (motion) spring.step(dt)
      else spring.snap(targets[name])
    }
    this.stepParticles(dt)

    const v = (name: Channel): number => this.springs[name].value

    // Glyph weights are normalised so a cross-fade never doubles the eyes.
    const eyeSum = Math.max(1e-3, v('gOpen') + v('gHappy') + v('gClosed') + v('gHeart'))
    const mouthSum = Math.max(1e-3, MOUTHS.reduce((sum, m) => sum + Math.max(0, v(m)), 0))

    const pupilX = clamp(v('pupilX') + add.pupilX, -1.2, 1.2)
    const pupilY = clamp(v('pupilY') + add.pupilY, -1.2, 1.2)
    const bodyRot = v('bodyRot') + add.bodyRot
    const bodyY = v('bodyY') + add.bodyY
    const lift = Math.max(0, -bodyY)
    const scale = clamp(v('scale') + add.scale, 0, 1.4)

    const frame: RigFrame = {
      ...(Object.fromEntries(CHANNELS.map((name) => [name, v(name)])) as Targets),
      bodyX: add.bodyX,
      bodyY,
      bodySX: v('bodySX') + add.bodySX,
      bodySY: v('bodySY') + add.bodySY,
      bodyRot,
      faceX: pupilX * 3.4 + add.faceX,
      faceY: pupilY * 2.4 + add.faceY,
      capY: v('capY') + add.capY,
      capRot: v('capRot') + add.capRot + pupilX * 2.2,
      capX: v('capX') + pupilX * 1.6,
      pupilX,
      pupilY,
      eyeOpen: clamp(v('eyeOpen') * (1 - clamp(add.eyeClose, 0, 1)), 0, 1),
      gOpen: Math.max(0, v('gOpen')) / eyeSum,
      gHappy: Math.max(0, v('gHappy')) / eyeSum,
      gClosed: Math.max(0, v('gClosed')) / eyeSum,
      gHeart: Math.max(0, v('gHeart')) / eyeSum,
      mSmile: Math.max(0, v('mSmile')) / mouthSum,
      mGrin: Math.max(0, v('mGrin')) / mouthSum,
      mO: Math.max(0, v('mO')) / mouthSum,
      mFlat: Math.max(0, v('mFlat')) / mouthSum,
      mWavy: Math.max(0, v('mWavy')) / mouthSum,
      mFrown: Math.max(0, v('mFrown')) / mouthSum,
      mCat: Math.max(0, v('mCat')) / mouthSum,
      mTongue: Math.max(0, v('mTongue')) / mouthSum,
      mouthOpen: clamp(v('mouthOpen') + add.mouthOpen, 0.15, 2.2),
      pawLX: v('pawLX') + add.pawLX,
      pawLY: v('pawLY') + add.pawLY,
      pawLR: v('pawLR') + add.pawLR,
      pawRX: v('pawRX') + add.pawRX,
      pawRY: v('pawRY') + add.pawRY,
      pawRR: v('pawRR') + add.pawRR,
      propRot: add.propRot,
      scale,
      alpha: clamp(v('alpha'), 0, 1) * (this.hiding && scale < 0.05 ? 0 : 1),
      shadowScale: clamp((1 - lift / 70) * scale, 0, 1.2),
      shadowAlpha: clamp(0.55 - lift / 90, 0.12, 0.6) * Math.min(1, scale * 1.5),
      accent: ACCENT[spec.accent],
      waveLevel: this.levelSmooth,
      time: t,
      paperProgress,
      lensX,
      lensY,
      particles: this.particles,
    }
    return frame
  }

  private isTalkingMouth(): boolean {
    return this.talking
  }

  private busy(): boolean {
    return this.actions.some((a) => a.name !== 'blink')
  }

  // ------------------------------------------------------------------ particles

  private spawn(kind: ParticleKind, x: number, y: number): void {
    if (this.reducedMotion) return
    if (this.particles.length >= 28) this.particles.shift()
    const r = this.rng
    const base: Particle = {
      id: (this.particleId += 1),
      kind,
      x,
      y,
      vx: 0,
      vy: 0,
      gravity: 0,
      age: 0,
      life: 1.2,
      rot: 0,
      spin: 0,
      size: 1,
      color: '#ffffff',
      wobble: r() * Math.PI * 2,
    }
    switch (kind) {
      case 'z':
        Object.assign(base, { vx: 7, vy: -15, life: 2.6, size: 0.95, color: '#5C74A8' })
        break
      case 'heart':
        Object.assign(base, { vx: (r() - 0.5) * 16, vy: -34, life: 1.3, size: 0.8 + r() * 0.5, color: '#FF6F91' })
        break
      case 'spark':
        Object.assign(base, { vx: 0, vy: -6, life: 0.9, size: 0.6 + r() * 0.7, color: r() < 0.5 ? '#FFD54A' : '#FFFFFF', spin: (r() - 0.5) * 200 })
        break
      case 'confetti': {
        const palette = ['#22C7DC', '#FFB020', '#FF6F91', '#3CCB7F', '#9C8CFF']
        const angle = -Math.PI / 2 + (r() - 0.5) * 2.4
        const speed = 70 + r() * 70
        Object.assign(base, {
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          gravity: 150,
          life: 1.6,
          rot: r() * 360,
          spin: (r() - 0.5) * 720,
          size: 0.8 + r() * 0.6,
          color: palette[Math.floor(r() * palette.length)],
        })
        break
      }
      case 'puff': {
        const angle = r() * Math.PI * 2
        Object.assign(base, {
          vx: Math.cos(angle) * 40,
          vy: Math.sin(angle) * 40 - 10,
          life: 0.8,
          size: 0.8 + r() * 0.8,
          color: '#E8FBFF',
        })
        break
      }
      case 'note':
        Object.assign(base, { vx: (x < 100 ? -1 : 1) * 10, vy: -22, life: 1.6, size: 0.8, color: '#22C7DC' })
        break
      case 'tear':
        Object.assign(base, { vy: 20, gravity: 40, life: 1, size: 0.8, color: '#7FDBFF' })
        break
    }
    this.particles.push(base)
  }

  private burst(kind: ParticleKind, count: number): void {
    for (let i = 0; i < count; i += 1) {
      const angle = this.rng() * Math.PI * 2
      const radius = kind === 'confetti' ? 4 : 58 + this.rng() * 18
      this.spawn(kind, 100 + Math.cos(angle) * radius, 118 + Math.sin(angle) * radius * 0.8)
    }
  }

  private stepParticles(dt: number): void {
    const next: Particle[] = []
    for (const p of this.particles) {
      p.age += dt
      if (p.age >= p.life) continue
      p.vy += p.gravity * dt
      p.x += p.vx * dt + (p.kind === 'z' || p.kind === 'heart' || p.kind === 'note' ? Math.sin(p.age * 4 + p.wobble) * 0.35 : 0)
      p.y += p.vy * dt
      p.rot += p.spin * dt
      next.push(p)
    }
    this.particles = next
  }
}

/** Opacity curve shared by all particles: pop in, hold, fade out. */
export function particleAlpha(p: Particle): number {
  const k = p.age / p.life
  return clamp(k < 0.15 ? k / 0.15 : 1 - phase(k, 0.6, 1), 0, 1)
}

/** Scale curve: Zzz grow as they float, sparks pop, puffs expand. */
export function particleScale(p: Particle): number {
  const k = p.age / p.life
  switch (p.kind) {
    case 'z':
      return p.size * (0.6 + k * 0.9)
    case 'spark':
      return p.size * bump(k) * 1.4
    case 'puff':
      return p.size * (0.6 + k * 1.2)
    default:
      return p.size * (k < 0.2 ? easeOut(k / 0.2) : 1)
  }
}
