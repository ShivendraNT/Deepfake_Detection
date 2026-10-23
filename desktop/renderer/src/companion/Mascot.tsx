import { memo, useMemo } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

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

const soft = springTokens.soft

/**
 * Pixel-accurate, seamlessly matched procedural facial overlay.
 * Measured directly from desktop/renderer/src/assets/mascot_3d.png (600x600 scaled into 200x200 viewBox):
 * - Left Eye Center:  (64.5, 113), radius rx=23, ry=24
 * - Right Eye Center: (133.0, 115), radius rx=23, ry=24
 * - Mouth Center:     (99.5, 146), bounds ~ 20x15
 * - Skin Cyan Fill:   #44D5DE (exact match to base 3D spherical mesh)
 * - Ink / Line:       #0F172A (crisp dark outline)
 */
function FaceOverlay({
  pose,
  lookX,
  lookY,
  reduced,
}: {
  pose: Pose
  lookX: number
  lookY: number
  reduced: boolean
}) {
  return (
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
      {/* 1. SLEEP & OFF POSE: Overlay disabled because 3D image has built-in closed eyelids, rosy cheeks, snoozing bubble & ZZZ */}
      {false && (pose === 'sleep' || pose === 'off') && (
        <motion.g
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
        >
          {/* Eyelids covering open eyes */}
          <ellipse cx={64.5} cy={113} rx={25} ry={25} fill="#44D5DE" />
          <ellipse cx={133} cy={115} rx={25} ry={25} fill="#44D5DE" />
          {/* Cute curved sleeping lash arcs */}
          <path
            d="M44 113 Q64.5 125 85 113"
            fill="none"
            stroke="#0F172A"
            strokeWidth={4.5}
            strokeLinecap="round"
          />
          <path
            d="M112 115 Q133 127 154 115"
            fill="none"
            stroke="#0F172A"
            strokeWidth={4.5}
            strokeLinecap="round"
          />
          {/* Cute sleeping mouth */}
          <ellipse cx={99.5} cy={146} rx={18} ry={13} fill="#44D5DE" />
          <path
            d="M93 145 Q99.5 149 106 145"
            fill="none"
            stroke="#0F172A"
            strokeWidth={3.5}
            strokeLinecap="round"
          />
        </motion.g>
      )}

      {/* 2. RELIEF POSE: Overlay disabled because 3D asset has built-in cyber security cap, relieved eyes, puff & blush */}
      {false && pose === 'relief' && (
        <motion.g
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.15 }}
        >
          <ellipse cx={64.5} cy={113} rx={25} ry={25} fill="#44D5DE" />
          <ellipse cx={133} cy={115} rx={25} ry={25} fill="#44D5DE" />
          <path
            d="M43 118 Q64.5 101 86 118"
            fill="none"
            stroke="#0F172A"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <path
            d="M111 120 Q133 103 155 120"
            fill="none"
            stroke="#0F172A"
            strokeWidth={5}
            strokeLinecap="round"
          />
          {/* Extra pink happy blush glow */}
          <ellipse cx={38} cy={124} rx={11} ry={7} fill="#FF6B8B" opacity={0.6} />
          <ellipse cx={160} cy={126} rx={11} ry={7} fill="#FF6B8B" opacity={0.6} />
        </motion.g>
      )}

      {/* 3. THINK POSE: Overlay disabled because image already has built-in thinking brows, chin hand & expression */}
      {false && pose === 'think' && (
        <motion.g
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.18 }}
        >
          {/* Inquisitive brows */}
          <path
            d="M47 80 Q64.5 73 82 80"
            fill="none"
            stroke="#0F172A"
            strokeWidth={4.5}
            strokeLinecap="round"
          />
          <path
            d="M116 82 Q133 75 151 79"
            fill="none"
            stroke="#0F172A"
            strokeWidth={4.5}
            strokeLinecap="round"
          />
          {/* Thoughtful straight mouth */}
          <ellipse cx={99.5} cy={146} rx={18} ry={13} fill="#44D5DE" />
          <path
            d="M89 146 L110 146"
            fill="none"
            stroke="#0F172A"
            strokeWidth={4}
            strokeLinecap="round"
          />
        </motion.g>
      )}

      {/* 4. ALERT POSE: Overlay disabled because image already has built-in angry brows & shield */}
      {false && pose === 'alert' && (
        <motion.g
          initial={{ opacity: 0, y: -2 }}
          animate={{ opacity: 1, y: 0 }}
          transition={soft}
        >
          {/* Inward sharply angled brows over eyes */}
          <path
            d="M44 80 Q64.5 90 85 91"
            fill="none"
            stroke="#0F172A"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <path
            d="M154 82 Q133 92 112 93"
            fill="none"
            stroke="#0F172A"
            strokeWidth={5}
            strokeLinecap="round"
          />
          {/* Firm determined mouth */}
          <ellipse cx={99.5} cy={146} rx={18} ry={13} fill="#44D5DE" />
          <path
            d="M89 147 Q99.5 142 110 147"
            fill="none"
            stroke="#0F172A"
            strokeWidth={4.5}
            strokeLinecap="round"
          />
        </motion.g>
      )}

      {/* 5. CATCH POSE: Overlay disabled because 3D asset has built-in cyber security cap, focused brow & reaching paws */}
      {false && pose === 'catch' && (
        <motion.g
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={soft}
          style={{ transformBox: 'view-box', transformOrigin: '99.5px 146px' }}
        >
          <ellipse cx={99.5} cy={146} rx={18} ry={13} fill="#44D5DE" />
          <ellipse cx={99.5} cy={146} rx={8} ry={10} fill="#B91C1C" stroke="#0F172A" strokeWidth={3.5} />
          <circle cx={101.5} cy={144} r={3} fill="#F87171" />
        </motion.g>
      )}

      {/* 6. WRITE POSE: Overlay disabled because 3D asset has built-in cyber security cap, focused brow & notebook */}
      {false && pose === 'write' && (
        <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
          <circle cx={64.5} cy={113} r={23} fill="none" stroke="#0F172A" strokeWidth={3.5} />
          <circle cx={133} cy={115} r={23} fill="none" stroke="#0F172A" strokeWidth={3.5} />
          <line x1="87.5" y1="113" x2="110" y2="115" stroke="#0F172A" strokeWidth={3.5} />
        </motion.g>
      )}
    </svg>
  )
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
  const reduced = useReducedMotion() || Boolean(reducedMotion)
  const spec = POSES[activePose] ?? POSES.idle
  const renderedSize = typeof size === 'number' ? size : sizePx[size]

  // Mouse pupil tracking
  const lookX =
    look && look.near && !reduced
      ? Math.max(-5, Math.min(5, look.dx / 35))
      : spec.look?.x ?? 0
  const lookY =
    look && look.near && !reduced
      ? Math.max(-4, Math.min(4, look.dy / 35))
      : spec.look?.y ?? 0

  // Select dedicated high-res asset per state:
  let currentMascotSrc = mascot3dImg
  if (activePose === 'wave') {
    currentMascotSrc = mascotWaveImg
  } else if (activePose === 'alert') {
    currentMascotSrc = mascotAlertImg
  } else if (activePose === 'sleep' || activePose === 'off') {
    currentMascotSrc = mascotSleepImg
  } else if (activePose === 'relief') {
    currentMascotSrc = mascotReliefImg
  } else if (activePose === 'think') {
    currentMascotSrc = mascotThinkImg
  } else if (activePose === 'write') {
    currentMascotSrc = mascotWriteImg
  } else if (activePose === 'listen') {
    currentMascotSrc = mascotListenImg
  } else if (activePose === 'catch') {
    currentMascotSrc = mascotCatchImg
  }

  // Slight zoom-in adjustment for poses to match body proportions across states:
  const mascotBaseScale =
    activePose === 'wave'
      ? 1.15
      : activePose === 'relief'
      ? 1.15
      : 1

  // Stable animation configuration memoized per activePose so Framer Motion
  // NEVER cancels, restarts, or glitches animations on re-renders:
  const { figureAnimate, figureTransition } = useMemo(() => {
    const anim: any = {
      scaleY: 1,
      scaleX: 1,
      y: 0,
      rotate: 0,
      opacity: 1,
    }
    let trans: any = soft

    if (!reduced) {
      if (activePose === 'sleep' || activePose === 'idle') {
        // Completely stable and static: no 4-5s periodic breathing/fading pulsation
        anim.scaleY = 1
        anim.scaleX = 1
        anim.y = 0
        anim.opacity = 1
        trans = soft
      } else if (activePose === 'listen') {
        // Attentive listening perk & audio resonance:
        // Tilts cupped ear attentively toward audio with curious micro-nods and volume pulse
        anim.rotate = [-4, -1.5, -4.5, -2, -4]
        anim.y = [0, 1.2, -1.8, 0.6, 0]
        anim.scaleY = [1, 1.025, 0.985, 1.015, 1]
        anim.scaleX = [1, 0.985, 1.015, 0.99, 1]
        trans = { duration: 2.6, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'think') {
        // Thoughtful sway
        anim.rotate = [-3, 3, -3]
        anim.y = [0, -2, 0]
        trans = { duration: 1.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'alert') {
        // Alert zoom-into-screen entrance: smaller first, then zooms to normal size with spring snap
        anim.scale = [0.65, 1.1, 0.96, 1]
        anim.y = [-4, 0]
        trans = { duration: 0.85, ease: [0.34, 1.56, 0.64, 1] }
      } else if (activePose === 'relief') {
        // Soothing sigh relief breathing loop ("phew!" relaxing breath)
        anim.y = [0, -3.5, 0.8, 0]
        anim.scaleY = [1, 1.035, 0.985, 1]
        anim.scaleX = [1, 0.99, 1.01, 1]
        trans = { duration: 3.2, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'catch') {
        // Dynamic forward-reaching anticipation grab:
        // Poised hovering reach forward, ready to intercept dropped document
        anim.y = [0, -7, 2, -5, 0]
        anim.scale = [1, 1.055, 0.985, 1.035, 1]
        anim.rotate = [0, -1.8, 1.8, -1.0, 0]
        trans = { duration: 1.8, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'write') {
        // Diligent note-taking scribbling loop
        anim.y = [0, 1.8, -0.4, 2.0, 0.4, 1.6, 0]
        anim.rotate = [0, -1.2, 0.8, -1.0, 0.6, -0.4, 0]
        anim.scaleY = [1, 0.988, 1.008, 0.99, 1.005, 0.992, 1]
        trans = { duration: 1.6, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'wave') {
        // Friendly greeting hand wave motion: continuous lively tilt
        anim.rotate = [0, 8, -4, 8, -4, 0]
        anim.y = [0, -3, 0]
        trans = { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }
      } else if (activePose === 'off') {
        anim.opacity = 0.6
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
      {/* SVG Underlay for Aura Ring & Accessories (Zero Bottom Shadows!) */}
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
        {/* State Aura Halo Ring */}
        <motion.circle
          cx={100}
          cy={100}
          r={96}
          fill="none"
          stroke={auraColor}
          strokeWidth={4}
          animate={{
            opacity:
              activePose === 'alert' ||
              activePose === 'relief' ||
              activePose === 'listen' ||
              activePose === 'write' ||
              activePose === 'catch'
                ? 0.7
                : 0,
            scale: activePose === 'alert' ? [1, 1.06, 1] : 1,
          }}
          transition={{ duration: 1.0, repeat: activePose === 'alert' ? Infinity : 0 }}
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        />

        {/* Floating Accessories (Floating Zzz, Sound Rings, Pen & Notepad) */}
        <motion.g
          id="accessories"
          animate={figureAnimate}
          transition={figureTransition}
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        >
          {activePose !== 'sleep' && activePose !== 'write' && activePose !== 'relief' && activePose !== 'listen' && activePose !== 'catch' && (
            <Accessories pose={activePose} audioLevel={audioLevel} reducedMotion={reduced} />
          )}
        </motion.g>
      </svg>

      {/* Perfectly Centered, Full-Frame 3D Mascot Character */}
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
        {/* The Base High-Resolution 3D Character (No bottom shadow, fills frame) */}
        <motion.img
          key={activePose}
          src={currentMascotSrc}
          alt={`Satya 3D Mascot - ${activePose}`}
          draggable={false}
          initial={
            activePose === 'alert'
              ? { scale: 0.6 }
              : { scale: mascotBaseScale }
          }
          animate={{
            scale: mascotBaseScale,
            x: activePose === 'sleep' ? 0 : activePose === 'write' ? lookX * 0.3 : lookX,
            y: activePose === 'sleep' ? 0 : activePose === 'write' ? Math.max(1.5, lookY * 0.3) : lookY,
          }}
          transition={
            activePose === 'alert'
              ? { duration: 0.85, ease: [0.34, 1.56, 0.64, 1] }
              : soft
          }
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'contain',
            pointerEvents: 'none',
            display: 'block',
            opacity: 1,
          }}
        />

        {/* Dynamic Expressions Built from Scratch Aligned Directly on the 3D Eyes and Mouth */}
        <FaceOverlay
          pose={activePose}
          lookX={lookX}
          lookY={lookY}
          reduced={reduced}
        />
      </motion.div>
    </div>
  )
})

export default Mascot
