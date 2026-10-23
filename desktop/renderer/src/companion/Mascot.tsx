import { memo, useEffect, useId, useMemo, useRef, useState } from 'react'
import {
  AnimatePresence,
  motion,
  useAnimationControls,
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

// Optical mass normalization: balances rendered volume across pose renders
const POSE_SCALE: Record<Pose, number> = {
  idle: 1.0,
  listen: 1.04,
  think: 1.03,
  alert: 1.02,
  relief: 1.15,
  catch: 1.05,
  write: 1.03,
  wave: 1.18,
  sleep: 0.98,
  off: 0.94,
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
  const safeAudioLevel = Number.isFinite(audioLevel) ? Math.min(1, Math.max(0, audioLevel)) : 0
  const blinkKey = useBlink(activePose, reduced)
  const supportsBlink = ['idle', 'listen', 'alert', 'catch'].includes(activePose)
  const svgId = useId().replace(/[^a-zA-Z0-9_-]/g, '')

  // Keep decoded 3D pose assets in browser memory so pose transitions are instantaneous
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

  // 1. Organic Wake-Up Reaction Animation
  // When transitioning from 'sleep' to 'idle', Satya stretches upward, shakes off sleep, and perks up.
  const previousPoseRef = useRef<Pose>(activePose)
  const [isWakingUp, setIsWakingUp] = useState(false)

  // 2. Ear Twitch Animation Controls (random + acoustic peak reactivity + wake-up perk)
  const leftEarControls = useAnimationControls()
  const rightEarControls = useAnimationControls()
  const previousAudioLevel = useRef(safeAudioLevel)
  const nextAudioEar = useRef<'left' | 'right'>('left')

  useEffect(() => {
    if (previousPoseRef.current === 'sleep' && activePose === 'idle' && !reduced) {
      setIsWakingUp(true)
      void leftEarControls.start({
        rotate: [0, -7, 0],
        y: [0, -3.5, 0],
        transition: { duration: 0.5, ease: 'easeOut' },
      })
      void rightEarControls.start({
        rotate: [0, 7, 0],
        y: [0, -3.5, 0],
        transition: { duration: 0.5, ease: 'easeOut' },
      })
      const timer = window.setTimeout(() => setIsWakingUp(false), 900)
      previousPoseRef.current = activePose
      return () => window.clearTimeout(timer)
    }
    previousPoseRef.current = activePose
  }, [activePose, leftEarControls, reduced, rightEarControls])

  // 3. Organic Idle Micro-Fidgets (Codex-style living companion physics)
  // Every 3.5 - 7 seconds, Satya performs a spontaneous micro-expression (head cock, ear perk, happy sigh)
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
    if (fidgetIndex === 0 || reduced || activePose === 'off' || isWakingUp) return

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

    const resetTimer = window.setTimeout(resetFidget, 320)
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
    isWakingUp,
    reduced,
  ])

  // Spontaneous idle ear twitches
  useEffect(() => {
    if (reduced || activePose === 'off') return

    const twitch = (controls: typeof leftEarControls, direction: number) => {
      void controls.start({
        rotate: [0, direction * 5, 0],
        y: [0, -2.5, 0],
        transition: { duration: 0.38, ease: 'easeOut' },
      })
    }
    let leftTimer: number
    let rightTimer: number
    const scheduleLeft = () => {
      leftTimer = window.setTimeout(() => {
        twitch(leftEarControls, -1)
        scheduleLeft()
      }, 6000 + Math.random() * 4000)
    }
    const scheduleRight = () => {
      rightTimer = window.setTimeout(() => {
        twitch(rightEarControls, 1)
        scheduleRight()
      }, 6000 + Math.random() * 4000)
    }

    scheduleLeft()
    scheduleRight()
    return () => {
      window.clearTimeout(leftTimer)
      window.clearTimeout(rightTimer)
      leftEarControls.stop()
      rightEarControls.stop()
    }
  }, [activePose, leftEarControls, reduced, rightEarControls])

  // Audio peak reactive ear perks
  useEffect(() => {
    const crossedAudioPeak = previousAudioLevel.current < 0.72 && safeAudioLevel >= 0.72
    previousAudioLevel.current = safeAudioLevel
    if (reduced || !crossedAudioPeak || activePose === 'off') return

    const isLeft = nextAudioEar.current === 'left'
    const controls = isLeft ? leftEarControls : rightEarControls
    nextAudioEar.current = isLeft ? 'right' : 'left'
    void controls.start({
      rotate: [0, (isLeft ? -1 : 1) * 6, 0],
      y: [0, -3.5, 0],
      transition: { duration: 0.36, ease: 'easeOut' },
    })
  }, [activePose, leftEarControls, reduced, rightEarControls, safeAudioLevel])

  // 4. Interactive Head Gaze & Orientation (Follows Cursor Smoothly via Natural Head Physics)
  const tracking = Boolean(look?.near) && !reduced
  const rawLookX = tracking ? (look?.dx ?? 0) / 32 : spec.look?.x ?? 0
  const rawLookY = tracking ? (look?.dy ?? 0) / 32 : spec.look?.y ?? 0

  const gazeX = useSpring(rawLookX, springTokens.gaze)
  const gazeY = useSpring(rawLookY, springTokens.gaze)
  const gazeRotate = useSpring(rawLookX * 0.8, springTokens.gaze)

  useEffect(() => {
    gazeX.set(rawLookX)
    gazeY.set(rawLookY)
    gazeRotate.set(rawLookX * 0.8)
  }, [gazeRotate, gazeX, gazeY, rawLookX, rawLookY])

  // 5. Drag Inertia and Velocity Tilt
  const dragLeanTarget = useMotionValue(0)
  const dragLean = useSpring(dragLeanTarget, springTokens.drag)

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

  // 6. Living Procedural Physics Loop per Pose (Squash, Stretch, Breathing, Pose Gestures)
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
      } else if (isWakingUp) {
        // Joyful wake-up stretch: squashes, stretches upward, and settles gently
        anim.scaleY = [1, 0.93, 1.07, 0.98, 1]
        anim.scaleX = [1, 1.05, 0.95, 1.01, 1]
        anim.y = [0, 2, -5.5, 0.5, 0]
        trans = { duration: 0.9, ease: 'easeOut' }
      } else if (activePose === 'idle') {
        // Continuous alive jelly micro-breathing loop (volume-preserving)
        anim.y = [0, -2.0, 0.4, 0]
        anim.scaleY = [1, 1.025, 0.988, 1]
        anim.scaleX = [1, 0.988, 1.012, 1]
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
        // Energetic spring hop onto screen with solid stance
        anim.scale = [0.9, 1.08, 1]
        anim.y = [-12, 0]
        trans = { type: 'spring', stiffness: 520, damping: 20 }
      } else if (activePose === 'relief') {
        // "Phew!" relieved breath loop and micro-hop
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
        // High-energy friendly hand wave sway and bounce
        anim.rotate = [0, 6, -5, 6, -5, 0]
        anim.y = [0, -3, 0]
        trans = { duration: 1.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'off') {
        anim.opacity = 0.5
        anim.scaleY = 0.94
        trans = soft
      }
    }

    return { figureAnimate: anim, figureTransition: trans }
  }, [activePose, dragging, isWakingUp, reduced])

  // 7. Halo Aura Ring
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
  const listenAura = 0.25 + Math.min(1, Math.max(0, safeAudioLevel)) * 0.55
  const auraOpacity = activePose === 'alert' ? 0.7 : activePose === 'listen' ? listenAura : 0.4
  const mascotBaseScale = POSE_SCALE[activePose] ?? 1.0

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
      {/* Background SVG: Grounding Shadow & Halo Aura Ring */}
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
        <ellipse
          cx={100}
          cy={188}
          rx={44}
          ry={7}
          fill="rgba(3, 51, 84, 0.28)"
          style={{ filter: 'blur(3px)' }}
        />

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
            transformBox: 'view-box',
            transformOrigin: '100px 100px',
            filter: activePose === 'alert' ? `drop-shadow(0 0 8px ${color.hold})` : undefined,
          }}
        />

        {/* Ambient SVG Accessories */}
        <motion.g
          id="accessories"
          animate={figureAnimate}
          transition={figureTransition}
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        >
          <Accessories pose={activePose} audioLevel={safeAudioLevel} reducedMotion={reduced} />
        </motion.g>
      </svg>

      {/* Main Living Character Rig (Physics Springs, Drag Lean, Micro-Fidgets, and Gaze Tracking) */}
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
              {/* Simultaneous Cross-Fade & Organic Morph Transition between Poses */}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <AnimatePresence initial={false}>
                  <motion.div
                    key={activePose}
                    initial={{
                      opacity: 0,
                      scale: mascotBaseScale * 0.94,
                    }}
                    animate={{
                      opacity: 1,
                      scale: mascotBaseScale,
                    }}
                    exit={{
                      opacity: 0,
                      scale: mascotBaseScale * 1.04,
                    }}
                    transition={{
                      opacity: { duration: 0.26, ease: 'easeInOut' },
                      scale: { type: 'spring', stiffness: 320, damping: 25 },
                    }}
                    style={{
                      position: 'absolute',
                      inset: 0,
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transformOrigin: '50% 65%',
                    }}
                  >
                    <img
                      src={POSE_IMAGES[activePose] ?? mascot3dImg}
                      alt={`Satya Mascot - ${activePose}`}
                      draggable={false}
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                        pointerEvents: 'none',
                        display: 'block',
                        filter: 'drop-shadow(0 8px 18px rgba(20,16,40,0.22))',
                      }}
                    />
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Foreground Interactive SVG Overlay: Ear Twitches & Natural Top-Down Eyelids */}
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
                <defs>
                  {/* Exact Eye Clip Paths matching Satya's 3D Blue Blob Eyes */}
                  <clipPath id={`${svgId}-left-eye-clip`}>
                    <ellipse cx={66.2} cy={115.2} rx={16} ry={14} />
                  </clipPath>
                  <clipPath id={`${svgId}-right-eye-clip`}>
                    <ellipse cx={131.3} cy={115.3} rx={16} ry={14} />
                  </clipPath>

                  {/* Top-down eyelid gradients matching Satya's skin tones & lighting */}
                  <linearGradient id={`${svgId}-lid-left`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#21C4CB" />
                    <stop offset="100%" stopColor="#1B9EA5" />
                  </linearGradient>
                  <linearGradient id={`${svgId}-lid-right`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#98E4E2" />
                    <stop offset="100%" stopColor="#5BC8C5" />
                  </linearGradient>
                </defs>

                {/* Left Ear Twitching Impulse */}
                <motion.g
                  animate={leftEarControls}
                  style={{ transformBox: 'view-box', transformOrigin: '48px 65px' }}
                />

                {/* Right Ear Twitching Impulse */}
                <motion.g
                  animate={rightEarControls}
                  style={{ transformBox: 'view-box', transformOrigin: '142px 65px' }}
                />

                {/* Natural Top-Down Eyelid Blink Animation (Only active during blinks in open-eye poses) */}
                {supportsBlink && blinkKey > 0 && !isWakingUp ? (
                  <>
                    <g clipPath={`url(#${svgId}-left-eye-clip)`}>
                      <motion.ellipse
                        key={`left-lid-${blinkKey}`}
                        cx={66.2}
                        cy={115.2}
                        rx={16}
                        ry={14}
                        fill={`url(#${svgId}-lid-left)`}
                        initial={{ scaleY: 0 }}
                        animate={{ scaleY: [0, 1, 0] }}
                        transition={{
                          duration: BLINK_MS / 1000,
                          times: [0, 0.5, 1],
                          ease: 'easeInOut',
                        }}
                        style={{ transformBox: 'fill-box', transformOrigin: 'center top' }}
                      />
                      <motion.path
                        key={`left-lash-${blinkKey}`}
                        d="M 52 117 Q 66.2 124 80 117"
                        stroke="#141122"
                        strokeWidth={2.4}
                        strokeLinecap="round"
                        fill="none"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: [0, 1, 0] }}
                        transition={{
                          duration: BLINK_MS / 1000,
                          times: [0, 0.5, 1],
                          ease: 'easeInOut',
                        }}
                      />
                    </g>
                    <g clipPath={`url(#${svgId}-right-eye-clip)`}>
                      <motion.ellipse
                        key={`right-lid-${blinkKey}`}
                        cx={131.3}
                        cy={115.3}
                        rx={16}
                        ry={14}
                        fill={`url(#${svgId}-lid-right)`}
                        initial={{ scaleY: 0 }}
                        animate={{ scaleY: [0, 1, 0] }}
                        transition={{
                          duration: BLINK_MS / 1000,
                          times: [0, 0.5, 1],
                          ease: 'easeInOut',
                        }}
                        style={{ transformBox: 'fill-box', transformOrigin: 'center top' }}
                      />
                      <motion.path
                        key={`right-lash-${blinkKey}`}
                        d="M 118 117 Q 131.3 124 144 117"
                        stroke="#141122"
                        strokeWidth={2.4}
                        strokeLinecap="round"
                        fill="none"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: [0, 1, 0] }}
                        transition={{
                          duration: BLINK_MS / 1000,
                          times: [0, 0.5, 1],
                          ease: 'easeInOut',
                        }}
                      />
                    </g>
                  </>
                ) : null}
              </svg>
            </motion.div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  )
})

export default Mascot
