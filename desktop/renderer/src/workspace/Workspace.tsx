import { useCallback, useEffect, useRef, useState } from 'react'

import type { CaptionLine, CompanionEvent, CompanionState, HealthInfo } from '../../../shared/contracts'
import { api, onWorkspaceNavigate, workspaceReady } from '../shared/api'
import Sidebar, {
  TAB_IDS,
  TAB_TITLES,
  type TabId,
} from './Sidebar'
import { EMPTY_LIVE, mergeState, reduceLive, type LiveSnapshot } from './lib/live'
import { satyaStatus, statusTone } from './lib/status'
import CasesTab from './tabs/CasesTab'
import EvidenceTab from './tabs/EvidenceTab'
import NowTab from './tabs/NowTab'
import PrivacyTab from './tabs/PrivacyTab'
import ReportsTab from './tabs/ReportsTab'
import SettingsTab from './tabs/SettingsTab'
import TimelineTab from './tabs/TimelineTab'
import { FONT_SANS, surface, tone } from './ui/theme'

function tabFromUrl(): TabId {
  if (typeof window === 'undefined') return 'now'
  const requested = new URLSearchParams(window.location.search).get('tab')
  return requested && (TAB_IDS as string[]).includes(requested) ? (requested as TabId) : 'now'
}

/** Events that can change a case, its evidence or a report draft. */
const DATA_EVENTS = new Set([
  'session.started',
  'session.stopped',
  'state.changed',
  'call.started',
  'call.stopped',
  'analysis.completed',
  'evidence.received',
  'alert.raised',
  'case.updated',
  'oob.result',
  'draft.ready',
  'report.ready',
])

/**
 * The Notebook: a 1120x720 inspection window. It only relays what the companion API already
 * decided; no band is computed here.
 */
export default function Workspace(): JSX.Element {
  const [tab, setTab] = useState<TabId>(() => tabFromUrl())
  const [state, setState] = useState<CompanionState | null>(null)
  const [live, setLive] = useState<LiveSnapshot>(EMPTY_LIVE)
  const [events, setEvents] = useState<CompanionEvent[]>([])
  const [pendingCaseId, setPendingCaseId] = useState<string | null>(null)
  // Captions of the current call, in memory only (dropped when the call stops).
  const [captions, setCaptions] = useState<CaptionLine[]>([])
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [dataVersion, setDataVersion] = useState(0)
  const seenEvents = useRef<Set<string>>(new Set())
  const mounted = useRef(true)
  const stateFetchInFlight = useRef(false)
  const stateRefreshQueued = useRef(false)
  const stateRefreshTimer = useRef<number | null>(null)

  const refreshState = useCallback(async (): Promise<void> => {
    if (stateFetchInFlight.current) {
      stateRefreshQueued.current = true
      return
    }
    stateFetchInFlight.current = true
    try {
      const result = await api.getState()
      if (mounted.current && result.ok) setState(result.data)
    } finally {
      stateFetchInFlight.current = false
      if (stateRefreshQueued.current) {
        stateRefreshQueued.current = false
        void refreshState()
      }
    }
  }, [])

  const refreshHealth = useCallback(async (): Promise<void> => {
    const result = await api.getHealth?.()
    if (mounted.current && result?.ok) setHealth(result.data)
  }, [])

  const scheduleStateRefresh = useCallback((): void => {
    if (stateRefreshTimer.current !== null) window.clearTimeout(stateRefreshTimer.current)
    stateRefreshTimer.current = window.setTimeout(() => {
      stateRefreshTimer.current = null
      void refreshState()
    }, 120)
  }, [refreshState])

  useEffect(() => {
    mounted.current = true
    void refreshState()
    void refreshHealth()

    const stateTimer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') void refreshState()
    }, 3000)
    const healthTimer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') void refreshHealth()
    }, 5000)
    const onFocus = (): void => {
      void refreshState()
      void refreshHealth()
    }
    const onVisibility = (): void => {
      if (document.visibilityState === 'visible') onFocus()
    }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      mounted.current = false
      window.clearInterval(stateTimer)
      window.clearInterval(healthTimer)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
      if (stateRefreshTimer.current !== null) window.clearTimeout(stateRefreshTimer.current)
    }
  }, [refreshHealth, refreshState])

  useEffect(() => {
    const unsubscribe = api.onEvent((event) => {
      if (seenEvents.current.has(event.event_id)) return
      seenEvents.current.add(event.event_id)
      setEvents((current) => [event, ...current].slice(0, 200))
      setLive((current) => reduceLive(current, event))
      setState((current) => mergeState(current, event))
      if (DATA_EVENTS.has(event.type)) setDataVersion((version) => version + 1)
      if (
        event.type === 'call.started' ||
        event.type === 'call.stopped' ||
        event.type === 'session.stopped'
      ) {
        setCaptions([])
      }
      scheduleStateRefresh()
    })
    return unsubscribe
  }, [scheduleStateRefresh])

  useEffect(() => {
    const off =
      api.onSignal?.((signal) => {
        if (signal.kind === 'caption') setCaptions((lines) => [...lines, signal.line].slice(-200))
        if (signal.kind === 'health') setHealth(signal.health)
      }) ?? (() => undefined)
    return off
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const sync = (): void => setTab(tabFromUrl())
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])

  const selectTab = useCallback((next: TabId) => {
    setTab(next)
    if (typeof window === 'undefined') return
    try {
      const url = new URL(window.location.href)
      url.searchParams.set('view', 'workspace')
      url.searchParams.set('tab', next)
      window.history.replaceState(null, '', url)
    } catch {
      // A sandboxed renderer may block history updates; the tab still switches.
    }
  }, [])

  useEffect(() => {
    const unsubscribe = onWorkspaceNavigate((requested) => {
      if ((TAB_IDS as readonly string[]).includes(requested)) selectTab(requested as TabId)
    })
    workspaceReady()
    return unsubscribe
  }, [selectTab])

  const openCase = useCallback(
    (caseId: string | null) => {
      setPendingCaseId(caseId)
      selectTab('cases')
    },
    [selectTab],
  )

  const status = satyaStatus(state, live)
  const statusColor = tone[statusTone(status.key)]

  let content: JSX.Element
  switch (tab) {
    case 'cases':
      content = <CasesTab initialCaseId={pendingCaseId} refreshKey={dataVersion} />
      break
    case 'timeline':
      content = <TimelineTab events={events} refreshKey={dataVersion} />
      break
    case 'evidence':
      content = <EvidenceTab refreshKey={dataVersion} />
      break
    case 'reports':
      content = (
        <ReportsTab preferredCaseId={live.lastAlert?.caseId ?? null} refreshKey={dataVersion} />
      )
      break
    case 'privacy':
      content = <PrivacyTab state={state} />
      break
    case 'settings':
      content = <SettingsTab />
      break
    case 'now':
    default:
      content = (
        <NowTab
          state={state}
          live={live}
          onOpenCase={openCase}
          captions={captions}
          health={health}
          refreshKey={dataVersion}
          onRecheckHealth={() => void refreshHealth()}
        />
      )
      break
  }

  return (
    <div
      className={`flex h-[720px] w-[1120px] max-h-screen max-w-full overflow-hidden border ${surface.line} ${surface.paper} ${surface.text} sm:rounded-[18px]`}
      style={{ fontFamily: FONT_SANS }}
    >
      <Sidebar
        active={tab}
        onSelect={selectTab}
        statusKey={status.key}
        statusLabel={status.label}
        statusActive={status.active}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header
          className={`flex h-16 shrink-0 items-center justify-between gap-4 border-b px-6 ${surface.line}`}
        >
          <div className="min-w-0">
            <h1 className="text-[20px] font-semibold tracking-[-0.02em]">{TAB_TITLES[tab]}</h1>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            {state?.mode_label ? (
              <span
                className={`hidden max-w-[260px] truncate rounded-full border px-2.5 py-1 text-[12px] ${surface.line} ${surface.muted} md:inline`}
                title={state.mode_label}
              >
                {state.mode_label}
              </span>
            ) : null}
            <span
              className={`inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1 text-[12px] font-medium ${surface.line} ${surface.card}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${status.active ? 'animate-pulse' : ''}`}
                style={{ backgroundColor: statusColor }}
                aria-hidden="true"
              />
              {status.label}
            </span>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{content}</div>
      </main>
    </div>
  )
}
