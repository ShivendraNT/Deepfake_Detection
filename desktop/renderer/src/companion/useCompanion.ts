/**
 * Companion state hook: consent, events, demo replay and drafts.
 *
 * The hook prefers the sandboxed Electron bridge. If the local FastAPI backend is not running it
 * falls back to the visibly-labelled local mock so the stage demo never shows a dead window.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type {
  Band,
  ClipboardCheck,
  CompanionApiClient,
  CompanionEvent,
  CompanionMode,
  CompanionSource,
  CompanionState,
  ConnectionStatus,
  DraftArtifact,
} from '../../../shared/contracts'
import { MODE_LABELS, SOURCE_LABELS } from '../../../shared/contracts'
import { createCompanionClient } from './CompanionApiClient'
import { MockCompanionClient } from './mockClient'
import { playChime } from './chime'

export const REFUSAL_SCRIPT =
  'I need to verify this through our registered callback process. I will get back to you.'

export interface CompanionStatus {
  mode: CompanionMode
  monitoring: boolean
  source: CompanionSource | null
  sourceLabel: string | null
  demo: boolean
  modeLabel: string | null
  band: Band | null
  sessionId: string | null
}

interface RequestHandlers {
  openConsent?: (source?: CompanionSource) => void
  demo?: (scenario?: string) => void
  toggleSleep?: () => void
  clipboard?: () => void
}

function statusFromState(state: CompanionState, previous?: CompanionStatus): CompanionStatus {
  return {
    mode: state.mode,
    monitoring: state.monitoring,
    source: state.source,
    sourceLabel: state.source_label,
    demo: state.demo,
    modeLabel: state.mode_label,
    band: previous?.band ?? null,
    sessionId: state.session_id,
  }
}

function initialStatus(): CompanionStatus {
  return {
    mode: 'SLEEP',
    monitoring: false,
    source: null,
    sourceLabel: null,
    demo: false,
    modeLabel: null,
    band: null,
    sessionId: null,
  }
}

export function useCompanion() {
  const mockRef = useRef<MockCompanionClient | null>(null)
  const [client, setClient] = useState<CompanionApiClient>(() => createCompanionClient())
  const [status, setStatus] = useState<CompanionStatus>(initialStatus)
  const [event, setEvent] = useState<CompanionEvent | null>(null)
  const [alert, setAlert] = useState<CompanionEvent | null>(null)
  const [history, setHistory] = useState<CompanionEvent[]>([])
  const [lastDraft, setLastDraft] = useState<DraftArtifact | null>(null)
  const [connection, setConnection] = useState<ConnectionStatus>(() => ({
    connected: false,
    backendUrl: window.satyapan ? 'connecting' : 'local mock',
    mock: !window.satyapan,
  }))
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ text: string; tone: 'info' | 'warn' | 'error' } | null>(null)
  const [consentOpen, setConsentOpen] = useState(false)
  const [consentSource, setConsentSource] = useState<CompanionSource>('demo_replay')
  const [dismissed, setDismissed] = useState(false)
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem('satya.sound') !== 'off')
  const [clipboard, setClipboard] = useState<ClipboardCheck | null>(null)
  const [ready, setReady] = useState(false)

  const soundRef = useRef(soundOn)
  soundRef.current = soundOn
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handlersRef = useRef<RequestHandlers>({})

  const notify = useCallback(
    (text: string, tone: 'info' | 'warn' | 'error' = 'info') => {
      setToast({ text, tone })
      if (toastTimer.current) clearTimeout(toastTimer.current)
      toastTimer.current = setTimeout(() => setToast(null), 5200)
    },
    [],
  )

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current)
    },
    [],
  )

  const applyState = useCallback((state: CompanionState) => {
    setStatus((previous) => statusFromState(state, previous))
  }, [])

  const applyEvent = useCallback((incoming: CompanionEvent) => {
    setEvent(incoming)
    if (incoming.type === 'alert.raised') setAlert(incoming)
    setDismissed(false)
    setStatus((previous) => ({
      mode: incoming.payload.state,
      monitoring: incoming.payload.monitoring,
      source: incoming.payload.source ?? previous.source,
      sourceLabel: previous.sourceLabel,
      demo: incoming.payload.demo,
      modeLabel: incoming.payload.mode_label,
      band: incoming.payload.band ?? previous.band,
      sessionId: incoming.session_id ?? previous.sessionId,
    }))
    setHistory((current) => [incoming, ...current].slice(0, 40))
    if (incoming.type === 'alert.raised' && soundRef.current) playChime('alert')
    if (incoming.type === 'draft.ready' && soundRef.current) playChime('soft')
  }, [])

  // ---------------------------------------------------------------- connection lifecycle
  useEffect(() => {
    let cancelled = false
    void client.connect({
      onEvent: applyEvent,
      onConnection: (next) => {
        setConnection(next)
      },
      onTrayRequest: (request) => {
        const handlers = handlersRef.current
        if (request.kind === 'start') handlers.openConsent?.(request.source)
        if (request.kind === 'demo') handlers.demo?.(request.scenario)
        if (request.kind === 'clipboard') {
          setClipboard(request.check)
          if (request.check.suspicious) {
            notify(`Clipboard check: ${request.check.matches.join(', ')}`, 'warn')
          } else {
            notify('Clipboard check complete — no strong pattern found.', 'info')
          }
        }
      },
      onHotkey: (action) => {
        const handlers = handlersRef.current
        if (action === 'sleep-toggle') handlers.toggleSleep?.()
        if (action === 'demo') handlers.demo?.('beneficiary_change')
        if (action === 'clipboard') handlers.clipboard?.()
      },
    })

    void client
      .getState()
      .then((state) => {
        if (cancelled) return
        setStatus(statusFromState(state))
        setReady(true)
      })
      .catch(() => {
        if (cancelled) return
        // Backend not up (or the bridge is absent): switch to the clearly-labelled mock.
        const mock = mockRef.current ?? new MockCompanionClient()
        mockRef.current = mock
        setConnection({ connected: false, backendUrl: 'local mock', mock: true })
        setClient(mock)
        setReady(true)
      })

    return () => {
      cancelled = true
      client.disconnect()
    }
  }, [applyEvent, client, notify])

  // ---------------------------------------------------------------- actions
  const start = useCallback(
    async (source: CompanionSource, label?: string) => {
      setBusy(true)
      try {
        const result = await client.startSession(source, label ?? SOURCE_LABELS[source])
        applyState(result.state)
        setConsentOpen(false)
        notify(
          source === 'demo_replay'
            ? 'Replay session ready. Nothing is captured.'
            : 'Consent recorded. Monitoring is visibly on.',
          'info',
        )
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Could not start the session', 'error')
      } finally {
        setBusy(false)
      }
    },
    [applyState, client, notify],
  )

  const stop = useCallback(async () => {
    setBusy(true)
    try {
      const result = await client.stopSession()
      applyState(result.state)
      notify('Stopped. Capture is off.', 'info')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not stop the session', 'error')
    } finally {
      setBusy(false)
    }
  }, [applyState, client, notify])

  const demo = useCallback(
    async (scenario = 'beneficiary_change') => {
      setBusy(true)
      try {
        const result = await client.command('demo.replay', { scenario })
        applyState(result.state)
        notify('DEMO REPLAY — NOT LIVE CAPTURE', 'warn')
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Replay failed', 'error')
      } finally {
        setBusy(false)
      }
    },
    [applyState, client, notify],
  )

  const hide = useCallback(async () => {
    try {
      if (client.hide) {
        await client.hide()
      } else {
        await client.command('ui.hide')
      }
      setStatus((previous) => ({
        ...previous,
        mode: 'SLEEP',
        monitoring: false,
        sessionId: null,
      }))
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not hide', 'error')
    }
  }, [client, notify])

  const disable = useCallback(async () => {
    try {
      const result = await client.command('ui.disable')
      applyState(result.state)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not disable', 'error')
    }
  }, [applyState, client, notify])

  const draft = useCallback(
    async (kind: 'section63' | 'helpline_1930') => {
      setBusy(true)
      try {
        const workspace = await client.workspace()
        const artifact = await client.draft(kind, workspace.case_id)
        setLastDraft(artifact)
        setStatus((previous) => ({ ...previous, mode: 'SCRIBE', monitoring: false }))
        notify('Draft ready — MANUAL_ONLY, human review required.', 'info')
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Could not create the draft', 'error')
      } finally {
        setBusy(false)
      }
    },
    [client, notify],
  )

  const openWorkspace = useCallback(async () => {
    try {
      await client.openWorkspace?.()
    } catch {
      notify('Could not open the details window.', 'error')
    }
  }, [client, notify])

  const copyRefusal = useCallback(async () => {
    try {
      if (client.copyText) await client.copyText(REFUSAL_SCRIPT)
      else await navigator.clipboard.writeText(REFUSAL_SCRIPT)
      notify('Refusal script copied. It discloses nothing internal.', 'info')
    } catch {
      notify('Copy failed. The script is shown below.', 'warn')
    }
  }, [client, notify])

  const checkClipboard = useCallback(async () => {
    try {
      if (client.checkClipboard) {
        const check = await client.checkClipboard()
        setClipboard(check)
        notify(
          check.suspicious
            ? `Clipboard: ${check.matches.join(', ')}`
            : 'Clipboard: no strong pattern found.',
          check.suspicious ? 'warn' : 'info',
        )
      } else {
        notify('Clipboard check needs the desktop app.', 'warn')
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Clipboard check failed', 'error')
    }
  }, [client, notify])

  const openConsent = useCallback((source: CompanionSource = 'demo_replay') => {
    setConsentSource(source)
    setConsentOpen(true)
  }, [])

  const toggleSound = useCallback(() => {
    setSoundOn((current) => {
      localStorage.setItem('satya.sound', current ? 'off' : 'on')
      return !current
    })
  }, [])

  const toggleSleep = useCallback(async () => {
    if (status.mode === 'ACTIVE' || status.monitoring) await stop()
    else openConsent()
  }, [openConsent, status.mode, status.monitoring, stop])

  handlersRef.current = {
    openConsent: (source) => openConsent(source ?? 'demo_replay'),
    demo: (scenario) => void demo(typeof scenario === 'string' ? scenario : 'beneficiary_change'),
    toggleSleep: () => void toggleSleep(),
    clipboard: () => void checkClipboard(),
  }

  const modeLabel = MODE_LABELS[status.mode]

  return useMemo(
    () => ({
      ready,
      status,
      modeLabel,
      event,
      alert,
      history,
      lastDraft,
      connection,
      busy,
      toast,
      consentOpen,
      consentSource,
      dismissed,
      soundOn,
      clipboard,
      start,
      stop,
      demo,
      hide,
      disable,
      draft,
      openWorkspace,
      copyRefusal,
      checkClipboard,
      openConsent,
      closeConsent: () => setConsentOpen(false),
      setConsentSource,
      dismiss: () => setDismissed(true),
      restore: () => setDismissed(false),
      toggleSound,
      toggleSleep,
      notify,
      quit: () => void window.satyapan?.quit(),
    }),
    [
      ready,
      status,
      modeLabel,
      event,
      alert,
      history,
      lastDraft,
      connection,
      busy,
      toast,
      consentOpen,
      consentSource,
      dismissed,
      soundOn,
      clipboard,
      start,
      stop,
      demo,
      hide,
      disable,
      draft,
      openWorkspace,
      copyRefusal,
      checkClipboard,
      openConsent,
      setConsentSource,
      toggleSound,
      toggleSleep,
      notify,
    ],
  )
}
