/**
 * useSatya — the impure edge of the mascot brain.
 *
 * The reducer in `satyaMachine.ts` is pure and decides every pose and card. Everything that
 * touches the bridge, timers, files, the cursor or the clipboard lives here. File bytes stay in a
 * ref and never enter reducer state, logs or prompts. Bands only ever arrive inside backend events.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import {
  DEFAULT_SCOPES,
  type BridgeResult,
  type BubbleCard,
  type CaptureSourceKind,
  type CompanionEvent,
  type EvidenceResult,
  type SatyaSignal,
  type Scopes,
} from '../../../shared/contracts'
import type { Emote } from '../satya/engine'
import { api } from '../shared/api'
import { t, type Lang } from '../shared/copy'
import { decodeScopes } from './bubble/cards/ConsentCard'
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

export interface Quip {
  id: number
  text: string
}

const SAFE_REPLY = 'I’ll verify this through our registered process and call you back.'
const HINT_IGNORE_MS = 30 * 60_000

const CONSENT_CARD: BubbleCard = {
  kind: 'consent',
  id: 'card_consent',
  scopes: [],
  actions: [
    { id: 'start_watching', variant: 'primary' },
    { id: 'not_now', variant: 'ghost' },
  ],
}

const SCRIBE_SECTIONS = [
  { id: 'helpline_1930', title: '1930 helpline script' },
  { id: 'bank_fraud_desk', title: 'Bank fraud desk email' },
  { id: 'ncrp_portal', title: 'cybercrime.gov.in fields' },
  { id: 'cert_in', title: 'CERT-In incident email' },
  { id: 'bsa_s63_part_a', title: 'BSA §63 certificate, Part A' },
]

export interface SatyaController {
  state: SatyaState
  look: SatyaLook
  level: number
  quip: Quip | null
  lang: Lang
  onMenu: (action: MenuAction) => void
  onFileHover: (active: boolean) => void
  onFileDrop: (file: File) => void
  onPet: () => void
}

export interface SatyaOptions {
  /** Play a one-shot gesture on the sprite (wave, nod, startle…). */
  onEmote?: (emote: Emote) => void
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : typeof error === 'string' ? error : fallback
}

export function useSatya(options: SatyaOptions = {}): SatyaController {
  const [state, dispatch] = useReducer(satyaReducer, initialSatyaState)
  const stateRef = useRef(state)
  stateRef.current = state

  const [look, setLook] = useState<SatyaLook>({ dx: 0, dy: 0, near: false })
  const [level, setLevel] = useState(0)
  const [quip, setQuip] = useState<Quip | null>(null)
  const [lang, setLang] = useState<Lang>('en')
  const langRef = useRef<Lang>('en')
  langRef.current = lang

  const emoteRef = useRef(options.onEmote)
  emoteRef.current = options.onEmote
  const emote = useCallback((name: Emote) => emoteRef.current?.(name), [])

  const quipTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const quipId = useRef(0)
  const soundEnabled = useRef(false)
  const scopesRef = useRef<Scopes>({ ...DEFAULT_SCOPES })
  const consentedThisRun = useRef(false)
  const seenEvents = useRef(new Set<string>())
  const shownCard = useRef<string | null>(null)
  const pendingFile = useRef<File | null>(null)
  const submittingEvidence = useRef(false)
  const ignoredMeetings = useRef(new Map<string, number>())
  const actionRef = useRef<(actionId: string, cardId: string) => void>(() => undefined)
  const onMenuRef = useRef<(action: MenuAction) => void>(() => undefined)
  const signalSeq = useRef(0)

  const say = useCallback((key: string, vars?: Record<string, string>) => {
    const text = t(key, langRef.current, vars)
    quipId.current += 1
    setQuip({ id: quipId.current, text })
    if (quipTimer.current) clearTimeout(quipTimer.current)
    quipTimer.current = setTimeout(() => setQuip(null), Math.min(5200, 1800 + text.length * 45))
  }, [])

  /** Free-text quip (errors). */
  const notify = useCallback((text: string) => {
    quipId.current += 1
    setQuip({ id: quipId.current, text })
    if (quipTimer.current) clearTimeout(quipTimer.current)
    quipTimer.current = setTimeout(() => setQuip(null), 4200)
  }, [])

  useEffect(
    () => () => {
      if (quipTimer.current) clearTimeout(quipTimer.current)
    },
    [],
  )

  useEffect(() => {
    let cancelled = false
    void api
      .getPrefs()
      .then((prefs) => {
        if (cancelled) return
        soundEnabled.current = Boolean(prefs.sound ?? prefs.sounds)
        if (prefs.scopes) scopesRef.current = { ...DEFAULT_SCOPES, ...prefs.scopes }
        if (prefs.lang) setLang(prefs.lang)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const chime = useCallback((kind: 'alert' | 'soft') => {
    // Never during a call: the caller could hear it, and it would end up in the captions.
    if (soundEnabled.current && !stateRef.current.callId) playChime(kind)
  }, [])

  // ------------------------------------------------------------------ modes
  const setWatching = useCallback(
    async (scopes: Scopes) => {
      scopesRef.current = scopes
      try {
        const result = await api.setUserMode('WATCHING', scopes)
        if (!result.ok) {
          dispatch({
            type: 'SHOW_CARD',
            card: {
              kind: 'notice',
              id: `notice_backend_${Date.now()}`,
              tone: 'warn',
              title: 'notice.backend.title',
              body: 'notice.backend.body',
              actions: [{ id: 'dismiss', variant: 'ghost' }],
            },
          })
          return
        }
        consentedThisRun.current = true
        dispatch({ type: 'SET_MODE', mode: 'WATCHING' })
        emote('wave')
        say('quip.watching')
        void api.setPrefs({ scopes }).catch(() => undefined)
        const health = await api.getHealth?.()
        if (health?.ok) dispatch({ type: 'SIGNAL', signal: { kind: 'health', health: health.data } })
      } catch (error) {
        notify(errorText(error, 'Could not start watching.'))
      }
    },
    [emote, notify, say],
  )

  const setSleeping = useCallback(async () => {
    dispatch({ type: 'SET_MODE', mode: 'SLEEPING' })
    say('quip.sleep')
    try {
      await api.setUserMode('SLEEPING')
    } catch (error) {
      notify(errorText(error, 'Could not stop watching.'))
    }
  }, [notify, say])

  const setOff = useCallback(() => {
    say('quip.bye')
    dispatch({ type: 'SET_MODE', mode: 'OFF' })
    window.setTimeout(() => {
      void api
        .setUserMode('OFF')
        .then((result) => {
          if (!result.ok) notify(result.error)
        })
        .catch((error: unknown) => notify(errorText(error, 'Could not turn Satya off.')))
    }, 1500)
  }, [notify, say])

  // ------------------------------------------------------------------ calls, OOB, files, reports
  const startCall = useCallback(
    async (source: CaptureSourceKind = 'loopback') => {
      if (stateRef.current.userMode !== 'WATCHING') {
        dispatch({ type: 'SET_MODE', mode: stateRef.current.userMode, card: CONSENT_CARD })
        return
      }
      if (!api.startCall) {
        notify('Listening needs the desktop app. Nothing is being captured.')
        return
      }
      const result = await api.startCall(source)
      if (!result.ok) notify(result.error)
      else say('quip.listening')
    },
    [notify, say],
  )

  const stopCall = useCallback(async () => {
    const result = await api.stopCall?.()
    if (result && !result.ok) notify(result.error)
  }, [notify])

  const requestOob = useCallback(async () => {
    const caseId = stateRef.current.caseId
    if (!api.requestOob) {
      notify('Verification needs the desktop app. Nothing was sent.')
      return
    }
    if (!caseId) {
      notify('No open case to verify yet.')
      return
    }
    const result = await api.requestOob(caseId)
    if (!result.ok) notify(result.error)
    else emote('nod')
  }, [emote, notify])

  const submitPendingFile = useCallback(async () => {
    const file = pendingFile.current
    if (!file || !api.submitFile) {
      notify('File checks need the desktop app. Nothing left this laptop.')
      return
    }
    try {
      const bytes = await file.arrayBuffer()
      const result = await api.submitFile(file.name, file.type || 'application/octet-stream', bytes, stateRef.current.caseId)
      pendingFile.current = null
      if (!result.ok) {
        notify(result.error || 'Could not check that file.')
        return
      }
      for (const event of result.data.events ?? []) {
        if (seenEvents.current.has(event.event_id)) continue
        seenEvents.current.add(event.event_id)
        dispatch({ type: 'EVENT', event })
      }
    } catch (error) {
      notify(errorText(error, 'Could not hand the file over.'))
    }
  }, [notify])

  const submitScreenText = useCallback(
    async (cardId: string) => {
      const submit = (
        api as {
          submitLastScreenText?: () => Promise<BridgeResult<EvidenceResult>>
        }
      ).submitLastScreenText
      if (!submit) {
        notify('Open the Notebook to paste the text as evidence.')
        return
      }
      // One click = one submission. Without this, a double click consumed the text with the
      // first call and reported the second one as "gone".
      if (submittingEvidence.current) return
      submittingEvidence.current = true
      try {
        const result = await submit()
        if (!result.ok) {
          notify(result.error ?? 'Could not check the screen text.')
          return
        }
        for (const event of result.data.events ?? []) {
          if (seenEvents.current.has(event.event_id)) continue
          seenEvents.current.add(event.event_id)
          dispatch({ type: 'EVENT', event })
        }
        // The text is evidence now; close the finding so its button cannot be clicked again.
        api.hideCard(cardId)
        dispatch({ type: 'CARD_ACTION', cardId, actionId: 'dismiss' })
        notify('Checked properly. I saved it as evidence; the policy engine still decides the band.')
      } catch (error) {
        notify(errorText(error, 'Could not check the screen text.'))
      } finally {
        submittingEvidence.current = false
      }
    },
    [notify],
  )

  const prepareReport = useCallback(async () => {
    const caseId = stateRef.current.caseId
    if (!caseId || !api.reportPack) {
      void api.openWorkspace('reports')
      return
    }
    const id = `scribe_${Date.now()}`
    dispatch({
      type: 'SHOW_CARD',
      card: {
        kind: 'scribe',
        id,
        actions: [{ id: 'open_reports', variant: 'primary' }],
        sections: SCRIBE_SECTIONS.map((s, i) => ({ ...s, status: i === 0 ? 'writing' : 'pending' })),
      },
    })
    say('quip.writing')
    const result = await api.reportPack(caseId)
    if (!result.ok) {
      notify(result.error)
      return
    }
    // Tick the sections off one by one so the user sees what was prepared.
    result.data.sections.forEach((_, index) => {
      window.setTimeout(() => {
        dispatch({
          type: 'SHOW_CARD',
          card: {
            kind: 'scribe',
            id,
            actions: [{ id: 'open_reports', variant: 'primary' }],
            sections: result.data.sections.map((section, i) => ({
              id: section.id,
              title: section.title,
              status: i <= index ? 'done' : i === index + 1 ? 'writing' : 'pending',
            })),
          },
        })
        if (index === result.data.sections.length - 1) emote('celebrate')
      }, 450 * (index + 1))
    })
  }, [emote, notify, say])

  const scanScreen = useCallback(async () => {
    if (!api.scanScreen) {
      notify('Screen checks need the desktop app.')
      return
    }
    emote('notice')
    const result = await api.scanScreen()
    if (!result.ok) notify(result.error)
  }, [emote, notify])

  // ------------------------------------------------------------------ card actions
  const handleAction = useCallback(
    async (actionId: string, cardId: string) => {
      if (actionId.startsWith('start_watching')) {
        chime('soft')
        await setWatching(decodeScopes(actionId.split(':')[1]))
        return
      }
      switch (actionId) {
        case 'not_now':
          api.hideCard(cardId)
          return
        case 'not_this_call': {
          const meeting = stateRef.current.meeting
          if (meeting) ignoredMeetings.current.set(`${meeting.app}|${meeting.title}`, Date.now() + HINT_IGNORE_MS)
          api.hideCard(cardId)
          return
        }
        case 'listen_call':
          await startCall('loopback')
          return
        case 'stop_listening':
          await stopCall()
          return
        case 'no_thanks':
          pendingFile.current = null
          api.hideCard(cardId)
          return
        case 'check_it':
          emote('gulp')
          say('quip.gulp')
          await submitPendingFile()
          return
        case 'check_this':
          emote('gulp')
          await submitScreenText(cardId)
          return
        case 'verify':
        case 'verify_with_approver':
        case 'oob_verify':
          chime('alert')
          await requestOob()
          return
        case 'copy_safe_reply':
        case 'copy_reply': {
          const result = await api.copyText(SAFE_REPLY)
          notify(result.ok ? 'Safe reply copied. It gives away nothing internal.' : 'Copy failed. Read it from the card.')
          return
        }
        case 'liveness':
          dispatch({
            type: 'SHOW_CARD',
            card: { kind: 'liveness', id: `liveness_${Date.now()}`, actions: [{ id: 'dismiss', variant: 'ghost' }] },
          })
          return
        case 'call_1930':
          await api.openExternal('tel:1930')
          return
        case 'open_check':
          await api.openExternal('http://127.0.0.1:8000/check#money')
          return
        case 'open_notebook':
          await api.openWorkspace('now')
          return
        case 'open_reports':
        case 'open_scribe':
          await api.openWorkspace('reports')
          return
        case 'prepare':
        case 'prepare_report':
          await prepareReport()
          return
        case 'close':
        case 'dismiss':
        case 'ok':
          return
        default:
          return
      }
    },
    [chime, emote, notify, prepareReport, requestOob, say, setWatching, startCall, stopCall, submitPendingFile, submitScreenText],
  )
  actionRef.current = (actionId, cardId) => {
    void handleAction(actionId, cardId).catch((error: unknown) => notify(errorText(error, 'That did not work.')))
  }

  // ------------------------------------------------------------------ events & signals
  const handleEvent = useCallback(
    (event: CompanionEvent) => {
      if (seenEvents.current.has(event.event_id)) return
      seenEvents.current.add(event.event_id)
      const before = stateRef.current
      dispatch({ type: 'EVENT', event })
      if (before.userMode === 'SLEEPING' && event.type !== 'session.started') return
      switch (event.type) {
        case 'live.chips': {
          const known = new Set(before.chips.map((c) => c.code))
          const fresh = (event.payload.chips ?? []).find((c) => !known.has(c.code))
          if (fresh) {
            emote('notice')
            say('quip.hmm', { chip: t(`ask.${fresh.code}`, langRef.current) })
          }
          return
        }
        case 'alert.raised':
          say('quip.pause')
          chime('alert')
          return
        case 'oob.result':
          if (event.payload.oob?.outcome === 'approved') say('quip.safe')
          else emote('shake')
          return
        case 'call.stopped':
          if (before.callId) {
            dispatch({
              type: 'SHOW_CARD',
              card: {
                kind: 'toast',
                id: `toast_call_stopped_${event.event_id}`,
                text_key: 'notice.listening_stopped.title',
                tone: 'neutral',
              },
            })
          }
          return
        default:
          return
      }
    },
    [chime, emote, say],
  )

  const handleSignal = useCallback(
    (signal: SatyaSignal) => {
      signalSeq.current += 1
      const id = `${Date.now().toString(36)}_${signalSeq.current}`
      switch (signal.kind) {
        case 'level':
          setLevel(signal.value)
          return
        case 'hotkey':
          if (signal.action === 'stop') {
            if (stateRef.current.userMode === 'WATCHING') void setSleeping()
          } else if (signal.action === 'wake') {
            if (stateRef.current.userMode !== 'WATCHING') onMenuRef.current('watch')
          } else if (signal.action === 'clipboard') notify('The clipboard is empty.')
          else if (signal.action === 'listen') void startCall('loopback')
          else if (signal.action === 'replay') void startCall('replay')
          else if (signal.action === 'scan') void scanScreen()
          return
        case 'meeting': {
          dispatch({ type: 'SIGNAL', signal, id })
          const s = stateRef.current
          const meeting = signal.meeting
          if (!meeting || s.userMode !== 'WATCHING' || s.callId || !scopesRef.current.listen) return
          const key = `${meeting.app}|${meeting.title}`
          if ((ignoredMeetings.current.get(key) ?? 0) > Date.now()) return
          dispatch({ type: 'CALL_HINT', hintId: id, source: 'loopback', app: meeting.app })
          emote('perk')
          say('quip.meeting', { app: meeting.app })
          return
        }
        case 'text_check':
          dispatch({ type: 'SIGNAL', signal, id })
          if (signal.finding.suspicious) {
            emote('startle')
            say('quip.screen')
          } else if (signal.on_demand) {
            emote('nod')
          }
          return
        case 'capture':
          dispatch({ type: 'SIGNAL', signal, id })
          if (signal.state === 'error') emote('shake')
          return
        default:
          dispatch({ type: 'SIGNAL', signal, id })
      }
    },
    [emote, notify, say, scanScreen, setSleeping, startCall],
  )

  useEffect(() => {
    let cancelled = false
    const offEvent = api.onEvent(handleEvent)
    const offSignal = api.onSignal?.(handleSignal) ?? (() => undefined)
    const offAction = api.onCardAction(({ card_id, action_id }) => {
      if (stateRef.current.card?.id !== card_id) return
      dispatch({ type: 'CARD_ACTION', cardId: card_id, actionId: action_id })
      actionRef.current(action_id, card_id)
    })
    const offCursor = api.onCursor((position) => {
      setLook((previous) =>
        previous.dx === position.dx && previous.dy === position.dy && previous.near === position.near
          ? previous
          : position,
      )
    })

    void api
      .getState()
      .then((result) => {
        if (cancelled || !result.ok) return
        dispatch({ type: 'SET_MODE', mode: modeForCompanionState(result.data.mode) })
      })
      .catch(() => undefined)
    void api.getHealth?.().then((result) => {
      if (!cancelled && result.ok) dispatch({ type: 'SIGNAL', signal: { kind: 'health', health: result.data } })
    })

    return () => {
      cancelled = true
      offEvent()
      offSignal()
      offAction()
      offCursor()
    }
  }, [handleEvent, handleSignal])

  // Mirror the reducer's one card into the bubble window.
  useEffect(() => {
    const card = state.card
    if (!card) {
      if (shownCard.current) {
        api.hideCard()
        shownCard.current = null
      }
      return
    }
    const signature = JSON.stringify(card)
    if (signature !== shownCard.current) {
      api.showCard(card)
      shownCard.current = signature
    }
  }, [state.card])

  useEffect(() => {
    if (state.pose !== 'relief') return
    const guardId = state.card?.id ?? state.callId ?? undefined
    const timer = setTimeout(() => dispatch({ type: 'TIMER', name: 'relief', guardId }), 3200)
    return () => clearTimeout(timer)
  }, [state.pose, state.card?.id, state.callId])

  useEffect(() => {
    if (state.card?.kind !== 'toast') return
    const guardId = state.card.id
    const timer = setTimeout(() => dispatch({ type: 'TIMER', name: 'toast', guardId }), 4000)
    return () => clearTimeout(timer)
  }, [state.card])

  useEffect(() => {
    if (!state.callId) setLevel(0)
  }, [state.callId])

  // ------------------------------------------------------------------ menu & gestures
  const onMenu = useCallback(
    (action: MenuAction) => {
      const s = stateRef.current
      switch (action) {
        case 'watch':
          if (s.userMode === 'WATCHING') return
          if (consentedThisRun.current) {
            void setWatching(scopesRef.current)
            return
          }
          dispatch({ type: 'SET_MODE', mode: s.userMode === 'OFF' ? 'SLEEPING' : s.userMode, card: CONSENT_CARD })
          return
        case 'sleep':
          void setSleeping()
          return
        case 'off':
          setOff()
          return
        case 'listen':
          void startCall('loopback')
          return
        case 'stop_listening':
          void stopCall()
          return
        case 'scan':
          void scanScreen()
          return
        case 'report':
          void prepareReport()
          return
        case 'quit':
          void api.quit()
          return
        case 'notebook':
          void api.openWorkspace('now')
          return
        default:
          return
      }
    },
    [prepareReport, scanScreen, setOff, setSleeping, setWatching, startCall, stopCall],
  )

  onMenuRef.current = onMenu

  const onFileHover = useCallback(
    (active: boolean) => {
      const wasCatching = stateRef.current.pose === 'catch'
      dispatch({ type: 'FILE_HOVER', active })
      if (active && !wasCatching && stateRef.current.userMode === 'WATCHING') say('quip.drop')
    },
    [say],
  )

  const onFileDrop = useCallback((file: File) => {
    if (stateRef.current.userMode !== 'WATCHING') {
      dispatch({ type: 'SET_MODE', mode: stateRef.current.userMode, card: CONSENT_CARD })
      return
    }
    pendingFile.current = file
    dispatch({
      type: 'FILE_DROP',
      fileId: `file_${Date.now()}`,
      name: file.name,
      kind: fileKindOf(file.name, file.type),
    })
  }, [])

  const lastPetQuip = useRef(0)
  const onPet = useCallback(() => {
    if (Date.now() - lastPetQuip.current < 6000) return
    lastPetQuip.current = Date.now()
    say('quip.pet')
  }, [say])

  return { state, look, level, quip, lang, onMenu, onFileHover, onFileDrop, onPet }
}
