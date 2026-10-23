import { memo, useMemo } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import type { TargetAndTransition, Transition } from 'framer-motion'

import type { MascotMood, Pose } from '../../../shared/contracts'
import { color, motion as springTokens, size as sizePx } from '../shared/tokens'
import { Accessories } from './accessories'
import { POSES } from './poses'
import { BLINK_MS, useBlink } from './useBlink'

export type MascotSize = keyof typeof sizePx

export interface MascotProps {
  pose?: Pose
  mood?: MascotMood | string
  alert?: boolean
  audioLevel?: number
  look?: { dx: number; dy: number; near: boolean }
  size?: number | MascotSize
  reducedMotion?: boolean
}

const MOOD_TO_POSE: Record<string, Pose> = {
  sleepy: 'sleep',
  attentive: 'idle',
  focused: 'think',
  calm_alert: 'alert',
  writing: 'write',
  off: 'off',
}

const EAR_ANGLES: Record<Pose, { l: number; r: number }> = {
  sleep: { l: -18, r: 18 },
  idle: { l: 0, r: 0 },
  listen: { l: -6, r: 6 },
  think: { l: 0, r: 0 },
  alert: { l: -2, r: 2 },
  relief: { l: 8, r: -8 },
  write: { l: -4, r: 4 },
  catch: { l: -6, r: 6 },
  wave: { l: 0, r: 0 },
  off: { l: -18, r: 18 },
}

/**
 * Satya's production art is the blue 3D blob in `../assets/mascot_*.png` (not the old shield
 * character). Every pose already has its face, cap, shield, pen or paws baked into the render, so
 * the component must not draw a second set of accessories on top of it.
 */
const AURA_POSES: Pose[] = ['alert', 'relief', 'listen', 'write', 'catch']

const soft = springTokens.soft

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

const REST: TargetAndTransition = { y: 0, rotate: 0, scaleX: 1, scaleY: 1, opacity: 1 }

/**
 * Pose motion is deliberately small and spring-smoothed. Big looping rotations read as jitter on
 * a 128 px mascot; a few pixels of squash/stretch reads as breathing.
 */
function getFigureMotion(
  pose: Pose,
  reduced: boolean,
): { animate: TargetAndTransition; transition: Transition } {
  if (reduced) {
    return { animate: REST, transition: { duration: 0.15, ease: 'easeOut' } }
  }

  switch (pose) {
    case 'sleep':
      return {
        animate: {
          ...REST,
          y: [0, -1.2, 0],
          scaleY: 1,
          scaleX: [1, 0.992, 1],
        },
        transition: { duration: 3.6, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'idle':
      return {
        animate: {
          ...REST,
          y: [0, -0.8, 0],
          scaleY: 1,
          scaleX: [1, 0.995, 1],
        },
        transition: { duration: 3.6, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'listen':
      return {
        animate: {
          ...REST,
          rotate: [0, -1.6, 0],
          y: [0, -0.8, 0],
          scaleY: 1,
        },
        transition: { duration: 2.4, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'think':
      return {
        animate: {
          ...REST,
          rotate: [-1.2, 1.2, -1.2],
          y: [0, -0.8, 0],
        },
        transition: { duration: 2.6, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'alert':
      // One soft hop on landing, then still. No shake, no repeat.
      return {
        animate: {
          ...REST,
          y: [0, -10, 0],
          scaleY: [1, 1.025, 0.99, 1],
          scaleX: [1, 0.985, 1.01, 1],
        },
        transition: {
          duration: 0.7,
          times: [0, 0.35, 0.65, 1],
          ease: [0.22, 1, 0.36, 1],
        },
      }
    case 'relief':
      return {
        animate: {
          ...REST,
          y: [0, -2.4, 0],
          scaleY: 1,
          scaleX: [1, 0.99, 1],
        },
        transition: { duration: 2.4, ease: 'easeInOut' },
      }
    case 'write':
      return {
        animate: {
          ...REST,
          y: [0, 1, 0],
          rotate: [0, -0.7, 0.7, 0],
          scaleY: 1,
        },
        transition: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'catch':
      return {
        animate: {
          ...REST,
          y: [0, -2.4, 0],
          scaleY: 1,
          scaleX: [1, 0.99, 1],
        },
        transition: { duration: 1.8, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'wave':
      return {
        animate: {
          ...REST,
          rotate: [0, 2, -1, 2, -1, 0],
          y: [0, -1, 0],
        },
        transition: { duration: 2.2, repeat: Infinity, repeatDelay: 0.5, ease: 'easeInOut' },
      }
    case 'off':
      return {
        animate: { ...REST, opacity: 0.6, scaleY: 0.96, scaleX: 0.98 },
        transition: soft,
      }
    default:
      return { animate: REST, transition: soft }
  }
}

const Mascot = memo(function Mascot({
  pose,
  mood,
  audioLevel = 0,
  look,
  size = 'M',
  reducedMotion,
}: MascotProps) {
  const activePose: Pose = pose ?? (mood ? MOOD_TO_POSE[mood] ?? 'idle' : 'idle')
  const reduced = Boolean(useReducedMotion()) || Boolean(reducedMotion)
  const spec = POSES[activePose] ?? POSES.idle
  const renderedSize = typeof size === 'number' ? size : sizePx[size]

  const blinkKey = useBlink(activePose, reduced)
  const earAngles = EAR_ANGLES[activePose] ?? EAR_ANGLES.idle
  const tracking = !reduced && spec.track && Boolean(look?.near)
  const lookX = tracking
    ? clamp((look?.dx ?? 0) / 35, -4, 4)
    : spec.look
    ? spec.look.x
    : 0
  const lookY = tracking
    ? clamp((look?.dy ?? 0) / 35, -3, 3)
    : spec.look
    ? spec.look.y
    : 0
  const audioScale =
    !reduced && activePose === 'listen' ? 1 + clamp(audioLevel, 0, 1) * 0.02 : 1

  const { animate: figureAnimate, transition: figureTransition } = useMemo(
    () => getFigureMotion(activePose, reduced),
    [activePose, reduced],
  )

  const auraColor =
    activePose === 'alert'
      ? color.hold
      : activePose === 'listen'
      ? color.watch
      : activePose === 'relief'
      ? color.good
      : activePose === 'write'
      ? color.write
      : color.verify
  const showAura = AURA_POSES.includes(activePose)
  const listenAura = 0.25 + clamp(audioLevel, 0, 1) * 0.35
  const auraOpacity = activePose === 'alert' ? 0.5 : activePose === 'listen' ? listenAura : 0.3

  return (
    <div
      style={{
        width: renderedSize,
        height: renderedSize,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        userSelect: 'none',
        overflow: 'visible',
      }}
      role="img"
      aria-label={`Satya mascot, ${activePose}`}
    >
      {/* Aura ring sits behind the character. Alert pulses twice and then holds steady. */}
      <svg
        viewBox="0 0 200 200"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          overflow: 'visible',
          pointerEvents: 'none',
        }}
      >
        <motion.circle
          cx={100}
          cy={100}
          r={96}
          fill="none"
          stroke={auraColor}
          strokeWidth={4}
          initial={false}
          animate={
            activePose === 'alert' && !reduced
              ? {
                  opacity: [0.2, 0.55, 0.5, 0.55, 0.5],
                  scale: [0.98, 1.05, 1, 1.05, 1],
                }
              : { opacity: showAura && activePose !== 'relief' ? auraOpacity : 0, scale: 1 }
          }
          transition={
            activePose === 'alert' && !reduced
              ? { duration: 1.2, times: [0, 0.25, 0.5, 0.75, 1], ease: 'easeInOut' }
              : {
                  duration: activePose === 'relief' ? 1.2 : reduced ? 0.15 : 0.35,
                  ease: 'easeOut',
                }
          }
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        />
      </svg>

      <motion.div
        animate={figureAnimate}
        transition={figureTransition}
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          transformOrigin: '50% 50%',
        }}
      >
        <motion.div
          animate={{ scale: audioScale }}
          transition={soft}
          style={{
            position: 'relative',
            width: '100%',
            height: '100%',
            transformOrigin: '50% 50%',
          }}
        >
          <svg
            viewBox="0 0 200 200"
            role="presentation"
            style={{ width: '100%', height: '100%', overflow: 'visible', display: 'block' }}
          >
            <defs>
              <linearGradient id="satya-body" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#F5CEA5" />
                <stop offset="100%" stopColor={color.body} />
              </linearGradient>
              <linearGradient id="satya-tummy" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FFF9EF" />
                <stop offset="100%" stopColor={color.tummy} />
              </linearGradient>
            </defs>

            {/* Rig layers 1–13: shadow, ears, body, tummy, limbs, cheeks, brows, eyes,
                spring-driven pupils, lids, mouth and pose accents. */}
            <g data-layer="shadow">
              <ellipse cx="100" cy="183" rx="55" ry="8" fill={color.shadow} />
            </g>
            <motion.g
              animate={{ scaleY: reduced ? spec.stretch : [spec.stretch, spec.stretch * 1.025, spec.stretch] }}
              transition={reduced ? { duration: 0.15 } : { duration: 3.6, repeat: Infinity, ease: 'easeInOut' }}
              style={{ transformBox: 'view-box', transformOrigin: '100px 177px' }}
            >
              <motion.g
                data-layer="left-ear"
                animate={{ rotate: reduced ? 0 : earAngles.l, y: !reduced && activePose === 'listen' ? -4 : 0 }}
                transition={springTokens.soft}
                style={{ transformBox: 'view-box', transformOrigin: '76px 80px' }}
              >
                <path
                  d="M59 78 C48 63 46 28 58 19 C72 9 83 30 82 68 Z"
                  fill="url(#satya-body)"
                  stroke={color.sticker}
                  strokeWidth="5"
                  strokeLinejoin="round"
                />
                <path d="M60 61 C55 46 56 31 62 27 C69 26 73 43 73 65 Z" fill={color.earInner} />
              </motion.g>
              <motion.g
                data-layer="right-ear"
                animate={{ rotate: reduced ? 0 : earAngles.r, y: !reduced && activePose === 'listen' ? -4 : 0 }}
                transition={springTokens.soft}
                style={{ transformBox: 'view-box', transformOrigin: '124px 80px' }}
              >
                <path
                  d="M141 78 C152 63 154 28 142 19 C128 9 117 30 118 68 Z"
                  fill="url(#satya-body)"
                  stroke={color.sticker}
                  strokeWidth="5"
                  strokeLinejoin="round"
                />
                <path d="M140 61 C145 46 144 31 138 27 C131 26 127 43 127 65 Z" fill={color.earInner} />
              </motion.g>
              <g data-layer="body">
                <path
                  d="M100 43 C139 43 164 70 164 112 C164 153 138 179 100 179 C62 179 36 153 36 112 C36 70 61 43 100 43 Z"
                  fill="url(#satya-body)"
                  stroke={color.sticker}
                  strokeWidth="6"
                />
              </g>
              <g data-layer="tummy">
                <ellipse cx="100" cy="145" rx="39" ry="27" fill="url(#satya-tummy)" />
              </g>
              <g data-layer="feet">
                <ellipse cx="80" cy="180" rx="15" ry="7" fill={color.bodyDark} />
                <ellipse cx="120" cy="180" rx="15" ry="7" fill={color.bodyDark} />
              </g>
              <g data-layer="limbs">
              <g fill="none" stroke={color.bodyDark} strokeWidth="13" strokeLinecap="round">
                {activePose !== 'catch' ? <path d="M49 122 C40 131 40 141 48 148" /> : null}
                {activePose !== 'wave' && activePose !== 'alert' ? (
                  activePose === 'catch' ? null : <path d="M151 122 C160 131 160 141 152 148" />
                ) : null}
              </g>
              <g fill={color.bodyDark} stroke={color.sticker} strokeWidth="3">
                {activePose !== 'catch' ? <ellipse cx="48" cy="149" rx="9" ry="8" /> : null}
                {activePose !== 'wave' && activePose !== 'alert' ? (
                  activePose === 'catch' ? null : <ellipse cx="152" cy="149" rx="9" ry="8" />
                ) : null}
              </g>
              </g>
              <g data-layer="cheeks">
              {spec.blush ? (
                <g fill={color.blush} opacity="0.68">
                  <ellipse cx="57" cy="128" rx="10" ry="5" />
                  <ellipse cx="143" cy="128" rx="10" ry="5" />
                </g>
              ) : null}
              </g>
              <g data-layer="brows">
              {spec.brows === 'think' ? (
                <g fill="none" stroke={color.ink} strokeWidth="3" strokeLinecap="round">
                  <path d="M68 85 Q78 80 87 85" />
                  <path d="M116 83 Q127 78 135 84" />
                </g>
              ) : null}
              {spec.brows === 'alert' ? (
                <g fill="none" stroke={color.ink} strokeWidth="3" strokeLinecap="round">
                  <path d="M68 82 L87 87" />
                  <path d="M113 87 L132 82" />
                </g>
              ) : null}
              </g>
              <g data-layer="eyes">
              {spec.eyes === 'sleep' ? (
                <g fill="none" stroke={color.ink} strokeWidth="4" strokeLinecap="round">
                  <path d="M67 104 Q78 111 89 104" />
                  <path d="M111 104 Q122 111 133 104" />
                </g>
              ) : spec.eyes === 'happy' ? (
                <g fill="none" stroke={color.ink} strokeWidth="4" strokeLinecap="round">
                  <path d="M67 105 Q78 94 89 105" />
                  <path d="M111 105 Q122 94 133 105" />
                </g>
              ) : null}
              </g>
              <g data-layer="pupils">
              {spec.eyes === 'open' || spec.eyes === 'wide' ? (
                <motion.g
                  key={blinkKey}
                  initial={blinkKey > 0 ? { scaleY: 1 } : false}
                  animate={blinkKey > 0 ? { scaleY: [1, 0.08, 1] } : { scaleY: 1 }}
                  transition={{ duration: BLINK_MS / 1000, times: [0, 0.5, 1], ease: 'easeInOut' }}
                  style={{ transformBox: 'view-box', transformOrigin: '100px 103px' }}
                >
                  <g fill={color.sticker}>
                    <ellipse cx="78" cy="103" rx="10" ry={spec.eyes === 'wide' ? 14 : 12} />
                    <ellipse cx="122" cy="103" rx="10" ry={spec.eyes === 'wide' ? 14 : 12} />
                  </g>
                  <motion.g
                    animate={{ x: lookX, y: lookY }}
                    transition={{ type: 'spring', stiffness: 220, damping: 18 }}
                  >
                    <g fill={color.ink}>
                      <ellipse cx="79" cy="104" rx="4.5" ry="6" />
                      <ellipse cx="123" cy="104" rx="4.5" ry="6" />
                    </g>
                    <g fill={color.sticker}>
                      <circle cx="80" cy="102" r="1.4" />
                      <circle cx="124" cy="102" r="1.4" />
                    </g>
                  </motion.g>
                </motion.g>
              ) : null}
              </g>
              <g data-layer="eyelids">
              {blinkKey > 0 && (spec.eyes === 'open' || spec.eyes === 'wide') ? (
                <motion.g
                  key={blinkKey}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0, 1, 0] }}
                  transition={{ duration: BLINK_MS / 1000, times: [0, 0.5, 1], ease: 'easeInOut' }}
                  fill={color.body}
                >
                  <path d="M67 103 Q78 91 89 103 L89 110 Q78 106 67 110 Z" />
                  <path d="M111 103 Q122 91 133 103 L133 110 Q122 106 111 110 Z" />
                </motion.g>
              ) : null}
              </g>
              <g data-layer="mouth">
              {spec.mouth === 'happy' ? (
                <path d="M89 133 Q100 145 111 133 Q108 152 100 151 Q92 151 89 133 Z" fill={color.ink} />
              ) : spec.mouth === 'smile' ? (
                <path d="M88 137 Q100 149 112 137" fill="none" stroke={color.ink} strokeWidth="3.5" strokeLinecap="round" />
              ) : spec.mouth === 'o' ? (
                <ellipse cx="100" cy="140" rx="6" ry="8" fill={color.ink} />
              ) : spec.mouth === 'firm' ? (
                <path d="M91 141 Q100 138 109 141" fill="none" stroke={color.ink} strokeWidth="3.5" strokeLinecap="round" />
              ) : spec.mouth === 'straight' ? (
                <path d="M92 141 L108 141" fill="none" stroke={color.ink} strokeWidth="3" strokeLinecap="round" />
              ) : spec.mouth === 'tiny' ? (
                <ellipse cx="100" cy="140" rx="3" ry="4" fill={color.ink} />
              ) : (
                <path d="M94 141 Q100 144 106 141" fill="none" stroke={color.ink} strokeWidth="2.5" strokeLinecap="round" />
              )}
              </g>
            </motion.g>
            <g data-layer="pose-accessories">
              <Accessories pose={activePose} audioLevel={audioLevel} reducedMotion={reduced} />
            </g>
          </svg>
        </motion.div>
      </motion.div>
    </div>
  )
})

export default Mascot
