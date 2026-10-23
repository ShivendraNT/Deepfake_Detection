import { memo, useEffect, useMemo } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
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
import { Accessories } from './accessories'
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
  size = 'M',
  reducedMotion,
}: MascotProps) {
  const activePose: Pose = pose ?? (mood ? MOOD_TO_POSE[mood] ?? 'idle' : 'idle')
  const reduced = Boolean(useReducedMotion()) || Boolean(reducedMotion)
  const spec = POSES[activePose] ?? POSES.idle
  const renderedSize = typeof size === 'number' ? size : sizePx[size]

  // Preload all 3D blue blob assets in the browser cache for instant zero-flash transitions
  useEffect(() => {
    const sources = Object.values(POSE_IMAGES)
    for (const src of sources) {
      const img = new Image()
      img.src = src
    }
  }, [])

  // Smooth mouse/cursor gaze tracking
  const tracking = Boolean(look?.near) && !reduced
  const lookX = tracking
    ? Math.max(-5, Math.min(5, (look?.dx ?? 0) / 35))
    : spec.look?.x ?? 0
  const lookY = tracking
    ? Math.max(-4, Math.min(4, (look?.dy ?? 0) / 35))
    : spec.look?.y ?? 0

  const currentMascotSrc = POSE_IMAGES[activePose] ?? mascot3dImg

  // Slight optical normalization so all 3D rendered poses have consistent visual mass
  const mascotBaseScale =
    activePose === 'wave'
      ? 1.14
      : activePose === 'relief'
      ? 1.12
      : activePose === 'alert'
      ? 1.04
      : 1

  const { figureAnimate, figureTransition } = useMemo((): {
    figureAnimate: TargetAndTransition
    figureTransition: Transition
  } => {
    const anim: TargetAndTransition = {
      scaleY: 1,
      scaleX: 1,
      y: 0,
      rotate: 0,
      opacity: 1,
    }
    let trans: Transition = soft

    if (!reduced) {
      if (activePose === 'idle') {
        // Continuous organic micro-breathing loop
        anim.y = [0, -1.2, 0]
        anim.scaleY = [1, 1.025, 1]
        anim.scaleX = [1, 0.995, 1]
        trans = { duration: 3.6, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'sleep') {
        // Peaceful deep sleep breathing
        anim.y = [0, -1.5, 0]
        anim.scaleY = [1, 1.03, 1]
        anim.scaleX = [1, 0.99, 1]
        trans = { duration: 4.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'listen') {
        // Attentive listening perk & gentle head tilt toward audio
        anim.rotate = [-3, -1, -3.5, -1.5, -3]
        anim.y = [0, 1.2, -1.5, 0.5, 0]
        anim.scaleY = [1, 1.02, 0.99, 1.015, 1]
        trans = { duration: 2.6, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'think') {
        // Thoughtful sway
        anim.rotate = [-2.5, 2.5, -2.5]
        anim.y = [0, -1.8, 0]
        trans = { duration: 1.8, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'alert') {
        // Alert entrance hop onto screen: snap zoom with spring settling
        anim.scale = [0.72, 1.08, 0.98, 1]
        anim.y = [-8, 0]
        trans = { duration: 0.75, ease: [0.34, 1.56, 0.64, 1] }
      } else if (activePose === 'relief') {
        // "Phew!" relieved breath loop
        anim.y = [0, -3, 0.6, 0]
        anim.scaleY = [1, 1.035, 0.988, 1]
        anim.scaleX = [1, 0.992, 1.01, 1]
        trans = { duration: 2.8, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'catch') {
        // Reaching forward to catch dropped document
        anim.y = [0, -6, 1.5, -4, 0]
        anim.scale = [1, 1.05, 0.988, 1.03, 1]
        anim.rotate = [0, -1.5, 1.5, -0.8, 0]
        trans = { duration: 1.8, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'write') {
        // Scribing/writing rhythmic micro-loop
        anim.y = [0, 1.6, -0.3, 1.8, 0.3, 0]
        anim.rotate = [0, -1, 0.8, -0.8, 0.5, 0]
        anim.scaleY = [1, 0.99, 1.008, 0.992, 1]
        trans = { duration: 1.6, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'wave') {
        // Continuous lively friendly hand wave tilt
        anim.rotate = [0, 7, -3, 7, -3, 0]
        anim.y = [0, -2.5, 0]
        trans = { duration: 1.5, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'off') {
        anim.opacity = 0.55
        anim.scaleY = 0.95
        trans = soft
      }
    }

    return { figureAnimate: anim, figureTransition: trans }
  }, [activePose, reduced])

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
  const listenAura = 0.25 + Math.min(1, Math.max(0, audioLevel)) * 0.45
  const auraOpacity = activePose === 'alert' ? 0.65 : activePose === 'listen' ? listenAura : 0.4

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
      aria-label={`Satya 3D mascot, ${activePose}`}
    >
      {/* SVG Halo Aura Ring Behind 3D Character */}
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
          animate={{
            opacity: showAura ? auraOpacity : 0,
            scale: activePose === 'alert' && !reduced ? [1, 1.06, 1] : 1,
          }}
          transition={
            activePose === 'alert' && !reduced
              ? { duration: 1.0, repeat: Infinity, ease: 'easeInOut' }
              : { duration: 0.3 }
          }
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        />

        {/* Ambient SVG Accessories for Poses that Benefit from Extra Visual Flourish */}
        <motion.g
          id="accessories"
          animate={figureAnimate}
          transition={figureTransition}
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        >
          {activePose === 'sleep' ? (
            <Accessories pose="sleep" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : activePose === 'listen' ? (
            <Accessories pose="listen" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : activePose === 'relief' ? (
            <Accessories pose="relief" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : activePose === 'think' ? (
            <Accessories pose="think" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : null}
        </motion.g>
      </svg>

      {/* Centered 3D Blue Blob Character with Physics Transitions */}
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
          transformOrigin: '50% 50%',
        }}
      >
        <motion.img
          key={activePose}
          src={currentMascotSrc}
          alt={`Satya 3D Mascot - ${activePose}`}
          draggable={false}
          initial={
            activePose === 'alert'
              ? { scale: mascotBaseScale * 0.75, opacity: 0.9 }
              : { scale: mascotBaseScale * 0.97, opacity: 0.92 }
          }
          animate={{
            scale: mascotBaseScale,
            opacity: 1,
            x: activePose === 'sleep' ? 0 : activePose === 'write' ? lookX * 0.3 : lookX,
            y: activePose === 'sleep' ? 0 : activePose === 'write' ? Math.max(1.5, lookY * 0.3) : lookY,
          }}
          transition={
            activePose === 'alert'
              ? { duration: 0.75, ease: [0.34, 1.56, 0.64, 1] }
              : soft
          }
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'contain',
            pointerEvents: 'none',
            display: 'block',
            filter: 'drop-shadow(0 6px 14px rgba(20,16,40,0.22))',
          }}
        />
      </motion.div>
    </div>
  )
})

export default Mascot
