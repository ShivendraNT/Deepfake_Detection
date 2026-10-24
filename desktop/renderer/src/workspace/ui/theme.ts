/**
 * Notebook-local design tokens.
 *
 * These mirror docs/finale/MASCOT_SPEC.md §2 exactly. They live inside the workspace because
 * shared/tokens.ts belongs to the mascot owner; the Notebook must keep working while that file
 * is still being written.
 */

export const FONT_SANS = 'Inter, "Noto Sans Devanagari", system-ui, sans-serif'
export const FONT_MONO =
  '"JetBrains Mono", "Noto Sans Devanagari", ui-monospace, SFMono-Regular, Menlo, monospace'

export const tone = {
  watch: '#1FB5A3',
  green: '#3CCB7F',
  amber: '#FFB020',
  coral: '#FF6B5E',
  write: '#9C8CFF',
  slate: '#8C96AA',
  ink: '#2A2238',
  paper: '#FBF8F3',
} as const

export const surface = {
  paper: 'bg-[#FBF8F3] dark:bg-[#16131F]',
  sidebar: 'bg-[#F3EEE6] dark:bg-[#1D1928]',
  card: 'bg-[#FFFCF7] dark:bg-[#1C1828]',
  inset: 'bg-[#F6F1E9] dark:bg-[#14111D]',
  line: 'border-[rgba(42,34,56,0.10)] dark:border-[rgba(237,232,245,0.10)]',
  text: 'text-[#2A2238] dark:text-[#EDE8F5]',
  muted: 'text-[#6B6478] dark:text-[#A8A0B8]',
  hover: 'hover:bg-[rgba(42,34,56,0.05)] dark:hover:bg-[rgba(237,232,245,0.06)]',
  active: 'bg-white dark:bg-[rgba(237,232,245,0.08)]',
} as const

export const card = `rounded-[18px] border ${surface.line} ${surface.card}`
export const inset = `rounded-[14px] border ${surface.line} ${surface.inset}`
export const focusRing =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1FB5A3] focus-visible:ring-offset-2 focus-visible:ring-offset-[#FBF8F3] dark:focus-visible:ring-offset-[#16131F]'

export const button = {
  primary: `${focusRing} inline-flex items-center justify-center gap-2 rounded-[10px] bg-[#1FB5A3] px-3 py-2 text-[13px] font-semibold text-white transition hover:bg-[#189684] active:translate-y-px`,
  outline: `${focusRing} inline-flex items-center justify-center gap-2 rounded-[10px] border ${surface.line} ${surface.card} px-3 py-2 text-[13px] font-medium transition ${surface.hover}`,
  ghost: `${focusRing} inline-flex items-center justify-center gap-2 rounded-[10px] px-2.5 py-2 text-[13px] font-medium transition ${surface.hover}`,
  danger: `${focusRing} inline-flex items-center justify-center gap-2 rounded-[10px] border border-[#FF6B5E]/40 bg-[#FF6B5E]/10 px-3 py-2 text-[13px] font-semibold text-[#C24136] transition hover:bg-[#FF6B5E]/20 dark:text-[#FF9A90]`,
} as const
