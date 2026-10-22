import { motion, useReducedMotion } from 'framer-motion'

import type { MascotMood } from '../../../shared/contracts'

const EYE_RY: Record<MascotMood, number> = {
  sleepy: 0.9,
  attentive: 4.2,
  focused: 2.4,
  calm_alert: 3.2,
  writing: 1.6,
  off: 0.8,
}

const EYE_X: Record<MascotMood, number> = {
  sleepy: 0,
  attentive: 0.6,
  focused: 0,
  calm_alert: 0,
  writing: -0.4,
  off: 0,
}

const MOUTH: Record<MascotMood, string> = {
  sleepy: 'M86 118 Q100 122 114 118',
  attentive: 'M86 114 Q100 126 114 114',
  focused: 'M89 118 Q100 121 111 118',
  calm_alert: 'M88 120 L112 120',
  writing: 'M88 119 Q100 123 112 119',
  off: 'M88 120 Q100 114 112 120',
}

const AURA: Record<MascotMood, string> = {
  sleepy: '#2a6f66',
  attentive: '#5ee9b8',
  focused: '#6fc6ff',
  calm_alert: '#ffc35c',
  writing: '#b9a7ff',
  off: '#3a4650',
}

export interface MascotProps {
  mood: MascotMood
  size?: number
  alert?: boolean
}

export default function Mascot({ mood, size = 188, alert = false }: MascotProps) {
  const reduced = useReducedMotion()
  const duration = reduced ? 0 : 4.2
  const aura = AURA[mood]
  const blinking = mood === 'attentive' || mood === 'focused'

  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      role="img"
      aria-label={`Satya mascot, ${mood.replace('_', ' ')}`}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: reduced ? 0 : 0.5, ease: 'easeOut' }}
    >
      <defs>
        <radialGradient id="aura" cx="50%" cy="45%" r="50%">
          <stop offset="0%" stopColor={aura} stopOpacity="0.28" />
          <stop offset="65%" stopColor={aura} stopOpacity="0.06" />
          <stop offset="100%" stopColor={aura} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="body" x1="30%" y1="10%" x2="70%" y2="92%">
          <stop offset="0%" stopColor="#183540" />
          <stop offset="55%" stopColor="#10222b" />
          <stop offset="100%" stopColor="#0a151c" />
        </linearGradient>
        <linearGradient id="rim" x1="20%" y1="0%" x2="80%" y2="100%">
          <stop offset="0%" stopColor={aura} stopOpacity="0.9" />
          <stop offset="100%" stopColor={aura} stopOpacity="0.16" />
        </linearGradient>
        <filter id="soft-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <circle cx="100" cy="102" r="94" fill="url(#aura)" />

      <motion.circle
        cx="100"
        cy="100"
        r="78"
        fill="none"
        stroke={aura}
        strokeOpacity="0.18"
        strokeWidth="1"
        animate={{ r: reduced ? 78 : [76, 82, 76], opacity: [0.25, 0.05, 0.25] }}
        transition={{ duration: 6, repeat: reduced ? 0 : Infinity, ease: 'easeInOut' }}
      />

      <motion.g
        animate={
          reduced
            ? undefined
            : mood === 'sleepy'
              ? { y: [0, 2.5, 0] }
              : mood === 'calm_alert'
                ? { scale: [1, 1.018, 1] }
                : { y: [0, -2, 0] }
        }
        transition={{ duration, repeat: reduced ? 0 : Infinity, ease: 'easeInOut' }}
        style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
      >
        <path
          d="M100 18 L154 38 V92 C154 129 130 157 100 176 C70 157 46 129 46 92 V38 Z"
          fill="url(#body)"
          stroke="url(#rim)"
          strokeWidth="1.4"
        />
        <path
          d="M100 27 L146 44 V92 C146 124 126 148 100 165 C74 148 54 124 54 92 V44 Z"
          fill="none"
          stroke={aura}
          strokeOpacity="0.12"
          strokeWidth="1"
        />

        {alert && (
          <motion.circle
            cx="100"
            cy="100"
            r="64"
            fill="none"
            stroke={aura}
            strokeWidth="1.4"
            strokeDasharray="3 9"
            animate={reduced ? undefined : { rotate: 360 }}
            transition={{ duration: 16, repeat: Infinity, ease: 'linear' }}
            style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
          />
        )}

        <g
          className={blinking ? 'animate-soft-blink' : undefined}
          style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
        >
          <motion.ellipse
            cx={76}
            cy={88}
            rx={6.4}
            fill="#eafff8"
            animate={{ ry: EYE_RY[mood], cx: 76 + EYE_X[mood] }}
            transition={{ duration: reduced ? 0 : 0.45, ease: 'easeOut' }}
          />
          <motion.ellipse
            cx={124}
            cy={88}
            rx={6.4}
            fill="#eafff8"
            animate={{ ry: EYE_RY[mood], cx: 124 + EYE_X[mood] }}
            transition={{ duration: reduced ? 0 : 0.45, ease: 'easeOut' }}
          />
          {(mood === 'attentive' || mood === 'focused' || mood === 'calm_alert') && (
            <>
              <motion.circle
                cx={77}
                cy={89}
                r={2.2}
                fill="#0a1218"
                animate={{ cx: reduced ? 77 : [77, 79, 77] }}
                transition={{ duration: 7, repeat: reduced ? 0 : Infinity, ease: 'easeInOut' }}
              />
              <motion.circle
                cx={125}
                cy={89}
                r={2.2}
                fill="#0a1218"
                animate={{ cx: reduced ? 125 : [125, 127, 125] }}
                transition={{ duration: 7, repeat: reduced ? 0 : Infinity, ease: 'easeInOut' }}
              />
            </>
          )}
        </g>

        {mood === 'calm_alert' && (
          <motion.path
            d="M67 76 Q76 71 85 75 M115 75 Q124 71 133 76"
            fill="none"
            stroke={aura}
            strokeWidth="2"
            strokeLinecap="round"
            animate={{ opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 3.4, repeat: reduced ? 0 : Infinity }}
          />
        )}

        <motion.path
          d={MOUTH[mood]}
          fill="none"
          stroke="#bff5e4"
          strokeOpacity="0.75"
          strokeWidth="2.2"
          strokeLinecap="round"
          animate={{ d: MOUTH[mood] }}
          transition={{ duration: reduced ? 0 : 0.4 }}
        />

        {mood === 'sleepy' && (
          <motion.text
            x="142"
            y="58"
            fill="#8ff5d2"
            fontSize="11"
            fontWeight="600"
            animate={reduced ? undefined : { y: [58, 48], opacity: [0.7, 0] }}
            transition={{ duration: 2.8, repeat: Infinity, ease: 'easeOut' }}
          >
            z
          </motion.text>
        )}

        {mood === 'writing' && (
          <motion.path
            d="M142 120 L156 128"
            stroke="#b9a7ff"
            strokeWidth="3"
            strokeLinecap="round"
            animate={reduced ? undefined : { x: [0, 4, 0], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
      </motion.g>

      {[
        { cx: 34, cy: 70, delay: 0 },
        { cx: 166, cy: 112, delay: 1.4 },
        { cx: 52, cy: 148, delay: 2.6 },
      ].map((dot) => (
        <motion.circle
          key={`${dot.cx}-${dot.cy}`}
          cx={dot.cx}
          cy={dot.cy}
          r="1.6"
          fill={aura}
          animate={
            reduced ? undefined : { opacity: [0, 0.8, 0], y: [dot.cy, dot.cy - 8, dot.cy - 12] }
          }
          transition={{ duration: 5, delay: dot.delay, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}

      <g filter="url(#soft-glow)">
        <circle cx="157" cy="46" r="2.4" fill={aura} fillOpacity="0.85" />
        <circle cx="44" cy="118" r="1.7" fill={aura} fillOpacity="0.5" />
      </g>
    </motion.svg>
  )
}
