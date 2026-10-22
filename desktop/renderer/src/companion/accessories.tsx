import { motion } from 'framer-motion'

import type { Pose } from '../../../shared/contracts'
import { color, motion as spring } from '../shared/tokens'

export interface AccessoriesProps {
  pose: Pose
  audioLevel: number
  reducedMotion: boolean
}

const STAR_D = 'M0 -12 Q2 -2 12 0 Q2 2 0 12 Q-2 2 -12 0 Q-2 -2 0 -12 Z'

const ZS = [
  { size: 10, delay: 0 },
  { size: 12, delay: 0.8 },
  { size: 14, delay: 1.6 },
]

const SPARKLES = [
  { x: 56, y: 64, size: 10, delay: 0 },
  { x: 148, y: 58, size: 12, delay: 0.08 },
  { x: 154, y: 100, size: 8, delay: 0.16 },
]

function Zzz({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <>
      {ZS.map((z) => (
        <motion.text
          key={z.size}
          x={132}
          y={62}
          fill={color.ink}
          fillOpacity={0.4}
          fontSize={z.size}
          fontWeight={600}
          animate={
            reducedMotion
              ? undefined
              : { x: [132, 144], y: [62, 38], opacity: [1, 0] }
          }
          transition={
            reducedMotion
              ? undefined
              : { duration: 2.4, delay: z.delay, repeat: Infinity, ease: 'easeOut' }
          }
        >
          z
        </motion.text>
      ))}
    </>
  )
}

function Rings({ level, color: ringColor = color.watch }: { level: number; color?: string }) {
  const scale = 1 + 0.35 * level
  const opacity = 0.25 + 0.6 * level

  return (
    <>
      <motion.g
        animate={{ scale, opacity }}
        transition={spring.soft}
        style={{ transformBox: 'view-box', transformOrigin: '40px 90px' }}
      >
        <path
          d="M40 70 Q30 90 40 110"
          fill="none"
          stroke={ringColor}
          strokeWidth={3}
          strokeLinecap="round"
        />
        <path
          d="M40 70 Q30 90 40 110"
          transform="translate(40 90) scale(1.18) translate(-40 -90)"
          fill="none"
          stroke={ringColor}
          strokeWidth={3}
          strokeLinecap="round"
        />
      </motion.g>
      <motion.g
        animate={{ scale, opacity }}
        transition={spring.soft}
        style={{ transformBox: 'view-box', transformOrigin: '160px 90px' }}
      >
        <path
          d="M160 70 Q170 90 160 110"
          fill="none"
          stroke={ringColor}
          strokeWidth={3}
          strokeLinecap="round"
        />
        <path
          d="M160 70 Q170 90 160 110"
          transform="translate(160 90) scale(1.18) translate(-160 -90)"
          fill="none"
          stroke={ringColor}
          strokeWidth={3}
          strokeLinecap="round"
        />
      </motion.g>
    </>
  )
}

function Shield() {
  return (
    <g>
      <path
        d="M138 123 C146 123 151 127 153 127 C153 142 148 151 138 157 C128 151 123 142 123 127 C125 127 130 123 138 123 Z"
        fill={color.verify}
        stroke={color.sticker}
        strokeWidth={3}
        strokeLinejoin="round"
      />
      <circle cx={138} cy={140} r={7} fill="none" stroke={color.sticker} strokeWidth={3} />
    </g>
  )
}

function Glasses() {
  return (
    <g fill="none" stroke={color.ink} strokeWidth={2.5}>
      <circle cx={80} cy={112} r={12} />
      <circle cx={120} cy={112} r={12} />
      <path d="M92 112 L108 112" />
    </g>
  )
}

function Pen({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <motion.g
      animate={
        reducedMotion
          ? undefined
          : {
              rotate: [0, -12, 4, 0],
              x: [0, 2, -1, 0],
              y: [0, -2, 1, 0],
            }
      }
      transition={
        reducedMotion
          ? undefined
          : { duration: 0.8, repeat: Infinity, ease: 'easeInOut' }
      }
      style={{ transformBox: 'view-box', transformOrigin: '142px 146px' }}
    >
      {/* Sleek ballpoint pen held in right paw */}
      <g transform="translate(136 128) rotate(32)">
        {/* Pen body */}
        <rect x={-2.5} y={-16} width={5} height={20} rx={1} fill="#1E3A8A" stroke="#FFFFFF" strokeWidth={1.5} />
        {/* Silver pen grip */}
        <rect x={-2.5} y={0} width={5} height={6} fill="#E2E8F0" stroke="#FFFFFF" strokeWidth={1} />
        {/* Pen tip cone */}
        <polygon points="-2.5,6 2.5,6 0,11" fill="#0F172A" stroke="#FFFFFF" strokeWidth={1} />
        {/* Silver pen clip */}
        <rect x={2.5} y={-14} width={1.8} height={9} rx={0.5} fill="#CBD5E1" />
      </g>
    </motion.g>
  )
}

function Notepad({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <motion.g
      initial={{ scale: 0.9, y: 4 }}
      animate={{ scale: 1, y: 0 }}
      transition={spring.soft}
      style={{ transformBox: 'view-box', transformOrigin: '100px 150px' }}
    >
      {/* Little Notepad held in left paw / center */}
      <g transform="translate(72 130) rotate(-8)">
        {/* Spiral wire ring binding at top */}
        <rect x={-2} y={-4} width={34} height={4} rx={2} fill="#334155" stroke="#FFFFFF" strokeWidth={1} />
        <circle cx={4} cy={-2} r={1.5} fill="#FFFFFF" />
        <circle cx={11} cy={-2} r={1.5} fill="#FFFFFF" />
        <circle cx={18} cy={-2} r={1.5} fill="#FFFFFF" />
        <circle cx={25} cy={-2} r={1.5} fill="#FFFFFF" />

        {/* Notepad yellow/cream paper page */}
        <rect
          x={0}
          y={0}
          width={30}
          height={38}
          rx={3}
          fill="#FEF08A"
          stroke="#FFFFFF"
          strokeWidth={2.5}
        />
        {/* Red margin line */}
        <line x1={6} y1={2} x2={6} y2={36} stroke="#F87171" strokeWidth={0.8} />

        {/* Ruled blue writing lines */}
        <line x1={8} y1={8} x2={26} y2={8} stroke="#93C5FD" strokeWidth={1} strokeLinecap="round" />
        <line x1={8} y1={14} x2={26} y2={14} stroke="#93C5FD" strokeWidth={1} strokeLinecap="round" />
        <line x1={8} y1={20} x2={26} y2={20} stroke="#93C5FD" strokeWidth={1} strokeLinecap="round" />
        <line x1={8} y1={26} x2={22} y2={26} stroke="#93C5FD" strokeWidth={1} strokeLinecap="round" />

        {/* Animated scribbling pen lines appearing on the pad */}
        <motion.path
          d="M9 14 L14 13 L18 14.5 L24 13.5"
          fill="none"
          stroke="#1E3A8A"
          strokeWidth={1.4}
          strokeLinecap="round"
          animate={reducedMotion ? { opacity: 0.8 } : { opacity: [0, 0.9, 0.9, 0], pathLength: [0, 1, 1, 0] }}
          transition={
            reducedMotion
              ? undefined
              : { duration: 1.2, repeat: Infinity, repeatDelay: 0.4 }
          }
        />
        <motion.path
          d="M9 20 L15 19.5 L20 20.5"
          fill="none"
          stroke="#1E3A8A"
          strokeWidth={1.4}
          strokeLinecap="round"
          animate={reducedMotion ? { opacity: 0.8 } : { opacity: [0, 0.9, 0.9, 0], pathLength: [0, 1, 1, 0] }}
          transition={
            reducedMotion
              ? undefined
              : { duration: 1.2, delay: 0.4, repeat: Infinity, repeatDelay: 0.4 }
          }
        />
      </g>
    </motion.g>
  )
}

function WriteKit({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <>
      <Notepad reducedMotion={reducedMotion} />
      <Pen reducedMotion={reducedMotion} />
    </>
  )
}

function Sparkles({ reducedMotion }: { reducedMotion: boolean }) {
  if (reducedMotion) {
    return (
      <>
        {SPARKLES.map((star) => (
          <g key={`${star.x}-${star.y}`} transform={`translate(${star.x} ${star.y})`}>
            <path d={STAR_D} transform={`scale(${star.size / 12})`} fill={color.good} opacity={0.9} />
          </g>
        ))}
      </>
    )
  }

  return (
    <motion.g
      initial={{ opacity: 1 }}
      animate={{ opacity: [1, 1, 0] }}
      transition={{ duration: 1.2, times: [0, 0.4, 1], ease: 'easeOut' }}
    >
      {SPARKLES.map((star) => (
        <g key={`${star.x}-${star.y}`} transform={`translate(${star.x} ${star.y})`}>
          <motion.g
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ ...spring.snappy, delay: star.delay }}
            style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
          >
            <path d={STAR_D} transform={`scale(${star.size / 12})`} fill={color.good} />
          </motion.g>
        </g>
      ))}
    </motion.g>
  )
}

function Paws({
  mode,
  reducedMotion,
}: {
  mode: 'catch' | 'wave'
  reducedMotion: boolean
}) {
  if (mode === 'catch') {
    if (reducedMotion) {
      return (
        <>
          <ellipse cx={62} cy={150} rx={9} ry={8} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
          <ellipse cx={138} cy={150} rx={9} ry={8} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
        </>
      )
    }

    return (
      <>
        <motion.ellipse
          cx={62}
          cy={132}
          rx={11}
          ry={10}
          fill={color.bodyDark}
          stroke={color.sticker}
          strokeWidth={3}
          initial={{ y: 16, opacity: 0 }}
          animate={{ y: [0, -3, 0], opacity: 1 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.ellipse
          cx={138}
          cy={132}
          rx={11}
          ry={10}
          fill={color.bodyDark}
          stroke={color.sticker}
          strokeWidth={3}
          initial={{ y: 16, opacity: 0 }}
          animate={{ y: [0, -3, 0], opacity: 1 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      </>
    )
  }

  if (reducedMotion) {
    return (
      <ellipse cx={138} cy={150} rx={9} ry={8} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
    )
  }

  return (
    <motion.g
      animate={{ rotate: [0, 20, -20, 20, -20, 20, 0] }}
      transition={{ duration: 1.5, ease: 'easeInOut' }}
      style={{ transformBox: 'view-box', transformOrigin: '138px 158px' }}
    >
      <ellipse cx={138} cy={150} rx={9} ry={8} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
    </motion.g>
  )
}

export function Accessories({ pose, audioLevel, reducedMotion }: AccessoriesProps) {
  return (
    <>
      {pose === 'sleep' ? <Zzz reducedMotion={reducedMotion} /> : null}
      {pose === 'listen' ? <Rings level={audioLevel} /> : null}
      {pose === 'alert' ? <Shield /> : null}
      {pose === 'write' ? <WriteKit reducedMotion={reducedMotion} /> : null}
      {pose === 'relief' ? <Sparkles reducedMotion={reducedMotion} /> : null}
      {pose === 'catch' ? <Paws mode="catch" reducedMotion={reducedMotion} /> : null}
      {pose === 'wave' || pose === 'off' ? (
        <Paws mode="wave" reducedMotion={reducedMotion} />
      ) : null}
    </>
  )
}
