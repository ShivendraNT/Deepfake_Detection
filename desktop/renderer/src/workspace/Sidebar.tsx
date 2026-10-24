import {
  Clock3,
  FileCheck2,
  FileText,
  FolderOpen,
  Lock,
  Radio,
  Settings,
  ShieldCheck,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { CompanionState, MascotMood } from '../../../shared/contracts'
import Mascot from '../companion/Mascot'
import { FONT_SANS, focusRing, surface, tone } from './ui/theme'

export type TabId = 'now' | 'cases' | 'timeline' | 'evidence' | 'reports' | 'privacy' | 'settings'

export interface TabDefinition {
  id: TabId
  label: string
  icon: LucideIcon
}

export const TABS: TabDefinition[] = [
  { id: 'now', label: 'Now', icon: Radio },
  { id: 'cases', label: 'Cases', icon: FolderOpen },
  { id: 'timeline', label: 'Timeline', icon: Clock3 },
  { id: 'evidence', label: 'Evidence', icon: FileCheck2 },
  { id: 'reports', label: 'Reports', icon: FileText },
  { id: 'privacy', label: 'Privacy', icon: ShieldCheck },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export const TAB_IDS: TabId[] = TABS.map((tab) => tab.id)

export const TAB_TITLES: Record<TabId, string> = {
  now: 'Now',
  cases: 'Cases',
  timeline: 'Timeline',
  evidence: 'Evidence',
  reports: 'Reports',
  privacy: 'Privacy',
  settings: 'Settings',
}

function moodFor(state: CompanionState | null, watching: boolean): MascotMood {
  if (!state) return watching ? 'attentive' : 'sleepy'
  switch (state.mode) {
    case 'ALERT':
      return 'calm_alert'
    case 'SCRIBE':
      return 'writing'
    case 'INVESTIGATING':
      return 'focused'
    case 'ACTIVE':
      return 'attentive'
    case 'DISABLED':
    case 'SLEEP':
    default:
      return watching ? 'attentive' : 'sleepy'
  }
}

export interface SidebarProps {
  active: TabId
  onSelect: (tab: TabId) => void
  state: CompanionState | null
  watching: boolean
}

export default function Sidebar({ active, onSelect, state, watching }: SidebarProps): JSX.Element {
  const mood = moodFor(state, watching)

  return (
    <aside
      className={`flex w-[224px] shrink-0 flex-col border-r ${surface.line} ${surface.sidebar}`}
      aria-label="Notebook navigation"
    >
      <div className="flex items-center gap-3 px-4 pb-4 pt-4">
        <div
          className={`grid h-10 w-10 shrink-0 place-items-center rounded-full border ${surface.line} ${surface.card}`}
          aria-hidden="true"
        >
          <Mascot mood={mood} size={28} />
        </div>
        <div className="min-w-0">
          <p className="truncate text-[14px] font-semibold tracking-[-0.01em]">Satya&apos;s Notebook</p>
          <p className={`mt-1 flex items-center gap-1.5 text-[12px] ${surface.muted}`}>
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: watching ? tone.watch : tone.slate }}
              aria-hidden="true"
            />
            {watching ? 'Watching' : 'Sleeping'}
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-2" aria-label="Notebook sections">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const selected = tab.id === active
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onSelect(tab.id)}
              aria-current={selected ? 'page' : undefined}
              className={`${focusRing} flex h-10 w-full items-center gap-2 rounded-[10px] px-2.5 text-left text-[13px] transition ${
                selected
                  ? `${surface.active} font-semibold shadow-[0_1px_2px_rgba(20,16,40,0.06)]`
                  : `${surface.muted} ${surface.hover}`
              }`}
            >
              <Icon
                size={16}
                strokeWidth={selected ? 2.2 : 1.9}
                aria-hidden="true"
                style={{ color: selected ? tone.watch : undefined }}
              />
              <span>{tab.label}</span>
              {selected ? (
                <span
                  className="ml-auto h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: tone.watch }}
                  aria-hidden="true"
                />
              ) : null}
            </button>
          )
        })}
      </nav>

      <div
        className={`border-t px-4 py-4 text-[12px] leading-relaxed ${surface.line} ${surface.muted}`}
        style={{ fontFamily: FONT_SANS }}
      >
        <p className="flex items-center gap-1.5">
          <Lock size={12} aria-hidden="true" /> Local only
        </p>
        <p className="mt-1">Bands come from satyapan.policy.</p>
      </div>
    </aside>
  )
}
