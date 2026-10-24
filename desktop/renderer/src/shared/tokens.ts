export const color = {
  body: '#E9B783',      // warm caramel
  bodyDark: '#D49A62',  // feet, paws
  tummy: '#FFF3E0',
  earInner: '#F6A79B',
  ink: '#2A2238',       // eyes, mouth, brows
  blush: '#FF8FA3',
  sticker: '#FFFFFF',   // outline so he reads on ANY wallpaper
  shadow: 'rgba(26,20,48,0.18)',
  // one accent per state — never two at once
  watch: '#1FB5A3',     // teal: watching / listening
  verify: '#FFB020',    // amber: VERIFY / alert
  hold: '#FF6B5E',      // coral: HOLD
  write: '#9C8CFF',     // lavender: scribe
  good: '#3CCB7F',      // green: relief / PASS
  sleep: '#8C96AA',     // slate: sleeping / off
} as const

export const ui = {
  light: { card: 'rgba(255,252,247,0.97)', text: '#2A2238', muted: '#6B6478',
           line: 'rgba(42,34,56,0.10)', paper: '#FBF8F3', sidebar: '#F3EEE6' },
  dark:  { card: 'rgba(28,24,40,0.96)', text: '#EDE8F5', muted: '#A8A0B8',
           line: 'rgba(237,232,245,0.10)', paper: '#16131F', sidebar: '#1D1928' },
  radius: { card: 18, button: 10, chip: 999 },
  shadow: '0 12px 32px rgba(20,16,40,0.22)',
  font: { sans: 'Inter, "Noto Sans Devanagari", system-ui, sans-serif',
          mono: '"JetBrains Mono", ui-monospace, monospace' },
} as const

export const motion = {
  soft:   { type: 'spring', stiffness: 220, damping: 18 },
  snappy: { type: 'spring', stiffness: 420, damping: 24 },
  gaze:   { stiffness: 240, damping: 18 },
  drag:   { stiffness: 450, damping: 22 },
  enter:  { duration: 0.18, ease: [0.2, 0.8, 0.2, 1] },
  exit:   { duration: 0.12, ease: 'easeIn' },
} as const

export const size = { S: 72, M: 96, L: 128 } as const   // rendered px; window stays 280×280
