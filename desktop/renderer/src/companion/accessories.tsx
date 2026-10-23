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
    <motion.g initial={{ y: 14, opacity: 0.7 }} animate={{ y: 0, opacity: 1 }} transition={spring.snappy}>
      <path d="M151 145 Q166 135 156 116" fill="none" stroke={color.bodyDark} strokeWidth={13} strokeLinecap="round" />
      <ellipse cx={155} cy={113} rx={9} ry={8} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
      <path
        d="M146 91 C154 91 161 96 164 96 C164 114 159 126 146 134 C133 126 128 114 128 96 C131 96 138 91 146 91 Z"
        fill={color.verify}
        stroke={color.sticker}
        strokeWidth={3}
        strokeLinejoin="round"
      />
      <circle cx={146} cy={111} r={7} fill="none" stroke={color.sticker} strokeWidth={3} />
    </motion.g>
  )
}

function Glasses() {
  return (
    <g fill="none" stroke={color.ink} strokeWidth={2.5}>
      <circle cx={78} cy={103} r={13} />
      <circle cx={122} cy={103} r={13} />
      <path d="M91 103 L109 103" />
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
      {/* Feather quill loops over the parchment as Satya writes. */}
      <g transform="translate(133 137)">
        <path d="M-1 10 C-15 -3 -7 -18 8 -25 C9 -9 7 3 -1 10 Z" fill="#D7C9FF" stroke={color.sticker} strokeWidth={1.5} />
        <path d="M-1 10 L6 -19 M0 3 L-7 -2 M2 -3 L8 -8 M4 -10 L-2 -13" fill="none" stroke={color.write} strokeWidth={1.5} strokeLinecap="round" />
        <path d="M-1 10 L-7 22" fill="none" stroke="#6B5A9B" strokeWidth={2} strokeLinecap="round" />
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
      {/* Small parchment pad held across Satya's tummy. */}
      <g transform="translate(72 126) rotate(-5)">
        {/* Spiral wire ring binding at top */}
        <rect x={-2} y={-4} width={56} height={4} rx={2} fill="#7C6E9D" stroke="#FFFFFF" strokeWidth={1} />
        <circle cx={6} cy={-2} r={1.5} fill="#FFFFFF" />
        <circle cx={18} cy={-2} r={1.5} fill="#FFFFFF" />
        <circle cx={30} cy={-2} r={1.5} fill="#FFFFFF" />
        <circle cx={42} cy={-2} r={1.5} fill="#FFFFFF" />

        {/* Notepad yellow/cream paper page */}
        <rect
          x={0}
          y={0}
          width={52}
          height={38}
          rx={3}
          fill="#FFF4D6"
          stroke="#FFFFFF"
          strokeWidth={2.5}
        />
        {/* Red margin line */}
        <line x1={8} y1={2} x2={8} y2={36} stroke="#E7A6A0" strokeWidth={0.8} />

        {/* Ruled blue writing lines */}
        <line x1={11} y1={8} x2={46} y2={8} stroke="#B9ADD6" strokeWidth={1} strokeLinecap="round" />
        <line x1={11} y1={14} x2={46} y2={14} stroke="#B9ADD6" strokeWidth={1} strokeLinecap="round" />
        <line x1={11} y1={20} x2={46} y2={20} stroke="#B9ADD6" strokeWidth={1} strokeLinecap="round" />
        <line x1={11} y1={26} x2={40} y2={26} stroke="#B9ADD6" strokeWidth={1} strokeLinecap="round" />

        {/* Animated scribbling pen lines appearing on the pad */}
        <motion.path
          d="M12 14 L20 13 L28 14.5 L42 13.5"
          fill="none"
          stroke={color.write}
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
          d="M12 20 L23 19.5 L34 20.5"
          fill="none"
          stroke={color.write}
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
      <Glasses />
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
        <g fill="none" stroke={color.bodyDark} strokeWidth={13} strokeLinecap="round">
          <path d="M57 143 Q48 126 61 109" />
          <path d="M143 143 Q152 126 139 109" />
          <g fill={color.bodyDark} stroke={color.sticker} strokeWidth={3}>
            <ellipse cx={61} cy={108} rx={10} ry={9} />
            <ellipse cx={139} cy={108} rx={10} ry={9} />
          </g>
        </g>
      )
    }

    return (
      <motion.g
        animate={{ y: [0, -2, 0] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        fill="none"
        stroke={color.bodyDark}
        strokeWidth={13}
        strokeLinecap="round"
      >
        <path d="M57 143 Q48 126 61 109" />
        <path d="M143 143 Q152 126 139 109" />
        <g fill={color.bodyDark} stroke={color.sticker} strokeWidth={3}>
          <ellipse cx={61} cy={108} rx={10} ry={9} />
          <ellipse cx={139} cy={108} rx={10} ry={9} />
        </g>
      </motion.g>
    )
  }

  if (reducedMotion) {
    return (
      <g fill="none" stroke={color.bodyDark} strokeWidth={13} strokeLinecap="round">
        <path d="M151 145 Q162 127 155 108" />
        <ellipse cx={155} cy={106} rx={10} ry={9} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
      </g>
    )
  }

  return (
    <motion.g
      animate={{ rotate: [0, -20, 20, -20, 20, -20, 0] }}
      transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
      style={{ transformBox: 'view-box', transformOrigin: '150px 145px' }}
    >
      <path d="M151 145 Q162 127 155 108" fill="none" stroke={color.bodyDark} strokeWidth={13} strokeLinecap="round" />
      <ellipse cx={155} cy={106} rx={10} ry={9} fill={color.bodyDark} stroke={color.sticker} strokeWidth={3} />
    </motion.g>
  )
}

function ThinkDots({ reducedMotion }: { reducedMotion: boolean }) {
  const dots = [
    { cx: 86, cy: 38, r: 3.5, delay: 0 },
    { cx: 100, cy: 30, r: 4.5, delay: 0.15 },
    { cx: 114, cy: 38, r: 3.5, delay: 0.3 },
  ]
  if (reducedMotion) {
    return (
      <g fill={color.ink} opacity={0.6}>
        {dots.map((d, i) => (
          <circle key={i} cx={d.cx} cy={d.cy} r={d.r} />
        ))}
      </g>
    )
  }
  return (
    <g fill={color.ink}>
      {dots.map((d, i) => (
        <motion.circle
          key={i}
          cx={d.cx}
          cy={d.cy}
          r={d.r}
          animate={{ opacity: [0.3, 0.85, 0.3], scale: [0.85, 1.2, 0.85] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: d.delay, ease: 'easeInOut' }}
          style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
        />
      ))}
    </g>
  )
}

export function Accessories({ pose, audioLevel, reducedMotion }: AccessoriesProps) {
  return (
    <>
      {pose === 'sleep' ? <Zzz reducedMotion={reducedMotion} /> : null}
      {pose === 'listen' ? <Rings level={audioLevel} /> : null}
      {pose === 'think' ? <ThinkDots reducedMotion={reducedMotion} /> : null}
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
