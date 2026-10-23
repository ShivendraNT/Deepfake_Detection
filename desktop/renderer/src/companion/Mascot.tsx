import { memo, useEffect, useMemo } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import type { TargetAndTransition, Transition } from 'framer-motion'

import type { MascotMood, Pose } from '../../../shared/contracts'
import mascot3dImg from '../assets/mascot_3d.png'
import mascotAlertImg from '../assets/mascot_alert.png'
import mascotCatchImg from '../assets/mascot_catch.png'
import mascotListenImg from '../assets/mascot_listen.png'
import mascotReliefImg from '../assets/mascot_relief.png'
import mascotSleepImg from '../assets/mascot_sleep.png'
import mascotThinkImg from '../assets/mascot_think.png'
import mascotWaveImg from '../assets/mascot_wave.png'
import mascotWriteImg from '../assets/mascot_write.png'
import { color, motion as springTokens, size as sizePx } from '../shared/tokens'
import { POSES } from './poses'

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

/**
 * Satya's production art is the blue 3D blob in `../assets/mascot_*.png` (not the old shield
 * character). Every pose already has its face, cap, shield, pen or paws baked into the render, so
 * the component must not draw a second set of accessories on top of it.
 */
const POSE_IMAGE: Record<Pose, string> = {
  sleep: mascotSleepImg,
  idle: mascot3dImg,
  listen: mascotListenImg,
  think: mascotThinkImg,
  alert: mascotAlertImg,
  relief: mascotReliefImg,
  write: mascotWriteImg,
  catch: mascotCatchImg,
  wave: mascotWaveImg,
  off: mascotSleepImg,
}

/** The wave render has more transparent padding around the blob; scale it back up to match. */
const POSE_SCALE: Partial<Record<Pose, number>> = { wave: 1.12 }

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
          scaleY: [1, 1.03, 1],
          scaleX: [1, 0.992, 1],
        },
        transition: { duration: 4.8, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'idle':
      return {
        animate: {
          ...REST,
          y: [0, -0.8, 0],
          scaleY: [1, 1.018, 1],
          scaleX: [1, 0.995, 1],
        },
        transition: { duration: 4.2, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'listen':
      return {
        animate: {
          ...REST,
          rotate: [0, -1.6, 0],
          y: [0, -0.8, 0],
          scaleY: [1, 1.012, 1],
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
          y: [0, -7, 0],
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
          scaleY: [1, 1.025, 1],
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
          scaleY: [1, 0.995, 1],
        },
        transition: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' },
      }
    case 'catch':
      return {
        animate: {
          ...REST,
          y: [0, -2.4, 0],
          scaleY: [1, 1.03, 1],
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

  // Warm the browser cache so the first pose switch is a cross-fade, never a blank frame.
  useEffect(() => {
    const sources = new Set(Object.values(POSE_IMAGE))
    for (const src of sources) {
      const preload = new Image()
      preload.src = src
    }
  }, [])

  const tracking = !reduced && spec.track && Boolean(look?.near)
  const lookX = tracking ? clamp((look?.dx ?? 0) / 70, -2, 2) : 0
  const lookY = tracking ? clamp((look?.dy ?? 0) / 90, -1, 1) : 0
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
          animate={{ x: lookX, y: lookY, scale: audioScale }}
          transition={soft}
          style={{
            position: 'relative',
            width: '100%',
            height: '100%',
            transformOrigin: '50% 50%',
          }}
        >
          <AnimatePresence initial={false}>
            <motion.img
              key={activePose}
              src={POSE_IMAGE[activePose]}
              alt={`Satya 3D mascot — ${activePose}`}
              draggable={false}
              initial={{ opacity: 0, scale: (POSE_SCALE[activePose] ?? 1) * 0.985 }}
              animate={{ opacity: 1, scale: POSE_SCALE[activePose] ?? 1 }}
              exit={{ opacity: 0, scale: (POSE_SCALE[activePose] ?? 1) * 0.99 }}
              transition={{
                opacity: { duration: reduced ? 0.15 : 0.22, ease: 'easeOut' },
                scale: soft,
              }}
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                pointerEvents: 'none',
                display: 'block',
                transformOrigin: '50% 50%',
              }}
            />
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </div>
  )
})

export default Mascot
