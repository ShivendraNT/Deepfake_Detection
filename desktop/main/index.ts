/**
 * Electron main process for Satya.
 *
 * Main owns the operating-system side: four windows (mascot, bubble, Notebook, hidden capture),
 * the tray, hotkeys, the meeting notice (window names), on-device screen reading, and the capture
 * handshake. It turns OS facts into local *signals* for the renderers. The mascot's pure reducer
 * decides every card and pose; the backend's policy engine decides every band.
 *
 * Privacy rules this file enforces:
 *  - Satya launches asleep. Nothing is read or heard before a visible consent card is accepted.
 *  - Watching only notices (window names; on-screen text if that scope is on). Listening to a call
 *    needs a separate yes for that call, and stops when the call window closes.
 *  - The microphone is never opened. Call audio is the system output (the other person).
 *  - Sleep / Off / Quit / ⌘⇧. stop everything first. Any capture error fails closed.
 */

import { join } from 'node:path'

import { app, BrowserWindow, clipboard, globalShortcut, ipcMain, Menu, screen, shell } from 'electron'

if (process.platform === 'win32') {
  // Avoid DirectX DXGI duplicator timeouts on hybrid-GPU Windows laptops.
  app.commandLine.appendSwitch('disable-features', 'DxgiDuplicatorController')
}
if (process.platform === 'darwin') {
  // Chromium's macOS system-audio loopback for screen share (ScreenCaptureKit, macOS 13+).
  app.commandLine.appendSwitch(
    'enable-features',
    'MacLoopbackAudioForScreenShare,MacSckSystemAudioLoopbackOverride',
  )
}

for (const stream of [process.stdout, process.stderr]) {
  stream?.on('error', () => undefined)
}
process.on('uncaughtException', (err: NodeJS.ErrnoException) => {
  if (err?.code === 'EPIPE' || err?.code === 'EIO') return
  console.error('Uncaught Exception:', err)
})

import type {
  BridgeResult,
  BubbleCard,
  CallStarted,
  CaptureSourceKind,
  CompanionEvent,
  CompanionState,
  EvidenceResult,
  MeetingInfo,
  Prefs,
  SatyaSignal,
  ScreenFinding,
  Scopes,
  UserMode,
} from '../shared/contracts'
import { DEFAULT_SCOPES, USER_MODE_LABELS } from '../shared/contracts'
import { BackendClient, type LiveBusEvent } from './backend'
import { registerCapture, sendCaptureCommand, type CaptureStatus } from './capture'
import { registerIpc } from './ipc'
import { MeetingWatcher } from './meetings'
import { placeBubble, snapToEdges, type Rect } from './placement'
import { readPrefs, writePrefs } from './prefs'
import { captureScreenText } from './screen'
import { createTray } from './tray'
import {
  BUBBLE_MAX_HEIGHT,
  BUBBLE_MIN_HEIGHT,
  BUBBLE_WIDTH,
  createBubbleWindow,
  createCaptureWindow,
  createMascotWindow,
  createWorkspaceWindow,
  hideWindow,
  markAppQuitting,
  showCompanion as showMascotWindow,
  workAreaFor,
} from './windows'

const backend = new BackendClient()
const preloadPath = join(__dirname, '../preload/index.js')

const SCREEN_GUARD_MS = 7000
const SCREEN_ALERT_COOLDOWN_MS = 5 * 60_000
const SCREEN_TEXT_TTL_MS = 10 * 60_000

let mascotWindow: BrowserWindow | null = null
let bubbleWindow: BrowserWindow | null = null
let workspaceWindow: BrowserWindow | null = null
let captureWindow: BrowserWindow | null = null
let tray: ReturnType<typeof createTray> | null = null
let cursorTimer: ReturnType<typeof setInterval> | null = null

let quitting = false
let userMode: UserMode = 'SLEEPING'
let prefs: Prefs = {}
let scopes: Scopes = { ...DEFAULT_SCOPES }
let consentedThisRun = false
let statusLine = 'Sleeping'

let activeCall: (CallStarted & { source: CaptureSourceKind }) | null = null
let stopLiveStream: (() => void) | null = null

let lastCard: BubbleCard | null = null
let lastTail: 'left' | 'right' = 'left'
let bubbleHeight = BUBBLE_MIN_HEIGHT
let workspaceReady = false
let pendingWorkspaceTab: string | null = null

let screenGuardTimer: ReturnType<typeof setInterval> | null = null
let screenGuardBusy = false
let lastScreenText: { text: string; at: number } | null = null
const screenAlertUntil = new Map<string, number>()

const meetingWatcher = new MeetingWatcher(onMeeting)

function errorOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

// ---------------------------------------------------------------------------------------------
// Broadcasting to the renderer windows
// ---------------------------------------------------------------------------------------------
function windows(): BrowserWindow[] {
  return [mascotWindow, bubbleWindow, workspaceWindow].filter(
    (win): win is BrowserWindow =>
      win !== null && !win.isDestroyed() && !win.webContents.isDestroyed() && !win.webContents.isLoading(),
  )
}

function broadcast(channel: string, payload: unknown, only?: BrowserWindow[]): void {
  for (const win of only ?? windows()) {
    try {
      win.webContents.send(channel, payload)
    } catch {
      // window going away
    }
  }
}

/** Local, OS-side facts for the renderers. Never sent to the backend. */
function signal(value: SatyaSignal): void {
  if (value.kind === 'level' || value.kind === 'speech') {
    // 20 Hz loudness only matters to the mascot (nodding) and the live card.
    broadcast('satya:signal', value, windows().filter((w) => w !== workspaceWindow))
    return
  }
  broadcast('satya:signal', value)
}

function refreshTray(): void {
  const refreshable = tray as (ReturnType<typeof createTray> & { refreshMenu?: () => void }) | null
  refreshable?.refreshMenu?.()
}

function setStatus(text: string): void {
  statusLine = text
  refreshTray()
}

// ---------------------------------------------------------------------------------------------
// Mascot + bubble windows
// ---------------------------------------------------------------------------------------------
function pinMascotWindow(): void {
  if (!mascotWindow || mascotWindow.isDestroyed()) return
  try {
    mascotWindow.setAlwaysOnTop(true, 'screen-saver', 1)
    mascotWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true, skipTransformProcessType: true })
  } catch {
    // races with Space changes are harmless
  }
}

/**
 * Hide Satya's windows from screenshots and screen sharing (on by default): a fraudster watching
 * your shared screen never sees the warning, and Screen Guard never reads Satya's own cards.
 * Turn it off in the tray to record a backup video of the demo.
 */
function applyContentProtection(): void {
  const hide = prefs.hide_from_capture !== false
  for (const win of [mascotWindow, bubbleWindow, workspaceWindow]) {
    if (win && !win.isDestroyed()) win.setContentProtection(hide)
  }
}

function showCompanionWindow(): void {
  pinMascotWindow()
  showMascotWindow(mascotWindow)
  startCursorFeed()
}

function ensureBubble(): BrowserWindow {
  if (bubbleWindow && !bubbleWindow.isDestroyed()) return bubbleWindow
  bubbleWindow = createBubbleWindow(preloadPath)
  bubbleWindow.setContentProtection(prefs.hide_from_capture !== false)
  bubbleWindow.on('closed', () => {
    bubbleWindow = null
  })
  return bubbleWindow
}

function placeBubbleWindow(): 'left' | 'right' {
  if (!mascotWindow || !bubbleWindow || mascotWindow.isDestroyed() || bubbleWindow.isDestroyed()) return lastTail
  const bounds = mascotWindow.getBounds() as Rect
  const area = workAreaFor(mascotWindow) as Rect
  const placement = placeBubble(bounds, area, { width: BUBBLE_WIDTH, height: bubbleHeight })
  bubbleWindow.setBounds({ x: placement.x, y: placement.y, width: BUBBLE_WIDTH, height: bubbleHeight })
  lastTail = placement.tail
  return placement.tail
}

function deliverCard(win: BrowserWindow, card: BubbleCard | null, tail: 'left' | 'right'): void {
  const payload = { card, tail }
  if (win.isDestroyed() || win.webContents.isDestroyed()) return
  const send = (): void => {
    if (win.isDestroyed() || win.webContents.isDestroyed()) return
    try {
      win.webContents.send('companion:card', payload)
    } catch {
      // ignore
    }
  }
  if (win.webContents.isLoading()) win.webContents.once('did-finish-load', send)
  else send()
}

function showCard(card: BubbleCard): void {
  const sameCard = lastCard?.id === card.id
  lastCard = card
  const win = ensureBubble()
  win.setAlwaysOnTop(true, 'screen-saver', 1)
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true, skipTransformProcessType: true })
  const tail = placeBubbleWindow()
  deliverCard(win, card, tail)
  if (sameCard && win.isVisible()) return
  // Passive cards never steal focus from the call window (Meet/Zoom keeps the keyboard).
  if (card.kind === 'live' || card.kind === 'toast' || card.kind === 'screen') win.showInactive()
  else win.show()
}

function hideCard(cardId?: string): void {
  if (cardId && lastCard?.id !== cardId) return
  lastCard = null
  if (!bubbleWindow || bubbleWindow.isDestroyed()) return
  deliverCard(bubbleWindow, null, lastTail)
  bubbleWindow.hide()
}

function resizeBubble(height: number): void {
  const next = Math.round(Math.min(Math.max(height, BUBBLE_MIN_HEIGHT), BUBBLE_MAX_HEIGHT))
  if (next === bubbleHeight) return
  bubbleHeight = next
  if (lastCard) placeBubbleWindow()
}

function relayCardAction(cardId: string, actionId: string): void {
  if (!mascotWindow || mascotWindow.isDestroyed() || mascotWindow.webContents.isDestroyed()) return
  try {
    mascotWindow.webContents.send('companion:card-action', { card_id: cardId, action_id: actionId })
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------------------------
// Drag, click-through and the cursor feed
// ---------------------------------------------------------------------------------------------
let mouseIgnored = true
let manualClickThrough: boolean | null = null
let isDragging = false

function setClickThrough(through: boolean): void {
  manualClickThrough = through ? null : false
  applyMouseHitTest()
}

function applyMouseHitTest(point = screen.getCursorScreenPoint()): void {
  if (!mascotWindow || mascotWindow.isDestroyed() || isDragging) return
  const bounds = mascotWindow.getBounds()
  const cx = bounds.x + bounds.width / 2
  const cy = bounds.y + bounds.height * 0.56
  const distance = Math.hypot(point.x - cx, point.y - cy)
  const shouldIgnore = manualClickThrough !== false && distance > 78
  if (shouldIgnore === mouseIgnored) return
  mouseIgnored = shouldIgnore
  if (shouldIgnore) mascotWindow.setIgnoreMouseEvents(true, { forward: true })
  else mascotWindow.setIgnoreMouseEvents(false)
}

function dragBy(dx: number, dy: number): void {
  isDragging = true
  if (!mascotWindow || mascotWindow.isDestroyed()) return
  if (mouseIgnored) {
    mouseIgnored = false
    mascotWindow.setIgnoreMouseEvents(false)
  }
  const bounds = mascotWindow.getBounds()
  mascotWindow.setPosition(Math.round(bounds.x + dx), Math.round(bounds.y + dy))
  if (lastCard && bubbleWindow && !bubbleWindow.isDestroyed() && bubbleWindow.isVisible()) placeBubbleWindow()
}

function dragEnd(): void {
  isDragging = false
  manualClickThrough = null
  if (!mascotWindow || mascotWindow.isDestroyed()) return
  const snapped = snapToEdges(mascotWindow.getBounds() as Rect, workAreaFor(mascotWindow) as Rect)
  mascotWindow.setBounds({ x: snapped.x, y: snapped.y, width: snapped.width, height: snapped.height })
  prefs = writePrefs({ position: { x: snapped.x, y: snapped.y } })
  placeBubbleWindow()
  applyMouseHitTest()
}

function stopCursorFeed(): void {
  if (cursorTimer) clearInterval(cursorTimer)
  cursorTimer = null
}

/** 30 Hz while Satya is visible; the renderer only needs dx/dy and a near flag. */
function startCursorFeed(): void {
  stopCursorFeed()
  cursorTimer = setInterval(() => {
    const win = mascotWindow
    if (!win || win.isDestroyed() || !win.isVisible() || win.webContents.isDestroyed() || win.webContents.isLoading()) {
      return
    }
    const point = screen.getCursorScreenPoint()
    const bounds = win.getBounds()
    const dx = point.x - (bounds.x + bounds.width / 2)
    const dy = point.y - (bounds.y + bounds.height * 0.56)
    try {
      applyMouseHitTest(point)
    } catch {
      // ignore
    }
    try {
      win.webContents.send('companion:cursor', { dx, dy, near: Math.hypot(dx, dy) < 500 })
    } catch {
      // ignore
    }
  }, 33)
}

// ---------------------------------------------------------------------------------------------
// Capture window (hidden): created on the first call
// ---------------------------------------------------------------------------------------------
async function ensureCapture(): Promise<BrowserWindow> {
  if (captureWindow && !captureWindow.isDestroyed()) return captureWindow
  const win = createCaptureWindow(preloadPath)
  captureWindow = win
  win.on('closed', () => {
    if (captureWindow === win) captureWindow = null
  })
  registerCapture(win, {
    onStatus: onCaptureStatus,
    onLevel: (value) => signal({ kind: 'level', value }),
    onSpeech: (active) => signal({ kind: 'speech', active }),
    onUtterance: (index) => signal({ kind: 'transcribing', index }),
  })
  if (win.webContents.isLoading()) {
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, 6000)
      win.webContents.once('did-finish-load', () => {
        clearTimeout(timer)
        resolve()
      })
    })
  }
  return win
}

function onCaptureStatus(status: CaptureStatus): void {
  signal({ kind: 'capture', ...status })
  if (status.state === 'capturing') {
    setStatus(activeCall?.source === 'replay' ? 'Listening · DEMO REPLAY' : 'Listening to the call')
  } else if (status.state === 'stopped') {
    if (activeCall) void stopCall()
  } else if (status.state === 'error') {
    // Fail closed: stop the call and go to sleep. The mascot shows why.
    void (async () => {
      await stopCall()
      await setUserMode('SLEEPING')
    })()
  }
}

// ---------------------------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------------------------
function onLiveEvent(event: LiveBusEvent): void {
  if (!activeCall || event.type !== 'transcript') return
  const e = event as Extract<LiveBusEvent, { type: 'transcript' }> & {
    chunk_index: number
    t_start_s: number
    text: string
  }
  if (e.call_id !== activeCall.call_id || !e.text) return
  signal({
    kind: 'caption',
    call_id: e.call_id,
    line: {
      id: `${e.call_id}_${e.chunk_index}`,
      text: e.text,
      t_start_s: e.t_start_s,
      t_end_s: typeof e.t_end_s === 'number' ? e.t_end_s : null,
      spans: Array.isArray(e.spans) ? e.spans : [],
      latency_ms: typeof e.latency_ms === 'number' ? e.latency_ms : null,
    },
  })
}

function replayUrl(): string {
  return `${backend.baseUrl}/companion/replay/cfo_call_en.wav`
}

async function startCall(source: CaptureSourceKind): Promise<BridgeResult<CallStarted>> {
  if (userMode !== 'WATCHING') return { ok: false, error: 'Wake me up first, then I can listen.' }
  if (activeCall) return { ok: true, data: { call_id: activeCall.call_id, case_id: activeCall.case_id } }
  try {
    const state = await backend.getState()
    if (!state.consent_id) return { ok: false, error: 'Start watching first (consent is needed).' }
    const kind = source === 'replay' ? 'replay' : 'loopback'
    const language = prefs.call_language ?? 'en'
    const started = await backend.startCall(state.consent_id, kind, language === 'auto' ? undefined : language)
    activeCall = { call_id: started.call_id, case_id: started.case_id, source: kind }
    stopLiveStream?.()
    stopLiveStream = backend.streamLive(started.call_id, onLiveEvent)
    const win = await ensureCapture()
    sendCaptureCommand(win, {
      action: 'start',
      call_id: started.call_id,
      source: kind,
      replay_url: kind === 'replay' ? replayUrl() : undefined,
    })
    setStatus('Starting to listen…')
    return { ok: true, data: { call_id: started.call_id, case_id: started.case_id } }
  } catch (error) {
    activeCall = null
    return { ok: false, error: errorOf(error) }
  }
}

async function stopCall(): Promise<BridgeResult<null>> {
  const call = activeCall
  activeCall = null
  sendCaptureCommand(captureWindow, { action: 'stop' })
  stopLiveStream?.()
  stopLiveStream = null
  signal({ kind: 'level', value: 0 })
  if (!call) return { ok: true, data: null }
  try {
    await backend.stopCall(call.call_id)
  } catch {
    // The backend may already have dropped it; capture is stopped locally either way.
  }
  setStatus(userMode === 'WATCHING' ? 'Watching' : USER_MODE_LABELS[userMode])
  return { ok: true, data: null }
}

function onMeeting(meeting: MeetingInfo | null): void {
  signal({ kind: 'meeting', meeting })
  // The call window closed while we were listening: stop at once.
  if (!meeting && activeCall?.source === 'loopback') void stopCall()
}

// ---------------------------------------------------------------------------------------------
// Screen Guard + clipboard (on-device OCR; text checked by the local engine, never stored)
// ---------------------------------------------------------------------------------------------
function findingSignature(finding: ScreenFinding): string {
  return [
    ...finding.asks.map((a) => a.code),
    ...finding.unknown_accounts_masked,
    ...finding.vendors,
  ].join('|')
}

async function runScreenCheck(onDemand: boolean): Promise<BridgeResult<ScreenFinding>> {
  if (screenGuardBusy) return { ok: false, error: 'already reading the screen' }
  screenGuardBusy = true
  try {
    const text = await captureScreenText()
    lastScreenText = { text, at: Date.now() }
    const finding = await backend.textCheck(text, meetingWatcher.meeting?.app ?? null, 'screen')
    const signature = findingSignature(finding)
    if (!onDemand) {
      if (!finding.suspicious) return { ok: true, data: finding }
      if ((screenAlertUntil.get(signature) ?? 0) > Date.now()) return { ok: true, data: finding }
      screenAlertUntil.set(signature, Date.now() + SCREEN_ALERT_COOLDOWN_MS)
    }
    signal({ kind: 'text_check', source: 'screen', finding, on_demand: onDemand })
    return { ok: true, data: finding }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  } finally {
    screenGuardBusy = false
  }
}

function startScreenGuard(): void {
  if (screenGuardTimer) return
  screenGuardTimer = setInterval(() => {
    if (userMode === 'WATCHING' && scopes.screen && mascotWindow?.isVisible()) void runScreenCheck(false)
  }, SCREEN_GUARD_MS)
}

function stopScreenGuard(): void {
  if (screenGuardTimer) clearInterval(screenGuardTimer)
  screenGuardTimer = null
  lastScreenText = null
  screenAlertUntil.clear()
}

/** Read the clipboard only on this request and check it. */
async function checkClipboardText(): Promise<BridgeResult<ScreenFinding>> {
  if (userMode !== 'WATCHING') return { ok: false, error: 'Wake me up first.' }
  const text = clipboard.readText()
  if (!text.trim()) return { ok: false, error: 'The clipboard is empty.' }
  try {
    lastScreenText = { text, at: Date.now() }
    const finding = await backend.textCheck(text, null, 'clipboard')
    signal({ kind: 'text_check', source: 'clipboard', finding, on_demand: true })
    return { ok: true, data: finding }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  }
}

/** "Check it properly": hand the last screen/clipboard text to the policy engine as evidence. */
async function submitLastScreenText(): Promise<BridgeResult<EvidenceResult>> {
  if (!lastScreenText || Date.now() - lastScreenText.at > SCREEN_TEXT_TTL_MS) {
    return { ok: false, error: 'That text is gone (I keep it for 10 minutes at most).' }
  }
  const text = lastScreenText.text
  lastScreenText = null
  try {
    return { ok: true, data: await backend.submitEvidence(text.slice(0, 20_000)) }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  }
}

// ---------------------------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------------------------
function startWatchers(): void {
  if (scopes.meetings) meetingWatcher.start()
  else meetingWatcher.stop()
  if (scopes.screen) startScreenGuard()
  else stopScreenGuard()
}

function stopWatchers(): void {
  meetingWatcher.stop()
  stopScreenGuard()
}

async function setUserMode(mode: UserMode, nextScopes?: Scopes): Promise<BridgeResult<CompanionState>> {
  try {
    if (mode === 'WATCHING') {
      if (nextScopes) {
        scopes = { ...DEFAULT_SCOPES, ...nextScopes }
        prefs = writePrefs({ scopes })
      }
      let state = await backend.getState().catch(() => null)
      if (!state?.session_id) {
        const started = await backend.startSession('user_selected_loopback', 'Watching (consented)')
        state = started.state
      }
      userMode = 'WATCHING'
      consentedThisRun = true
      showCompanionWindow()
      startWatchers()
      setStatus('Watching')
      void backend.healthInfo().then((health) => signal({ kind: 'health', health }))
      return { ok: true, data: state }
    }

    // Sleeping / Off: stop everything first, then tell the backend.
    await stopCall()
    stopWatchers()
    userMode = mode
    try {
      await backend.stopSession()
    } catch {
      // Backend down: the local session is already off.
    }
    if (mode === 'OFF') {
      setTimeout(() => {
        if (userMode !== 'OFF') return
        stopCursorFeed()
        hideCard()
        hideWindow(mascotWindow)
      }, 1500)
    }
    setStatus(USER_MODE_LABELS[mode])
    const state = await backend.getState().catch(() => null)
    if (state) return { ok: true, data: state }
    return { ok: false, error: 'The engine is offline, so I went to sleep locally.' }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  }
}

function emergencyStop(): void {
  signal({ kind: 'hotkey', action: 'stop' })
  void setUserMode('SLEEPING')
}

/** Hide and Quit fail closed: stop the call, then `POST /companion/session/stop`. */
async function hideCompanion(): Promise<void> {
  await setUserMode('SLEEPING')
  stopCursorFeed()
  hideCard()
  hideWindow(mascotWindow)
}

async function quit(): Promise<void> {
  if (quitting) return
  quitting = true
  markAppQuitting()
  await Promise.race([
    (async () => {
      await stopCall()
      stopWatchers()
      await backend.stopSession().catch(() => undefined)
    })(),
    new Promise((resolve) => setTimeout(resolve, 800)),
  ])
  stopCursorFeed()
  backend.disconnect()
  for (const win of [mascotWindow, bubbleWindow, workspaceWindow, captureWindow]) {
    if (win && !win.isDestroyed()) {
      win.removeAllListeners('close')
      try {
        win.destroy()
      } catch {
        // ignore
      }
    }
  }
  app.exit(0)
}

// ---------------------------------------------------------------------------------------------
// Notebook
// ---------------------------------------------------------------------------------------------
function sendWorkspaceNavigation(): void {
  if (!pendingWorkspaceTab || !workspaceReady || !workspaceWindow || workspaceWindow.isDestroyed()) return
  try {
    workspaceWindow.webContents.send('companion:navigate-workspace', pendingWorkspaceTab)
    pendingWorkspaceTab = null
  } catch {
    // ignore
  }
}

function openWorkspace(tab?: string): void {
  pendingWorkspaceTab = tab ?? null
  if (process.platform === 'darwin') app.dock?.show()
  if (!workspaceWindow || workspaceWindow.isDestroyed()) {
    workspaceReady = false
    const win = createWorkspaceWindow(preloadPath)
    win.setContentProtection(prefs.hide_from_capture !== false)
    workspaceWindow = win
    win.on('closed', () => {
      if (workspaceWindow === win) workspaceWindow = null
      workspaceReady = false
      if (process.platform === 'darwin') app.dock?.hide()
    })
    win.webContents.on('did-start-loading', () => {
      workspaceReady = false
    })
    return
  }
  if (workspaceWindow.isMinimized()) workspaceWindow.restore()
  workspaceWindow.show()
  workspaceWindow.focus()
  sendWorkspaceNavigation()
}

// ---------------------------------------------------------------------------------------------
// Hotkeys
// ---------------------------------------------------------------------------------------------
function wakeOrSleep(): void {
  if (userMode === 'WATCHING') {
    signal({ kind: 'hotkey', action: 'stop' })
    void setUserMode('SLEEPING')
    return
  }
  showCompanionWindow()
  if (consentedThisRun) void setUserMode('WATCHING', scopes).then(() => signal({ kind: 'hotkey', action: 'wake' }))
  else signal({ kind: 'hotkey', action: 'wake' })
}

function registerShortcuts(): void {
  const bind = (accelerator: string, run: () => void): void => {
    try {
      globalShortcut.register(accelerator, run)
    } catch {
      // taken by another app: the menu and tray still work
    }
  }
  bind('CommandOrControl+Shift+S', wakeOrSleep)
  // Emergency brake: stop listening and reading, from any state.
  bind('CommandOrControl+Shift+.', emergencyStop)
  bind('CommandOrControl+Shift+N', () => openWorkspace())
  bind('CommandOrControl+Shift+L', () => {
    showCompanionWindow()
    signal({ kind: 'hotkey', action: 'listen' })
  })
  bind('CommandOrControl+Shift+K', () => {
    showCompanionWindow()
    signal({ kind: 'hotkey', action: 'scan' })
  })
  bind('CommandOrControl+Shift+V', () => {
    showCompanionWindow()
    void checkClipboardText().then((result) => {
      if (!result.ok) signal({ kind: 'hotkey', action: 'clipboard' })
    })
  })
  // Presenter fallback: play the labelled demo recording through the real pipeline.
  bind('CommandOrControl+Shift+D', () => {
    showCompanionWindow()
    signal({ kind: 'hotkey', action: 'replay' })
  })
}

function handleEvent(event: CompanionEvent): void {
  if (event.type === 'alert.raised' && event.payload.band) setStatus(`Alert · ${event.payload.band}`)
  broadcast('companion:event', event)
}

// ---------------------------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------------------------
const hasLock = app.requestSingleInstanceLock()
if (!hasLock) {
  console.warn('[Satya] Another instance is already running; showing it instead.')
  app.quit()
} else {
  app.on('second-instance', () => {
    showCompanionWindow()
    mascotWindow?.show()
  })

  void app.whenReady().then(() => {
    ipcMain.on('companion:workspace-ready', (event) => {
      if (event.sender !== workspaceWindow?.webContents) return
      workspaceReady = true
      sendWorkspaceNavigation()
    })
    if (process.platform === 'darwin') app.dock?.hide()
    app.setAppUserModelId('in.example.satyapan.companion')
    prefs = readPrefs()
    scopes = { ...DEFAULT_SCOPES, ...(prefs.scopes ?? {}) }

    mascotWindow = createMascotWindow({
      preloadPath,
      prefs,
      onCompanionHidden: () => {
        stopCursorFeed()
        void setUserMode('SLEEPING')
      },
    })
    mascotWindow.on('closed', () => {
      mascotWindow = null
    })
    mascotWindow.on('blur', pinMascotWindow)
    mascotWindow.on('focus', pinMascotWindow)
    mascotWindow.on('show', startCursorFeed)
    mascotWindow.on('hide', stopCursorFeed)
    screen.on('display-added', pinMascotWindow)
    screen.on('display-removed', pinMascotWindow)
    screen.on('display-metrics-changed', pinMascotWindow)
    pinMascotWindow()

    mascotWindow.webContents.on('context-menu', (_event, params) => {
      const watching = userMode === 'WATCHING'
      const menu = Menu.buildFromTemplate([
        { label: `Satya · ${statusLine}`, enabled: false },
        { type: 'separator' },
        watching
          ? { label: 'Sleep (⌘⇧.)', click: () => void setUserMode('SLEEPING') }
          : { label: 'Wake up', click: wakeOrSleep },
        ...(watching
          ? [
              activeCall
                ? { label: 'Stop listening', click: () => void stopCall() }
                : { label: 'Listen to a call now', click: () => signal({ kind: 'hotkey', action: 'listen' }) },
              { label: 'Scan my screen now', click: () => signal({ kind: 'hotkey', action: 'scan' }) },
              { label: 'Check what I copied', click: () => void checkClipboardText() },
              { label: 'Play the demo call (replay)', click: () => signal({ kind: 'hotkey', action: 'replay' }) },
            ]
          : []),
        { label: 'Open Notebook', click: () => openWorkspace() },
        { type: 'separator' },
        { label: 'Turn off', click: () => void setUserMode('OFF') },
        { label: 'Quit Satya', click: () => void quit() },
      ])
      menu.popup({ window: mascotWindow ?? undefined, x: params.x, y: params.y })
    })

    bubbleWindow = createBubbleWindow(preloadPath)
    bubbleWindow.on('closed', () => {
      bubbleWindow = null
    })
    applyContentProtection()

    registerIpc({
      backend,
      getCompanion: () => mascotWindow,
      openWorkspace,
      hideCompanion,
      quit,
      setClickThrough,
      dragBy,
      dragEnd,
      showCard,
      hideCard,
      relayCardAction,
      resizeBubble,
      setUserMode,
      getUserMode: () => userMode,
      getActiveCallId: () => activeCall?.call_id ?? null,
      startCall,
      stopCall,
      scanScreen: () => runScreenCheck(true),
      checkClipboardText,
      submitLastScreenText,
      setScopes: async (next) => {
        scopes = { ...DEFAULT_SCOPES, ...next }
        prefs = writePrefs({ scopes })
        if (userMode === 'WATCHING') startWatchers()
        return { ok: true, data: scopes }
      },
      getPrefs: () => prefs,
      setPrefs: (patch) => {
        prefs = writePrefs(patch)
        if (patch.position && mascotWindow) mascotWindow.setPosition(patch.position.x, patch.position.y)
        if (patch.hide_from_capture !== undefined) applyContentProtection()
        return prefs
      },
      openExternal: async (url) => {
        await shell.openExternal(url)
      },
    })

    tray = createTray({
      showCompanion: showCompanionWindow,
      hideCompanion: () => void hideCompanion(),
      openWorkspace: () => openWorkspace(),
      quit: () => void quit(),
      statusLabel: () => statusLine,
      getMode: () => userMode,
      setMode: (mode) => {
        if (mode === 'WATCHING') wakeOrSleep()
        else void setUserMode(mode)
      },
      toggleVisible: () => {
        if (mascotWindow?.isVisible()) void hideCompanion()
        else showCompanionWindow()
      },
      isVisible: () => Boolean(mascotWindow?.isVisible()),
      inCall: () => activeCall !== null,
      listenNow: () => {
        showCompanionWindow()
        signal({ kind: 'hotkey', action: 'listen' })
      },
      stopListening: () => void stopCall(),
      playDemoCall: () => {
        showCompanionWindow()
        signal({ kind: 'hotkey', action: 'replay' })
      },
      scanScreen: () => {
        showCompanionWindow()
        signal({ kind: 'hotkey', action: 'scan' })
      },
      checkClipboard: () => void checkClipboardText(),
      hideFromCapture: () => prefs.hide_from_capture !== false,
      toggleHideFromCapture: () => {
        prefs = writePrefs({ hide_from_capture: prefs.hide_from_capture === false })
        applyContentProtection()
        refreshTray()
      },
    })

    registerShortcuts()

    void backend.connect({
      onEvent: handleEvent,
      onConnection: (status) => {
        broadcast('companion:connection', status)
        if (!status.connected) setStatus('Engine offline — run `make run`')
        else if (statusLine.startsWith('Engine offline')) setStatus(USER_MODE_LABELS[userMode])
      },
      onTrayRequest: () => undefined,
      onHotkey: () => undefined,
    })
  })

  app.on('activate', showCompanionWindow)
  app.on('window-all-closed', () => {
    // Tray app: keep running until the user chooses Quit.
  })
  app.on('before-quit', (event) => {
    if (quitting) return
    event.preventDefault()
    void quit()
  })
  app.on('will-quit', () => {
    stopCursorFeed()
    globalShortcut.unregisterAll()
  })
}
