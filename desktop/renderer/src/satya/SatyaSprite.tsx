/**
 * SatyaSprite — draws Satya as layered SVG and animates him from `SatyaEngine` frames.
 *
 * The SVG tree is rendered once by React. A single requestAnimationFrame loop then writes
 * transforms/opacities straight onto the nodes (no React re-render per frame), and only when a
 * value actually changed, so the always-on-top window stays cheap.
 */

import { forwardRef, useEffect, useId, useImperativeHandle, useMemo, useRef } from 'react'

import {
  ACCENT,
  particleAlpha,
  particleScale,
  SatyaEngine,
  type Emote,
  type Look,
  type ParticleKind,
  type RigFrame,
  type SatyaPose,
} from './engine'

export interface SatyaSpriteProps {
  pose: SatyaPose
  /** Rendered size in CSS pixels (square). */
  size?: number
  look?: Look
  /** 0..1 call-audio loudness (local only). */
  level?: number
  talking?: boolean
  dragging?: boolean
  dragVelocity?: { x: number; y: number }
  reducedMotion?: boolean
  seed?: number
  className?: string
}

export interface SatyaHandle {
  play: (emote: Emote) => void
  pet: () => void
}

const INK = '#13303A'
const MOUTH_INK = '#3A1218'
const LID = '#3FCFE3'
const POOL = 28

const PARTICLE_PATH: Record<ParticleKind, string> = {
  z: 'M-4 -4 H4 L-4 4 H4',
  heart: 'M0 4.5 C-6.5 -0.5 -7.5 -5 -4.2 -7.2 C-2.2 -8.6 0 -7.2 0 -5.2 C0 -7.2 2.2 -8.6 4.2 -7.2 C7.5 -5 6.5 -0.5 0 4.5 Z',
  spark: 'M0 -6 L1.5 -1.5 L6 0 L1.5 1.5 L0 6 L-1.5 1.5 L-6 0 L-1.5 -1.5 Z',
  confetti: 'M-2.6 -1.5 H2.6 V1.5 H-2.6 Z',
  puff: 'M-5 0 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0 Z',
  note: 'M-2.6 3 a2.6 2.1 -20 1 0 5.2 0 a2.6 2.1 -20 1 0 -5.2 0 Z M2.4 3 V-6 L6 -4.5',
  tear: 'M0 -5 C3 -1 4 2 4 3.5 a4 4 0 0 1 -8 0 C-4 2 -3 -1 0 -5 Z',
}

const STROKED: Partial<Record<ParticleKind, true>> = { z: true, note: true }

function n(value: number): string {
  return (Math.round(value * 100) / 100).toString()
}

/** Writes attributes only when they changed since the last frame. */
class Writer {
  private cache = new WeakMap<Element, Map<string, string>>()

  set(el: Element | null | undefined, attr: string, value: string): void {
    if (!el) return
    let map = this.cache.get(el)
    if (!map) {
      map = new Map()
      this.cache.set(el, map)
    }
    if (map.get(attr) === value) return
    map.set(attr, value)
    el.setAttribute(attr, value)
  }

  opacity(el: Element | null | undefined, value: number): void {
    const v = value < 0.01 ? 0 : value > 0.99 ? 1 : value
    this.set(el, 'opacity', n(v))
    this.set(el, 'visibility', v === 0 ? 'hidden' : 'visible')
  }
}

type NodeKey =
  | 'root'
  | 'shadow'
  | 'auraGlow'
  | 'auraRing'
  | 'auraStop0'
  | 'auraStop1'
  | 'wavesL'
  | 'wavesR'
  | 'wave0'
  | 'wave1'
  | 'wave2'
  | 'wave3'
  | 'body'
  | 'face'
  | 'cheekL'
  | 'cheekR'
  | 'eyeL'
  | 'eyeR'
  | 'openL'
  | 'openR'
  | 'irisL'
  | 'irisR'
  | 'glintL'
  | 'glintR'
  | 'lidL'
  | 'lidR'
  | 'lowL'
  | 'lowR'
  | 'happyL'
  | 'happyR'
  | 'closedL'
  | 'closedR'
  | 'heartL'
  | 'heartR'
  | 'browL'
  | 'browR'
  | 'mouth'
  | 'mSmile'
  | 'mGrin'
  | 'mGrinInner'
  | 'mO'
  | 'mFlat'
  | 'mWavy'
  | 'mFrown'
  | 'mCat'
  | 'mTongue'
  | 'glasses'
  | 'cap'
  | 'emblem'
  | 'headphones'
  | 'ledL'
  | 'ledR'
  | 'sweat'
  | 'shield'
  | 'shieldFill'
  | 'paper'
  | 'line0'
  | 'line1'
  | 'line2'
  | 'pawL'
  | 'pawR'
  | 'phone'
  | 'stop'
  | 'magnifier'
  | 'quill'
  | 'dots'
  | 'dot0'
  | 'dot1'
  | 'dot2'
  | 'exclaim'
  | 'exclaimFill'
  | 'question'

const LINE_LENGTH = 44

const SatyaSprite = forwardRef<SatyaHandle, SatyaSpriteProps>(function SatyaSprite(
  {
    pose,
    size = 128,
    look,
    level = 0,
    talking = false,
    dragging = false,
    dragVelocity,
    reducedMotion = false,
    seed = 7,
    className,
  },
  ref,
) {
  const rawId = useId()
  const uid = useMemo(() => `s${rawId.replace(/[^a-zA-Z0-9]/g, '')}`, [rawId])
  const engine = useMemo(() => new SatyaEngine({ seed, pose, reducedMotion }), []) // eslint-disable-line react-hooks/exhaustive-deps
  const nodes = useRef<Partial<Record<NodeKey, SVGElement | null>>>({})
  const particleNodes = useRef<Array<{ g: SVGGElement | null; path: SVGPathElement | null }>>(
    Array.from({ length: POOL }, () => ({ g: null, path: null })),
  )

  useImperativeHandle(ref, () => ({
    play: (emote: Emote) => engine.play(emote),
    pet: () => engine.pet(),
  }))

  useEffect(() => engine.setPose(pose), [engine, pose])
  useEffect(() => engine.setLevel(level), [engine, level])
  useEffect(() => engine.setTalking(talking), [engine, talking])
  useEffect(() => engine.setReducedMotion(reducedMotion), [engine, reducedMotion])
  useEffect(() => {
    if (look) engine.setLook(look)
  }, [engine, look])
  useEffect(() => {
    engine.setDrag(dragging, dragVelocity?.x ?? 0, dragVelocity?.y ?? 0)
  }, [engine, dragging, dragVelocity?.x, dragVelocity?.y])

  useEffect(() => {
    const writer = new Writer()
    const slotOf = new Map<number, number>()
    const slotKind: Array<ParticleKind | null> = Array.from({ length: POOL }, () => null)
    let raf = 0
    let last = performance.now()
    let accumulated = 0

    const apply = (f: RigFrame): void => {
      const N = nodes.current
      const w = writer

      w.set(N.root, 'transform', `translate(100 186) scale(${n(f.scale)}) translate(-100 -186)`)
      w.opacity(N.root, f.alpha)
      w.set(N.shadow, 'transform', `translate(${n(100 + f.bodyX)} 187) scale(${n(f.shadowScale)} ${n(f.shadowScale)}) translate(-100 -187)`)
      w.opacity(N.shadow, f.shadowAlpha)

      // Aura: soft glow + a slow breathing ring in the state's accent colour.
      const pulse = 0.65 + 0.35 * Math.sin(f.time * 3)
      w.set(N.auraStop0, 'stop-color', f.accent)
      w.set(N.auraStop1, 'stop-color', f.accent)
      w.set(N.auraRing, 'stroke', f.accent)
      w.opacity(N.auraGlow, f.aura * 0.9)
      w.opacity(N.auraRing, f.aura * 0.55 * pulse)
      w.set(N.auraRing, 'transform', `translate(100 124) scale(${n(1 + (1 - pulse) * 0.04)}) translate(-100 -124)`)

      // Sound waves beside the headphones follow the call loudness.
      const waves = f.pWaves
      for (let i = 0; i < 4; i += 1) {
        const node = N[`wave${i}` as NodeKey]
        const beat = 0.5 + 0.5 * Math.sin(f.time * 7 - (i % 2) * 1.4)
        w.opacity(node, waves * (0.18 + f.waveLevel * 0.8) * (0.55 + 0.45 * beat))
      }
      const ws = 1 + f.waveLevel * 0.28
      w.set(N.wavesL, 'transform', `translate(${n(f.bodyX + 40)} ${n(f.bodyY + 118)}) scale(${n(ws)}) translate(-40 -118)`)
      w.set(N.wavesR, 'transform', `translate(${n(f.bodyX + 160)} ${n(f.bodyY + 118)}) scale(${n(ws)}) translate(-160 -118)`)

      // Body: squash/stretch and tilt around the feet.
      w.set(
        N.body,
        'transform',
        `translate(${n(f.bodyX)} ${n(f.bodyY)}) translate(100 184) rotate(${n(f.bodyRot)}) scale(${n(f.bodySX)} ${n(f.bodySY)}) translate(-100 -184)`,
      )
      w.set(N.face, 'transform', `translate(${n(f.faceX)} ${n(f.faceY)})`)
      w.opacity(N.cheekL, f.cheek * 0.6)
      w.opacity(N.cheekR, f.cheek * 0.6)

      // Eyes: the realistic eye (lids, iris, catchlights) cross-fades with ^ ^ / closed / heart.
      const closed = 1 - f.eyeOpen
      const lidY = -16.5 + closed * 33
      const lowY = 33 - f.lowerLid * 17
      for (const side of ['L', 'R'] as const) {
        const cx = side === 'L' ? 77 : 123
        w.set(N[`eye${side}`], 'transform', `translate(${cx} 130) scale(${n(f.eyeScale)})`)
        w.opacity(N[`open${side}`], f.gOpen)
        w.set(N[`iris${side}`], 'transform', `translate(${n(f.pupilX * 4.6)} ${n(f.pupilY * 4.2)})`)
        w.set(N[`glint${side}`], 'transform', `translate(${n(f.pupilX * 2.2)} ${n(f.pupilY * 2)})`)
        w.set(N[`lid${side}`], 'transform', `translate(0 ${n(lidY)})`)
        w.set(N[`low${side}`], 'transform', `translate(0 ${n(lowY)})`)
        w.opacity(N[`happy${side}`], f.gHappy)
        w.opacity(N[`closed${side}`], f.gClosed)
        w.opacity(N[`heart${side}`], f.gHeart)
      }
      w.set(N.browL, 'transform', `translate(77 ${n(111 + f.browY)}) rotate(${n(f.browTilt)})`)
      w.set(N.browR, 'transform', `translate(123 ${n(111 + f.browY)}) rotate(${n(-f.browTilt)})`)
      w.opacity(N.browL, f.browOp)
      w.opacity(N.browR, f.browOp)

      // Mouth shapes cross-fade; open shapes scale with mouthOpen.
      w.set(N.mouth, 'transform', `translate(100 155)`)
      w.opacity(N.mSmile, f.mSmile)
      w.opacity(N.mGrin, f.mGrin)
      w.set(N.mGrinInner, 'transform', `translate(0 -3) scale(1 ${n(0.55 + f.mouthOpen * 0.45)}) translate(0 3)`)
      w.opacity(N.mO, f.mO)
      w.set(N.mO, 'transform', `scale(${n(0.75 + f.mouthOpen * 0.25)} ${n(f.mouthOpen)})`)
      w.opacity(N.mFlat, f.mFlat)
      w.opacity(N.mWavy, f.mWavy)
      w.opacity(N.mFrown, f.mFrown)
      w.opacity(N.mCat, f.mCat)
      w.opacity(N.mTongue, f.mTongue)

      w.opacity(N.glasses, f.pGlasses)
      w.set(N.glasses, 'transform', `translate(100 130) scale(${n(0.7 + 0.3 * Math.min(1, f.pGlasses))}) translate(-100 -130)`)

      // Cap: follows the gaze a little (parallax) and pops off when startled.
      w.set(N.cap, 'transform', `translate(${n(f.capX + f.faceX * 0.45)} ${n(f.capY)}) rotate(${n(f.capRot)} 100 92)`)
      w.opacity(N.emblem, 0.55 + f.emblem * 0.45)

      const hp = Math.min(1.1, f.pHeadphones)
      w.opacity(N.headphones, Math.min(1, f.pHeadphones * 1.4))
      w.set(N.headphones, 'transform', `translate(${n(f.faceX * 0.45)} ${n((1 - hp) * -14)}) translate(100 96) scale(${n(0.8 + 0.2 * hp)}) translate(-100 -96)`)
      w.opacity(N.ledL, 0.35 + f.waveLevel * 0.65)
      w.opacity(N.ledR, 0.35 + f.waveLevel * 0.65)

      const sweatY = ((f.time * 14) % 16) - 2
      w.opacity(N.sweat, f.pSweat * (1 - Math.max(0, sweatY - 9) / 7))
      w.set(N.sweat, 'transform', `translate(152 ${n(92 + sweatY)})`)

      w.opacity(N.shield, Math.min(1, f.pShield * 1.3))
      w.set(N.shield, 'transform', `translate(${n(f.pawRX + 14)} ${n(f.pawRY - 10)}) rotate(${n(8 + f.pawRR * 0.5)}) scale(${n(0.72 * Math.max(0.001, f.pShield))}) translate(-100 -162)`)
      w.set(N.shieldFill, 'fill', f.accent === ACCENT.hold ? ACCENT.hold : ACCENT.verify)

      w.opacity(N.paper, f.pPaper)
      const cycle = f.paperProgress % 3.6
      for (let i = 0; i < 3; i += 1) {
        const k = Math.max(0, Math.min(1, cycle - i))
        w.set(N[`line${i}` as NodeKey], 'stroke-dashoffset', n(LINE_LENGTH * (1 - k)))
      }

      w.set(N.pawL, 'transform', `translate(${n(f.pawLX)} ${n(f.pawLY)}) rotate(${n(f.pawLR)})`)
      w.set(N.pawR, 'transform', `translate(${n(f.pawRX)} ${n(f.pawRY)}) rotate(${n(f.pawRR)})`)
      w.opacity(N.phone, Math.min(1, f.pPhone * 1.3))
      w.set(N.phone, 'transform', `rotate(${n(f.propRot)}) scale(${n(Math.max(0.001, Math.min(1.1, f.pPhone)))})`)
      w.opacity(N.stop, f.pStop * (0.6 + 0.4 * Math.sin(f.time * 6)))
      w.opacity(N.magnifier, Math.min(1, f.pMagnifier * 1.3))
      w.set(N.magnifier, 'transform', `scale(${n(Math.max(0.001, Math.min(1.1, f.pMagnifier)))})`)
      w.opacity(N.quill, Math.min(1, f.pQuill * 1.3))
      w.set(N.quill, 'transform', `scale(${n(Math.max(0.001, Math.min(1.1, f.pQuill)))})`)

      // Floating marks follow the body so they stay above his head while he hops.
      const head = `translate(${n(f.bodyX)} ${n(f.bodyY * 0.9 + Math.min(0, f.capY) * 0.5)})`
      w.opacity(N.dots, f.pDots)
      w.set(N.dots, 'transform', head)
      for (let i = 0; i < 3; i += 1) {
        const beat = 0.35 + 0.65 * Math.max(0, Math.sin(f.time * 4 - i * 0.9))
        w.opacity(N[`dot${i}` as NodeKey], beat)
      }
      const ex = Math.max(0.001, Math.min(1.2, f.pExclaim))
      w.opacity(N.exclaim, Math.min(1, f.pExclaim * 1.4))
      w.set(N.exclaim, 'transform', `${head} translate(100 30) scale(${n(ex)}) rotate(${n(Math.sin(f.time * 9) * 6)}) translate(-100 -30)`)
      w.set(N.exclaimFill, 'fill', f.accent === ACCENT.hold ? ACCENT.hold : ACCENT.verify)
      const q = Math.max(0.001, Math.min(1.2, f.pQuestion))
      w.opacity(N.question, Math.min(1, f.pQuestion * 1.4))
      w.set(N.question, 'transform', `${head} translate(146 46) scale(${n(q)}) rotate(${n(12 + Math.sin(f.time * 5) * 6)})`)

      // Particles: a fixed pool of <path>s; each new particle claims a free slot.
      const liveIds = new Set<number>()
      for (const p of f.particles) {
        liveIds.add(p.id)
        let slot = slotOf.get(p.id)
        if (slot === undefined) {
          slot = slotKind.findIndex((kind, index) => kind === null && ![...slotOf.values()].includes(index))
          if (slot === -1) continue
          slotOf.set(p.id, slot)
          slotKind[slot] = p.kind
          const node = particleNodes.current[slot]
          w.set(node.path, 'd', PARTICLE_PATH[p.kind])
          if (STROKED[p.kind]) {
            w.set(node.path, 'fill', p.kind === 'note' ? p.color : 'none')
            w.set(node.path, 'stroke', p.color)
            w.set(node.path, 'stroke-width', p.kind === 'z' ? '2.8' : '2.2')
          } else {
            w.set(node.path, 'fill', p.color)
            w.set(node.path, 'stroke', p.kind === 'puff' ? 'none' : 'rgba(255,255,255,0.9)')
            w.set(node.path, 'stroke-width', p.kind === 'heart' ? '1.2' : '0')
          }
        }
        const node = particleNodes.current[slot]
        w.set(node.g, 'transform', `translate(${n(p.x)} ${n(p.y)}) rotate(${n(p.rot)}) scale(${n(particleScale(p))})`)
        w.opacity(node.g, particleAlpha(p) * (p.kind === 'puff' ? 0.8 : 1))
      }
      for (const [id, slot] of [...slotOf.entries()]) {
        if (!liveIds.has(id)) {
          slotOf.delete(id)
          slotKind[slot] = null
          w.opacity(particleNodes.current[slot].g, 0)
        }
      }
    }

    const loop = (now: number): void => {
      const dt = (now - last) / 1000
      last = now
      accumulated += dt
      // Sleeping Satya only needs ~30 fps; everything else gets every frame.
      const minStep = engine.pose === 'sleep' ? 1 / 31 : 0
      if (accumulated >= minStep) {
        apply(engine.tick(accumulated))
        accumulated = 0
      }
      raf = requestAnimationFrame(loop)
    }
    apply(engine.tick(1 / 60))
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [engine])

  const bind =
    (key: NodeKey) =>
    (el: SVGElement | null): void => {
      nodes.current[key] = el
    }
  const id = (name: string): string => `${uid}-${name}`
  const url = (name: string): string => `url(#${id(name)})`

  return (
    <svg
      viewBox="0 0 200 200"
      width={size}
      height={size}
      className={className}
      style={{ overflow: 'visible', display: 'block' }}
      role="img"
      aria-label={`Satya is ${pose}`}
    >
      <defs>
        <radialGradient id={id('body')} cx="0.36" cy="0.32" r="0.78">
          <stop offset="0" stopColor="#B4F8FC" />
          <stop offset="0.42" stopColor="#4FD9EA" />
          <stop offset="0.8" stopColor="#21B3CC" />
          <stop offset="1" stopColor="#1393AE" />
        </radialGradient>
        <radialGradient id={id('paw')} cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#B9F9FD" />
          <stop offset="0.55" stopColor="#4CD6E8" />
          <stop offset="1" stopColor="#1A9FBA" />
        </radialGradient>
        <linearGradient id={id('cap')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3A4256" />
          <stop offset="1" stopColor="#11151F" />
        </linearGradient>
        <linearGradient id={id('brim')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#262C3B" />
          <stop offset="1" stopColor="#07090E" />
        </linearGradient>
        <radialGradient id={id('iris')} cx="0.45" cy="0.4" r="0.6">
          <stop offset="0" stopColor="#9A5A2C" />
          <stop offset="0.6" stopColor="#4E2611" />
          <stop offset="1" stopColor="#1D0C04" />
        </radialGradient>
        <radialGradient id={id('aura')} cx="0.5" cy="0.5" r="0.5">
          <stop ref={bind('auraStop0')} offset="0.55" stopColor={ACCENT.watch} stopOpacity="0.28" />
          <stop ref={bind('auraStop1')} offset="1" stopColor={ACCENT.watch} stopOpacity="0" />
        </radialGradient>
        <clipPath id={id('eye')} clipPathUnits="userSpaceOnUse">
          <ellipse cx="0" cy="0" rx="13.6" ry="16.2" />
        </clipPath>
        <clipPath id={id('bodyClip')} clipPathUnits="userSpaceOnUse">
          <path d="M100 68 C140 68 166 98 166 136 C166 166 142 184 100 184 C58 184 34 166 34 136 C34 98 60 68 100 68 Z" />
        </clipPath>
        <clipPath id={id('grin')} clipPathUnits="userSpaceOnUse">
          <path d="M-11 -3 Q0 -1.2 11 -3 Q9.5 11 0 12 Q-9.5 11 -11 -3 Z" />
        </clipPath>
      </defs>

      <g ref={bind('root')}>
        <ellipse ref={bind('shadow')} cx="100" cy="187" rx="44" ry="6" fill="#0B2230" opacity="0.3" />
        <circle ref={bind('auraGlow')} cx="100" cy="124" r="92" fill={url('aura')} opacity="0" />
        <circle ref={bind('auraRing')} cx="100" cy="124" r="80" fill="none" stroke={ACCENT.watch} strokeWidth="2.5" opacity="0" />

        <g ref={bind('wavesL')} fill="none" stroke={ACCENT.watch} strokeLinecap="round">
          <path ref={bind('wave0')} d="M27 100 Q17 118 27 136" strokeWidth="3.2" opacity="0" />
          <path ref={bind('wave1')} d="M17 91 Q2 118 17 145" strokeWidth="2.6" opacity="0" />
        </g>
        <g ref={bind('wavesR')} fill="none" stroke={ACCENT.watch} strokeLinecap="round">
          <path ref={bind('wave2')} d="M173 100 Q183 118 173 136" strokeWidth="3.2" opacity="0" />
          <path ref={bind('wave3')} d="M183 91 Q198 118 183 145" strokeWidth="2.6" opacity="0" />
        </g>

        <g ref={bind('body')}>
          {/* jelly body */}
          <path
            d="M100 68 C140 68 166 98 166 136 C166 166 142 184 100 184 C58 184 34 166 34 136 C34 98 60 68 100 68 Z"
            fill={url('body')}
            stroke="#0E7C93"
            strokeWidth="2.2"
          />
          <g clipPath={url('bodyClip')}>
            <ellipse cx="100" cy="182" rx="58" ry="16" fill="#0A6A82" opacity="0.28" />
            <ellipse cx="150" cy="150" rx="12" ry="30" fill="#0A6A82" opacity="0.12" />
            <ellipse cx="100" cy="158" rx="38" ry="20" fill="#E9FDFF" opacity="0.13" />
          </g>
          <ellipse cx="51" cy="124" rx="6.5" ry="13" transform="rotate(18 51 124)" fill="#FFFFFF" opacity="0.32" />
          <circle cx="50" cy="143" r="2.6" fill="#FFFFFF" opacity="0.55" />
          <path d="M150 160 Q158 148 159 134" fill="none" stroke="#E9FDFF" strokeWidth="2" strokeLinecap="round" opacity="0.25" />

          {/* face (parallax with the gaze) */}
          <g ref={bind('face')}>
            <ellipse ref={bind('cheekL')} cx="59" cy="150" rx="9.5" ry="5.5" fill="#FF7A93" opacity="0.3" />
            <ellipse ref={bind('cheekR')} cx="141" cy="150" rx="9.5" ry="5.5" fill="#FF7A93" opacity="0.3" />

            {(['L', 'R'] as const).map((side) => (
              <g key={side} ref={bind(`eye${side}`)} transform={`translate(${side === 'L' ? 77 : 123} 130)`}>
                <g ref={bind(`open${side}`)}>
                  <ellipse rx="13.6" ry="16.2" fill="#FFFFFF" stroke="#0E5E70" strokeWidth="1.4" />
                  <g clipPath={url('eye')}>
                    <g ref={bind(`iris${side}`)}>
                      <circle cy="1.5" r="10.4" fill={url('iris')} />
                      <circle cy="1.5" r="5" fill="#140803" />
                    </g>
                    <g ref={bind(`glint${side}`)}>
                      <circle cx="3.8" cy="-3.6" r="3.9" fill="#FFFFFF" />
                      <circle cx="-3.8" cy="5" r="1.8" fill="#FFFFFF" opacity="0.9" />
                    </g>
                    <g ref={bind(`low${side}`)} transform="translate(0 33)">
                      <path d="M-17 1 Q0 -5 17 1 V30 H-17 Z" fill={LID} />
                    </g>
                    <g ref={bind(`lid${side}`)} transform="translate(0 -16.5)">
                      <path d="M-17 -40 H17 V-1 Q0 5 -17 -1 Z" fill={LID} />
                      <path d="M-15 -1.2 Q0 4.6 15 -1.2" fill="none" stroke={INK} strokeWidth="2.6" strokeLinecap="round" />
                    </g>
                  </g>
                </g>
                <path ref={bind(`happy${side}`)} d="M-10.5 4 Q0 -9 10.5 4" fill="none" stroke={INK} strokeWidth="3.6" strokeLinecap="round" opacity="0" />
                <g ref={bind(`closed${side}`)} opacity="0">
                  <path d="M-10.5 0 Q0 8 10.5 0" fill="none" stroke={INK} strokeWidth="3.4" strokeLinecap="round" />
                  <path d={side === 'L' ? 'M-10.5 0 L-13.5 -2.5' : 'M10.5 0 L13.5 -2.5'} stroke={INK} strokeWidth="2.2" strokeLinecap="round" />
                </g>
                <path
                  ref={bind(`heart${side}`)}
                  d="M0 9 C-11 1 -12 -7 -6.5 -10 C-3 -11.8 0 -9.5 0 -6.5 C0 -9.5 3 -11.8 6.5 -10 C12 -7 11 1 0 9 Z"
                  fill="#FF5C8A"
                  stroke="#FFFFFF"
                  strokeWidth="1.4"
                  opacity="0"
                />
              </g>
            ))}

            <path ref={bind('browL')} d="M-9 2 Q0 -3 9 2" fill="none" stroke="#1B2F38" strokeWidth="3.4" strokeLinecap="round" transform="translate(77 111)" />
            <path ref={bind('browR')} d="M-9 2 Q0 -3 9 2" fill="none" stroke="#1B2F38" strokeWidth="3.4" strokeLinecap="round" transform="translate(123 111)" />

            <g ref={bind('mouth')} transform="translate(100 155)">
              <path ref={bind('mSmile')} d="M-10.5 -2 Q0 8 10.5 -2" fill="none" stroke={MOUTH_INK} strokeWidth="2.8" strokeLinecap="round" />
              <g ref={bind('mGrin')} opacity="0">
                <g ref={bind('mGrinInner')}>
                  <path d="M-11 -3 Q0 -1.2 11 -3 Q9.5 11 0 12 Q-9.5 11 -11 -3 Z" fill="#5A1520" stroke={MOUTH_INK} strokeWidth="1.6" strokeLinejoin="round" />
                  <g clipPath={url('grin')}>
                    <ellipse cx="0" cy="9.5" rx="6.5" ry="4.2" fill="#FF7E8F" />
                  </g>
                </g>
              </g>
              <ellipse ref={bind('mO')} cx="0" cy="1" rx="4.6" ry="5.6" fill="#5A1520" stroke={MOUTH_INK} strokeWidth="1.4" opacity="0" />
              <path ref={bind('mFlat')} d="M-7 1 H7" fill="none" stroke={MOUTH_INK} strokeWidth="2.8" strokeLinecap="round" opacity="0" />
              <path ref={bind('mWavy')} d="M-9 2 Q-4.5 -2.5 0 2 Q4.5 6.5 9 2" fill="none" stroke={MOUTH_INK} strokeWidth="2.6" strokeLinecap="round" opacity="0" />
              <path ref={bind('mFrown')} d="M-8 4 Q0 -3.5 8 4" fill="none" stroke={MOUTH_INK} strokeWidth="2.8" strokeLinecap="round" opacity="0" />
              <path ref={bind('mCat')} d="M-9 -1 Q-4.5 4.5 0 0 Q4.5 4.5 9 -1" fill="none" stroke={MOUTH_INK} strokeWidth="2.6" strokeLinecap="round" opacity="0" />
              <g ref={bind('mTongue')} opacity="0">
                <path d="M-7 -1 Q0 5 7 -1" fill="none" stroke={MOUTH_INK} strokeWidth="2.6" strokeLinecap="round" />
                <path d="M3 1.8 q4.5 0.8 5.2 5.4 q-3.8 2.2 -5.9 -1.6 z" fill="#FF7E8F" stroke={MOUTH_INK} strokeWidth="1.1" />
              </g>
            </g>

            <g ref={bind('glasses')} opacity="0" fill="rgba(255,255,255,0.14)" stroke="#2A2238" strokeWidth="2.6">
              <circle cx="77" cy="130" r="16.5" />
              <circle cx="123" cy="130" r="16.5" />
              <path d="M93.5 128 Q100 124 106.5 128" fill="none" />
              <path d="M60.5 127 L48 122" fill="none" />
              <path d="M139.5 127 L152 122" fill="none" />
            </g>
          </g>

          {/* cap */}
          <g ref={bind('cap')}>
            <ellipse cx="100" cy="109" rx="44" ry="5.5" fill="#0A5266" opacity="0.35" />
            <path d="M53 100 C51 63 73 44 100 44 C127 44 149 63 147 100 Z" fill={url('cap')} stroke="#56627E" strokeWidth="1.8" />
            <path d="M78 49 Q71 72 69 99 M122 49 Q129 72 131 99" fill="none" stroke="#454E64" strokeWidth="1.1" opacity="0.8" />
            <path d="M62 66 Q80 52 100 51" fill="none" stroke="#5A6580" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
            <circle cx="100" cy="44.5" r="3.4" fill="#262C3B" stroke="#0A0D14" strokeWidth="1" />
            <g ref={bind('emblem')} stroke="#45E0EF" strokeLinecap="round" strokeLinejoin="round">
              <path d="M86 72 H80 L76 68 H70 M86 78 H78 L74 82 H68 M114 72 H120 L124 68 H130 M114 78 H122 L126 82 H132" fill="none" strokeWidth="1.2" opacity="0.85" />
              <circle cx="69" cy="68" r="1.5" fill="#45E0EF" stroke="none" />
              <circle cx="67" cy="82" r="1.5" fill="#45E0EF" stroke="none" />
              <circle cx="131" cy="68" r="1.5" fill="#45E0EF" stroke="none" />
              <circle cx="133" cy="82" r="1.5" fill="#45E0EF" stroke="none" />
              <path d="M100 58 L111 62 V71 C111 78 106 83 100 86 C94 83 89 78 89 71 V62 Z" fill="rgba(69,224,239,0.16)" strokeWidth="2" />
              <rect x="95.5" y="70" width="9" height="7.5" rx="1.4" fill="#45E0EF" stroke="none" />
              <path d="M97.4 70 V67.6 a2.6 2.6 0 0 1 5.2 0 V70" fill="none" strokeWidth="1.6" />
            </g>
            <path
              d="M46 98 C62 91 138 91 154 98 C157 103 151 109 141 111 C119 105.5 81 105.5 59 111 C49 109 43 103 46 98 Z"
              fill={url('brim')}
              stroke="#4B5670"
              strokeWidth="1.6"
            />
            <path d="M52 98.5 C66 93.5 134 93.5 148 98.5" fill="none" stroke="#3B4458" strokeWidth="1.2" opacity="0.7" />
          </g>

          {/* headphones (listening) */}
          <g ref={bind('headphones')} opacity="0">
            <path d="M40 110 C30 8 170 8 160 110" fill="none" stroke="#56627E" strokeWidth="9" strokeLinecap="round" />
            <path d="M40 110 C30 8 170 8 160 110" fill="none" stroke="#222A38" strokeWidth="6.5" strokeLinecap="round" />
            <path d="M42.5 104 C34 16 166 16 157.5 104" fill="none" stroke="#3A4558" strokeWidth="2" strokeLinecap="round" />
            <rect x="31" y="100" width="17" height="32" rx="8.5" fill="#222A38" stroke="#0E131B" strokeWidth="1.4" />
            <rect x="152" y="100" width="17" height="32" rx="8.5" fill="#222A38" stroke="#0E131B" strokeWidth="1.4" />
            <circle ref={bind('ledL')} cx="39.5" cy="116" r="2.8" fill={ACCENT.watch} />
            <circle ref={bind('ledR')} cx="160.5" cy="116" r="2.8" fill={ACCENT.watch} />
          </g>

          <path ref={bind('sweat')} d="M0 -7 C4 -1 6 3 6 6 a6 6 0 0 1 -12 0 C-6 3 -4 -1 0 -7 Z" fill="#9BE8FF" stroke="#3FA9D0" strokeWidth="1.2" opacity="0" />

          {/* paper for the Scribe */}
          <g ref={bind('paper')} opacity="0" transform="rotate(-4 100 180)">
            <rect x="72" y="166" width="58" height="24" rx="3" fill="#FFFDF6" stroke="#D8D2C4" strokeWidth="1.2" />
            {[0, 1, 2].map((i) => (
              <path
                key={i}
                ref={bind(`line${i}` as NodeKey)}
                d={`M78 ${172 + i * 6} H${78 + LINE_LENGTH}`}
                stroke="#7A6FD6"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeDasharray={`${LINE_LENGTH} ${LINE_LENGTH}`}
                strokeDashoffset={LINE_LENGTH}
              />
            ))}
          </g>

          {/* shield: "pause before you pay" */}
          <g ref={bind('shield')} opacity="0">
            <path
              ref={bind('shieldFill')}
              d="M100 137 L123 144 V161 C123 175 113 184 100 189 C87 184 77 175 77 161 V144 Z"
              fill={ACCENT.verify}
              stroke="#FFFFFF"
              strokeWidth="2.6"
              strokeLinejoin="round"
            />
            <path d="M100 141 L119 147 V161 C119 172 111 180 100 184" fill="none" stroke="#FFFFFF" strokeWidth="1.4" opacity="0.35" />
            <rect x="93" y="154" width="5" height="15" rx="2.2" fill="#FFFFFF" />
            <rect x="102" y="154" width="5" height="15" rx="2.2" fill="#FFFFFF" />
          </g>

          {/* paws, with the props they hold */}
          <g ref={bind('pawL')} transform={`translate(80 174)`}>
            <g ref={bind('phone')} opacity="0">
              <rect x="-8" y="-32" width="15" height="27" rx="3.6" fill="#263040" stroke="#0E131B" strokeWidth="1.4" />
              <rect x="-6" y="-29" width="11" height="19" rx="1.8" fill={ACCENT.watch} opacity="0.92" />
              <path d="M-13 -26 l-4 -2.5 M-13.5 -18.5 h-5 M-13 -11 l-4 2.5" stroke={ACCENT.verify} strokeWidth="2" strokeLinecap="round" />
            </g>
            <g ref={bind('stop')} opacity="0" stroke={ACCENT.hold} strokeWidth="2.4" strokeLinecap="round">
              <path d="M-16 -8 l-6 -3 M-17 2 h-7 M-15 11 l-6 3 M-4 -16 l-2 -6 M6 -15 l3 -5" />
            </g>
            <circle r="10.5" fill={url('paw')} stroke="#0E7C93" strokeWidth="1.8" />
            <circle cx="-3.5" cy="-3.5" r="2.4" fill="#FFFFFF" opacity="0.45" />
          </g>
          <g ref={bind('pawR')} transform={`translate(120 174)`}>
            <g ref={bind('magnifier')} opacity="0">
              <path d="M-5 -6 L3 4" stroke="#6B4A2E" strokeWidth="5.5" strokeLinecap="round" />
              <circle cx="-15" cy="-19" r="14" fill="rgba(214,248,255,0.35)" stroke="#2C3444" strokeWidth="3.6" />
              <path d="M-21 -22 Q-19 -27 -13 -27.5" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" opacity="0.85" />
            </g>
            <g ref={bind('quill')} opacity="0">
              <path d="M-1 9 C2 -6 9 -21 18 -33 C11 -19 6 -6 -1 9 Z" fill="#B9AEFF" stroke="#6A5BD6" strokeWidth="1.3" />
              <path d="M18 -33 C21 -24 15 -12 4 -2" fill="#D6CFFF" stroke="#6A5BD6" strokeWidth="1.1" />
              <path d="M-1 9 L-3 13" stroke="#2A2238" strokeWidth="2.2" strokeLinecap="round" />
            </g>
            <circle r="10.5" fill={url('paw')} stroke="#0E7C93" strokeWidth="1.8" />
            <circle cx="-3.5" cy="-3.5" r="2.4" fill="#FFFFFF" opacity="0.45" />
          </g>
        </g>

        {/* thought dots, ! and ? float above his head */}
        <g ref={bind('dots')} opacity="0" fill="#FFFFFF" stroke="#8FA6B8" strokeWidth="1.4">
          <circle ref={bind('dot0')} cx="140" cy="54" r="3.2" />
          <circle ref={bind('dot1')} cx="152" cy="42" r="4.4" />
          <circle ref={bind('dot2')} cx="166" cy="30" r="5.8" />
        </g>
        <g ref={bind('exclaim')} opacity="0">
          <rect ref={bind('exclaimFill')} x="95" y="6" width="10" height="21" rx="5" fill={ACCENT.verify} stroke="#FFFFFF" strokeWidth="2.4" />
          <circle cx="100" cy="35" r="5.2" fill="#FFFFFF" />
          <circle cx="100" cy="35" r="3.6" fill={ACCENT.verify} />
        </g>
        <g ref={bind('question')} opacity="0">
          <path d="M-5.5 -7 C-5.5 -14 5.5 -14 5.5 -7 C5.5 -2.5 0 -1.5 0 4" fill="none" stroke="#FFFFFF" strokeWidth="6.5" strokeLinecap="round" />
          <path d="M-5.5 -7 C-5.5 -14 5.5 -14 5.5 -7 C5.5 -2.5 0 -1.5 0 4" fill="none" stroke={ACCENT.watch} strokeWidth="3.6" strokeLinecap="round" />
          <circle cy="11" r="2.8" fill={ACCENT.watch} stroke="#FFFFFF" strokeWidth="1.4" />
        </g>

        <g>
          {particleNodes.current.map((_, index) => (
            <g
              key={index}
              ref={(el) => {
                particleNodes.current[index].g = el
              }}
              opacity="0"
              visibility="hidden"
            >
              <path
                ref={(el) => {
                  particleNodes.current[index].path = el
                }}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
          ))}
        </g>
      </g>
    </svg>
  )
})

export default SatyaSprite
