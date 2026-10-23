/**
 * useSatya — the impure edge of the mascot brain.
 *
 * The reducer in `satyaMachine.ts` is pure. Everything that touches the bridge, timers, files or
 * the cursor lives here. File bytes stay in a ref and never enter reducer state, logs or prompts.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import type {
  BubbleCard,
  CaptureSourceKind,
  CompanionBridge,
  CompanionEvent,
} from '../../../shared/contracts'
import { api } from '../shared/api'
import { playChime } from './chime'
import type { MenuAction } from './RadialMenu'
import {
  fileKindOf,
  initialSatyaState,
  modeForCompanionState,
  satyaReducer,
  type SatyaState,
} from './satyaMachine'

export interface SatyaLook {
  dx: number
  dy: number
  near: boolean
}

interface FinaleBridge {
  startCall?: (source?: CaptureSourceKind) => Promise<unknown>
  stopCall?: (callId?: string) => Promise<unknown>
  submitFile?: (
    name: string,
    mediaType: string,
    bytes: ArrayBuffer,
    caseId?: string | null,
  ) => Promise<unknown>
  requestOob?: (caseId: string) => Promise<unknown>
}

const finale = api as CompanionBridge & FinaleBridge

const SAFE_REPLY =
  'I’ll verify this through our registered process and call you back.'

const HINT_IGNORE_MS = 30 * 60_000

const CONSENT_CARD: BubbleCard = {
  kind: 'consent',
  id: 'card_consent',
  scopes: [
    'Notice calls (no recording)',
    'Listen to a call when you say yes',
    'Check files you give me',
  ],
  actions: [
    { id: 'start_watching', variant: 'primary' },
    { id: 'not_now', variant: 'ghost' },
  ],
}

export interface SatyaController {
  state: SatyaState
  look: SatyaLook
  notice: string | null
  onMenu: (action: MenuAction) => void
  onFileHover: (active: boolean) => void
  onFileDrop: (file: File) => void
  hintCall: (source: CaptureSourceKind) => void
}

export function useSatya(): SatyaController {
  const [state, dispatch] = useReducer(satyaReducer, initialSatyaState)
  const stateRef = useRef(state)
  stateRef.current = state

  const [look, setLook] = useState<SatyaLook>({ dx: 0, dy: 0, near: false })
  const [notice, setNotice] = useState<string | null>(null)
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const soundEnabled = useRef(false)

  const seenEvents = useRef(new Set<string>())
  const shownCard = useRef<string | null>(null)
  const pendingFile = useRef<File | null>(null)
  const ignoreHintsUntil = useRef(0)
  const actionRef = useRef<(actionId: string, cardId: string) => void>(() => undefined)

  const notify = useCallback((text: string) => {
    setNotice(text)
    if (noticeTimer.current) clearTimeout(noticeTimer.current)
    noticeTimer.current = setTimeout(() => setNotice(null), 3600)
  }, [])

  useEffect(
    () => () => {
      if (noticeTimer.current) clearTimeout(noticeTimer.current)
    },
    [],
  )

  useEffect(() => {
    let cancelled = false
    void api
      .getPrefs()
      .then((prefs) => {
        if (!cancelled) soundEnabled.current = Boolean(prefs.sound ?? prefs.sounds)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const setWatching = useCallback(async () => {
    try {
      const result = await api.setUserMode('WATCHING')
      if (!result.ok) {
        notify(result.error)
        return
      }
      dispatch({ type: 'SET_MODE', mode: 'WATCHING' })
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not start watching.')
    }
  }, [notify])

  const setSleeping = useCallback(async () => {
    dispatch({ type: 'SET_MODE', mode: 'SLEEPING' })
    try {
      await api.setUserMode('SLEEPING')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not stop watching.')
    }
  }, [notify])

  const setOff = useCallback(() => {
    dispatch({ type: 'SET_MODE', mode: 'OFF' })
    window.setTimeout(() => {
      try {
        void api
          .setUserMode('OFF')
          .then((result) => {
            if (!result.ok) notify(result.error)
          })
          .catch((error: unknown) => {
            notify(error instanceof Error ? error.message : 'Could not turn Satya off.')
          })
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Could not turn Satya off.')
      }
    }, 400)
  }, [notify])

  const startCall = useCallback(async () => {
    if (typeof finale.startCall !== 'function') {
      notify('Calls need the desktop bridge (F03). No audio is being captured.')
      return
    }
    try {
      await finale.startCall('replay')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not start the call check.')
    }
  }, [notify])

  const requestOob = useCallback(async () => {
    const caseId = stateRef.current.caseId
    if (typeof finale.requestOob !== 'function') {
      notify('Verification needs the desktop bridge (F03). Nothing was sent.')
      return
    }
    if (!caseId) {
      notify('No open case to verify yet.')
      return
    }
    try {
      await finale.requestOob(caseId)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not ask the approver.')
    }
  }, [notify])

  const submitPendingFile = useCallback(async () => {
    const file = pendingFile.current
    if (!file) return
    if (typeof finale.submitFile !== 'function') {
      notify('File checks need the desktop bridge (F03). Nothing left this laptop.')
      return
    }
    try {
      const bytes = await file.arrayBuffer()
      await finale.submitFile(
        file.name,
        file.type || 'application/octet-stream',
        bytes,
        stateRef.current.caseId,
      )
      pendingFile.current = null
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not hand the file over.')
    }
  }, [notify])

  const handleAction = useCallback(
    async (actionId: string, cardId: string) => {
      if (soundEnabled.current) {
        if (['start_watching', 'check_it', 'copy_reply', 'copy_safe_reply', 'open_reports'].includes(actionId)) {
          playChime('soft')
        } else if (['verify', 'verify_with_approver', 'oob_verify'].includes(actionId)) {
          playChime('alert')
        }
      }
      switch (actionId) {
        case 'start_watching':
          await setWatching()
          return
        case 'not_now':
        case 'not_this_call':
          ignoreHintsUntil.current = Date.now() + HINT_IGNORE_MS
          api.hideCard(cardId)
          return
        case 'listen_call':
          await startCall()
          return
        case 'no_thanks':
          pendingFile.current = null
          api.hideCard(cardId)
          return
        case 'check_it':
          await submitPendingFile()
          return
        case 'verify':
        case 'verify_with_approver':
        case 'oob_verify':
          await requestOob()
          return
        case 'copy_safe_reply':
        case 'copy_reply':
          try {
            const result = await api.copyText(SAFE_REPLY)
            if (!result.ok) throw new Error(result.error)
            notify('Safe reply copied. It discloses nothing internal.')
          } catch {
            notify('Copy failed. Read the safe reply from the card.')
          }
          return
        case 'open_notebook':
          try {
            await api.openWorkspace('now')
          } catch (error) {
            notify(error instanceof Error ? error.message : 'Could not open the Notebook.')
          }
          return
        case 'open_reports':
        case 'prepare_report':
        case 'open_scribe':
          try {
            await api.openWorkspace('reports')
          } catch (error) {
            notify(error instanceof Error ? error.message : 'Could not open Reports.')
          }
          return
        case 'close':
        case 'dismiss':
          api.hideCard(cardId)
          return
        default:
          return
      }
    },
    [notify, requestOob, setWatching, startCall, submitPendingFile],
  )
  actionRef.current = (actionId, cardId) => {
    void handleAction(actionId, cardId).catch((error: unknown) => {
      notify(error instanceof Error ? error.message : 'That action could not be completed.')
    })
  }

  useEffect(() => {
    let cancelled = false

    const offEvent = api.onEvent((event: CompanionEvent) => {
      if (seenEvents.current.has(event.event_id)) return
      seenEvents.current.add(event.event_id)
      dispatch({ type: 'EVENT', event })
    })

    const offAction = api.onCardAction(({ card_id, action_id }) => {
      if (stateRef.current.card?.id !== card_id) return
      dispatch({ type: 'CARD_ACTION', cardId: card_id, actionId: action_id })
      actionRef.current(action_id, card_id)
    })

    const offCursor = api.onCursor((position) => {
      setLook((previous) =>
        previous.dx === position.dx &&
        previous.dy === position.dy &&
        previous.near === position.near
          ? previous
          : position,
      )
    })

    void api
      .getState()
      .then((result) => {
        if (cancelled) return
        if (!result.ok) throw new Error(result.error)
        dispatch({ type: 'SET_MODE', mode: modeForCompanionState(result.data.mode) })
      })
      .catch(() => {
        if (cancelled) return
        notify('I cannot reach my brain, so I went to sleep.')
      })

    return () => {
      cancelled = true
      offEvent()
      offAction()
      offCursor()
    }
  }, [notify])

  useEffect(() => {
    const card = state.card
    if (!card) {
      if (shownCard.current) {
        api.hideCard()
        shownCard.current = null
      }
      return
    }
    const signature = `${card.id}:${JSON.stringify(card)}`
    if (signature !== shownCard.current) {
      api.showCard(card)
      shownCard.current = signature
    }
  }, [state.card])

  useEffect(() => {
    if (state.pose !== 'relief') return
    const guardId = state.card?.id ?? state.callId ?? undefined
    const timer = setTimeout(() => {
      dispatch({ type: 'TIMER', name: 'relief', guardId })
    }, 3000)
    return () => clearTimeout(timer)
  }, [state.pose, state.card?.id, state.callId])

  useEffect(() => {
    if (state.card?.kind !== 'toast') return
    const guardId = state.card.id
    const timer = setTimeout(() => {
      dispatch({ type: 'TIMER', name: 'toast', guardId })
    }, 4000)
    return () => clearTimeout(timer)
  }, [state.card])

  const onMenu = useCallback(
    (action: MenuAction) => {
      switch (action) {
        case 'watch':
          if (stateRef.current.userMode === 'WATCHING') return
          dispatch({
            type: 'SET_MODE',
            mode: stateRef.current.userMode === 'OFF' ? 'SLEEPING' : stateRef.current.userMode,
            card: CONSENT_CARD,
          })
          return
        case 'sleep':
          void setSleeping()
          return
        case 'off':
          setOff()
          return
        case 'notebook':
          void api.openWorkspace('now').catch((error: unknown) => {
            notify(error instanceof Error ? error.message : 'Could not open the Notebook.')
          })
          return
        default:
          return
      }
    },
    [notify, setSleeping, setOff],
  )

  const onFileHover = useCallback((active: boolean) => {
    dispatch({ type: 'FILE_HOVER', active })
  }, [])

  const onFileDrop = useCallback((file: File) => {
    pendingFile.current = file
    dispatch({
      type: 'FILE_DROP',
      fileId: `file_${Date.now()}`,
      name: file.name,
      kind: fileKindOf(file.name, file.type),
    })
  }, [])

  const hintCall = useCallback((source: CaptureSourceKind) => {
    if (Date.now() < ignoreHintsUntil.current) return
    if (stateRef.current.userMode !== 'WATCHING') return
    dispatch({ type: 'CALL_HINT', hintId: `hint_${Date.now()}`, source })
  }, [])

  return { state, look, notice, onMenu, onFileHover, onFileDrop, hintCall }
}
