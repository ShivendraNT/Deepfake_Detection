import { memo, useEffect, useMemo, useRef, useState } from 'react'
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
} from 'framer-motion'
import type { MotionValue, TargetAndTransition, Transition } from 'framer-motion'

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
import { Accessories } from './accessories'
import { POSES } from './poses'
import { BLINK_MS, useBlink } from './useBlink'

export type MascotSize = keyof typeof sizePx

export interface MascotProps {
  pose?: Pose
  mood?: MascotMood
  alert?: boolean
  audioLevel?: number
  look?: { dx: number; dy: number; near: boolean }
  dragging?: boolean
  dragVelocity?: MotionValue<{ x: number; y: number }>
  size?: number | MascotSize
  reducedMotion?: boolean
}

const MOOD_TO_POSE: Record<MascotMood, Pose> = {
  sleepy: 'sleep',
  attentive: 'idle',
  focused: 'think',
  calm_alert: 'alert',
  writing: 'write',
  off: 'off',
}

const POSE_IMAGES: Record<Pose, string> = {
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

const soft = springTokens.soft

const Mascot = memo(function Mascot({
  pose,
  mood,
  audioLevel = 0,
  look,
  dragging = false,
  dragVelocity,
  size = 'M',
  reducedMotion,
}: MascotProps) {
  const activePose: Pose = pose ?? (mood ? MOOD_TO_POSE[mood] : 'idle')
  const reduced = Boolean(useReducedMotion()) || Boolean(reducedMotion)
  const spec = POSES[activePose] ?? POSES.idle
  const renderedSize = typeof size === 'number' ? size : sizePx[size]
  const blinkKey = useBlink(activePose, reduced)
  const supportsBlink = ['idle', 'listen', 'alert', 'catch'].includes(activePose)

  // Keep decoded pose assets alive so pose transitions can use the browser's image cache.
  const preloadedImages = useRef<HTMLImageElement[]>([])
  useEffect(() => {
    const images: HTMLImageElement[] = []
    for (const src of new Set(Object.values(POSE_IMAGES))) {
      const img = new Image()
      img.decoding = 'async'
      img.src = src
      if (typeof img.decode === 'function') void img.decode().catch(() => undefined)
      images.push(img)
    }
    preloadedImages.current = images
    return () => {
      preloadedImages.current = []
    }
  }, [])

  // 1. Organic Idle Micro-Fidgets (like Codex Pet)
  // Every 3.5 - 7 seconds, Satya makes a tiny spontaneous head-cock or happy micro-hop.
  const [fidgetIndex, setFidgetIndex] = useState(0)
  useEffect(() => {
    if (reduced || activePose === 'off') return
    let timeoutId: number
    const scheduleNextFidget = () => {
      const delay = 3500 + Math.random() * 3500
      timeoutId = window.setTimeout(() => {
        setFidgetIndex((prev) => prev + 1)
        scheduleNextFidget()
      }, delay)
    }
    scheduleNextFidget()
    return () => window.clearTimeout(timeoutId)
  }, [activePose, reduced])

  const fidgetRotationTarget = useMotionValue(0)
  const fidgetRotation = useSpring(fidgetRotationTarget, springTokens.gaze)
  const fidgetLiftTarget = useMotionValue(0)
  const fidgetLift = useSpring(fidgetLiftTarget, springTokens.drag)
  const fidgetScaleXTarget = useMotionValue(1)
  const fidgetScaleX = useSpring(fidgetScaleXTarget, springTokens.drag)
  const fidgetScaleYTarget = useMotionValue(1)
  const fidgetScaleY = useSpring(fidgetScaleYTarget, springTokens.drag)

  useEffect(() => {
    if (fidgetIndex === 0 || reduced || activePose === 'off') return

    const resetFidget = () => {
      fidgetRotationTarget.set(0)
      fidgetLiftTarget.set(0)
      fidgetScaleXTarget.set(1)
      fidgetScaleYTarget.set(1)
    }
    const gesture = fidgetIndex % 3
    if (gesture === 1) {
      fidgetRotationTarget.set(-2.5)
    } else if (gesture === 2) {
      fidgetRotationTarget.set(2.5)
    } else {
      fidgetLiftTarget.set(-3)
      fidgetScaleXTarget.set(0.985)
      fidgetScaleYTarget.set(1.025)
    }

    const resetTimer = window.setTimeout(resetFidget, 300)
    return () => {
      window.clearTimeout(resetTimer)
      resetFidget()
    }
  }, [
    activePose,
    fidgetIndex,
    fidgetLiftTarget,
    fidgetRotationTarget,
    fidgetScaleXTarget,
    fidgetScaleYTarget,
    reduced,
  ])

  // 2. Smooth Interactive Cursor Gaze & Head Orientation
  const tracking = Boolean(look?.near) && !reduced
  const rawLookX = tracking ? (look?.dx ?? 0) / 32 : spec.look?.x ?? 0
  const rawLookY = tracking ? (look?.dy ?? 0) / 32 : spec.look?.y ?? 0

  const gazeX = useSpring(rawLookX, springTokens.gaze)
  const gazeY = useSpring(rawLookY, springTokens.gaze)
  const gazeRotate = useSpring(rawLookX * 0.8, springTokens.gaze)
  const dragLeanTarget = useMotionValue(0)
  const dragLean = useSpring(dragLeanTarget, springTokens.drag)

  useEffect(() => {
    gazeX.set(rawLookX)
    gazeY.set(rawLookY)
    gazeRotate.set(rawLookX * 0.8)
  }, [gazeX, gazeY, gazeRotate, rawLookX, rawLookY])

  useEffect(() => {
    if (!dragging || !dragVelocity) {
      dragLeanTarget.set(0)
      return
    }

    const followVelocity = (velocity: { x: number; y: number }) => {
      dragLeanTarget.set(Math.max(-18, Math.min(18, velocity.x * 0.12)))
    }
    followVelocity(dragVelocity.get())
    return dragVelocity.on('change', followVelocity)
  }, [dragging, dragLeanTarget, dragVelocity])

  // Current Mascot Asset Source
  const currentMascotSrc = POSE_IMAGES[activePose] ?? mascot3dImg

  // 3. Optical Mass Normalization per Pose
  const mascotBaseScale =
    activePose === 'wave'
      ? 1.14
      : activePose === 'relief'
      ? 1.12
      : activePose === 'alert'
      ? 1.05
      : 1

  // 4. Living Procedural Physics & Animation Loop (Squash, Stretch, Breathing, Pose Gestures)
  const { figureAnimate, figureTransition } = useMemo((): {
    figureAnimate: TargetAndTransition
    figureTransition: Transition
  } => {
    const anim: TargetAndTransition = {
      scaleY: 1,
      scaleX: 1,
      scale: 1,
      y: 0,
      rotate: 0,
      opacity: 1,
    }
    let trans: Transition = soft

    if (!reduced) {
      if (dragging) {
        // Jelly drag squash: stretches vertically and thins horizontally when held
        anim.scaleX = 0.94
        anim.scaleY = 1.08
        anim.y = -4
        trans = { type: 'spring', stiffness: 450, damping: 22 }
      } else if (activePose === 'idle') {
        // Continuous alive jelly micro-breathing loop (volume-preserving)
        anim.y = [0, -1.8, 0.4, 0]
        anim.scaleY = [1, 1.03, 0.985, 1]
        anim.scaleX = [1, 0.985, 1.015, 1]
        trans = { duration: 3.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'sleep') {
        // Peaceful slow rhythmic sleep breathing with gentle droop
        anim.y = [0, -1.0, 0]
        anim.scaleY = [1, 1.025, 1]
        anim.scaleX = [1, 0.99, 1]
        trans = { duration: 4.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'listen') {
        // Attentive listening perk & gentle head tilt toward incoming audio
        anim.rotate = [-3.5, -1, -4.0, -1.5, -3.5]
        anim.y = [0, 1.4, -1.8, 0.6, 0]
        anim.scaleY = [1, 1.025, 0.988, 1.02, 1]
        trans = { duration: 2.6, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'think') {
        // Thoughtful float & sway
        anim.rotate = [-2.8, 2.8, -2.8]
        anim.y = [0, -2.4, 0]
        anim.scaleY = [1, 1.018, 1]
        trans = { duration: 2.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'alert') {
        // Alert spring hop onto screen with energetic stance
        anim.scale = [0.9, 1.08, 1]
        anim.y = [-12, 0]
        trans = { type: 'spring', stiffness: 520, damping: 20 }
      } else if (activePose === 'relief') {
        // "Phew!" relieved breath loop
        anim.y = [0, -3.2, 0.8, 0]
        anim.scaleY = [1, 1.04, 0.98, 1]
        anim.scaleX = [1, 0.985, 1.015, 1]
        trans = { duration: 2.8, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'catch') {
        // Reaching upward to catch dropped files
        anim.y = [0, -6, 1.5, -4, 0]
        anim.scale = [1, 1.06, 0.985, 1.03, 1]
        anim.rotate = [0, -1.5, 1.5, -0.8, 0]
        trans = { duration: 1.8, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'write') {
        // Scribing/writing rhythmic micro-loop
        anim.y = [0, 1.8, -0.4, 2.0, 0.4, 0]
        anim.rotate = [0, -1.2, 0.9, -0.9, 0.6, 0]
        anim.scaleY = [1, 0.988, 1.01, 0.99, 1]
        trans = { duration: 1.5, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'wave') {
        // Friendly lively hand wave sway
        anim.rotate = [0, 7, -7, 7, -7, 0]
        anim.y = [0, -3, 0]
        trans = { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'off') {
        anim.opacity = 0.5
        anim.scaleY = 0.94
        trans = soft
      }
    }

    return { figureAnimate: anim, figureTransition: trans }
  }, [activePose, dragging, reduced])

  // Aura Ring Color per MASCOT_SPEC
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

  const showAura = ['alert', 'relief', 'listen', 'write', 'catch'].includes(activePose)
  const listenAura = 0.25 + Math.min(1, Math.max(0, audioLevel)) * 0.55
  const auraOpacity = activePose === 'alert' ? 0.7 : activePose === 'listen' ? listenAura : 0.4

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
      aria-label={`Satya living mascot, ${activePose}`}
    >
      {/* SVG Halo Aura Ring Behind Character */}
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
          initial={{ opacity: 0 }}
          animate={{
            opacity: showAura ? auraOpacity : 0,
            scale: activePose === 'alert' && !reduced ? [1, 1.07, 1] : 1,
          }}
          transition={
            activePose === 'alert' && !reduced
              ? { duration: 1.0, repeat: Infinity, ease: 'easeInOut' }
              : { duration: 0.3 }
          }
          style={{
            opacity: 0,
            filter: activePose === 'alert' ? `drop-shadow(0 0 8px ${color.hold})` : undefined,
            transformBox: 'view-box',
            transformOrigin: '100px 100px',
          }}
        />

        {/* Ambient SVG Accessories for Poses that Benefit from Extra Visual Flourish */}
        <motion.g
          id="accessories"
          animate={figureAnimate}
          transition={figureTransition}
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        >
          <Accessories pose={activePose} audioLevel={audioLevel} reducedMotion={reduced} />
        </motion.g>
      </svg>

      {/* Centered Living 3D Blue Blob Character with Codex-Style Springs & Micro-Fidgets */}
      <motion.div
        animate={figureAnimate}
        transition={figureTransition}
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          transformOrigin: '50% 65%',
        }}
      >
        <motion.div
          style={{
            position: 'absolute',
            inset: 0,
            rotate: dragLean,
            transformOrigin: '50% 65%',
          }}
        >
          <motion.div
            style={{
              position: 'absolute',
              inset: 0,
              y: fidgetLift,
              rotate: fidgetRotation,
              scaleX: fidgetScaleX,
              scaleY: fidgetScaleY,
              transformOrigin: '50% 65%',
            }}
          >
            <motion.div
              style={{
                position: 'absolute',
                inset: 0,
                x: gazeX,
                y: gazeY,
                rotate: gazeRotate,
                transformOrigin: '50% 50%',
              }}
            >
              {/* Smooth Elastic Pose Transitions (Anticipatory Squash & Spring Pop) */}
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.img
                  key={activePose}
                  src={currentMascotSrc}
                  alt={`Satya Mascot - ${activePose}`}
                  draggable={false}
                  initial={{
                    scaleX: mascotBaseScale * 1.04,
                    scaleY: mascotBaseScale * 0.92,
                    opacity: 0.6,
                    y: 3,
                  }}
                  animate={{ scaleX: mascotBaseScale, scaleY: mascotBaseScale, opacity: 1, y: 0 }}
                  exit={{
                    scaleX: mascotBaseScale * 0.97,
                    scaleY: mascotBaseScale * 0.94,
                    opacity: 0,
                    y: -2,
                  }}
                  transition={{
                    scaleX: { type: 'spring', stiffness: 420, damping: 24 },
                    scaleY: { type: 'spring', stiffness: 420, damping: 24 },
                    y: { type: 'spring', stiffness: 380, damping: 22 },
                    opacity: { duration: 0.12 },
                  }}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    pointerEvents: 'none',
                    display: 'block',
                    filter: 'drop-shadow(0 8px 18px rgba(20,16,40,0.24))',
                  }}
                />
              </AnimatePresence>

              {/* Natural Eye Blinking Layer with Cyan Eyelids */}
              {supportsBlink && blinkKey > 0 ? (
                <svg
                  viewBox="0 0 200 200"
                  aria-hidden="true"
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: '100%',
                    height: '100%',
                    overflow: 'visible',
                    pointerEvents: 'none',
                    zIndex: 2,
                  }}
                >
                  <motion.ellipse
                    key={`left-${blinkKey}`}
                    cx={64.5}
                    cy={113}
                    rx={23}
                    ry={24}
                    fill="#44D5DE"
                    initial={{ scaleY: 0 }}
                    animate={{ scaleY: [0, 1, 0] }}
                    transition={{ duration: BLINK_MS / 1000, ease: 'easeInOut' }}
                    style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
                  />
                  <motion.ellipse
                    key={`right-${blinkKey}`}
                    cx={133}
                    cy={115}
                    rx={23}
                    ry={24}
                    fill="#44D5DE"
                    initial={{ scaleY: 0 }}
                    animate={{ scaleY: [0, 1, 0] }}
                    transition={{ duration: BLINK_MS / 1000, ease: 'easeInOut' }}
                    style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
                  />
                </svg>
              ) : null}
            </motion.div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  )
})

export default Mascot
