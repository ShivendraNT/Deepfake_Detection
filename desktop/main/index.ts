/**
 * Electron main process for Satya (F02).
 *
 * Four decoupled windows: mascot (280×280, click-through), bubble (one card), Notebook,
 * hidden capture. Starts in Sleeping: no capture, no session, no backend subscription until the
 * user says yes on a visible consent card. Hiding or quitting always stops the consented session
 * first (`POST /companion/session/stop`); if the backend is down we still fail closed locally.
 */

import { join } from 'node:path'

import { app, BrowserWindow, clipboard, globalShortcut, Menu, screen, shell } from 'electron'

import type {
  BridgeResult,
  BubbleCard,
  CompanionEvent,
  CompanionState,
  Prefs,
  TrayRequest,
  UserMode,
} from '../shared/contracts'
import { MODE_LABELS } from '../shared/contracts'
import { BackendClient } from './backend'
import { inspectClipboard, registerIpc } from './ipc'
import { placeBubble, snapToEdges, type Rect } from './placement'
import { readPrefs, writePrefs } from './prefs'
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
  showCompanion as showMascotWindow,
  workAreaFor,
} from './windows'

const backend = new BackendClient()
const preloadPath = join(__dirname, '../preload/index.js')

let mascotWindow: BrowserWindow | null = null
let bubbleWindow: BrowserWindow | null = null
let workspaceWindow: BrowserWindow | null = null
let captureWindow: BrowserWindow | null = null
let tray: ReturnType<typeof createTray> | null = null
let cursorTimer: ReturnType<typeof setInterval> | null = null

let quitting = false
let lastStatus = 'Sleeping'
let userMode: UserMode = 'SLEEPING'
let prefs: Prefs = {}
let lastCard: BubbleCard | null = null
let lastTail: 'left' | 'right' = 'left'
let bubbleHeight = BUBBLE_MIN_HEIGHT

function errorOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function send(channel: string, payload: unknown): void {
  for (const win of [mascotWindow, bubbleWindow, workspaceWindow]) {
    if (win && !win.isDestroyed()) win.webContents.send(channel, payload)
  }
}

function refreshTray(): void {
  const refreshable = tray as (ReturnType<typeof createTray> & { refreshMenu?: () => void }) | null
  refreshable?.refreshMenu?.()
}

function showCompanionWindow(): void {
  showMascotWindow(mascotWindow)
  startCursorFeed()
}

// ---------------------------------------------------------------------------------------------
// Bubble placement
// ---------------------------------------------------------------------------------------------
function ensureBubble(): BrowserWindow {
  if (bubbleWindow && !bubbleWindow.isDestroyed()) return bubbleWindow
  bubbleWindow = createBubbleWindow(preloadPath)
  bubbleWindow.on('closed', () => {
    bubbleWindow = null
  })
  return bubbleWindow
}

function placeBubbleWindow(): 'left' | 'right' {
  if (!mascotWindow || !bubbleWindow || mascotWindow.isDestroyed()) return lastTail
  const bounds = mascotWindow.getBounds() as Rect
  const area = workAreaFor(mascotWindow) as Rect
  const placement = placeBubble(bounds, area, { width: BUBBLE_WIDTH, height: bubbleHeight })
  bubbleWindow.setBounds({
    x: placement.x,
    y: placement.y,
    width: BUBBLE_WIDTH,
    height: bubbleHeight,
  })
  lastTail = placement.tail
  return placement.tail
}

function deliverCard(win: BrowserWindow, card: BubbleCard | null, tail: 'left' | 'right'): void {
  const payload = { card, tail }
  if (win.webContents.isLoading()) {
    win.webContents.once('did-finish-load', () => win.webContents.send('companion:card', payload))
    return
  }
  win.webContents.send('companion:card', payload)
}

function showCard(card: BubbleCard): void {
  lastCard = card
  const win = ensureBubble()
  win.setAlwaysOnTop(true, 'screen-saver', 1)
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true, skipTransformProcessType: true })
  const tail = placeBubbleWindow()
  deliverCard(win, card, tail)
  // Passive cards must never steal focus from the call (Meet/Teams keeps focus).
  if (card.kind === 'live' || card.kind === 'toast') win.showInactive()
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
  if (actionId === 'dismiss') {
    hideCard(cardId)
    return
  }
  if (!mascotWindow || mascotWindow.isDestroyed()) return
  mascotWindow.webContents.send('companion:card-action', { card_id: cardId, action_id: actionId })
}

// ---------------------------------------------------------------------------------------------
// Drag, click-through and the cursor feed
// ---------------------------------------------------------------------------------------------
let mouseIgnored = true
let manualClickThrough: boolean | null = null
let isDragging = false

function setClickThrough(through: boolean): void {
  manualClickThrough = through ? null : false
  if (!mascotWindow || mascotWindow.isDestroyed()) return
  if (!through && mouseIgnored) {
    mouseIgnored = false
    mascotWindow.setIgnoreMouseEvents(false)
  }
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
  if (lastCard && bubbleWindow && !bubbleWindow.isDestroyed() && bubbleWindow.isVisible()) {
    placeBubbleWindow()
  }
}

function dragEnd(): void {
  isDragging = false
  manualClickThrough = null
  if (!mascotWindow || mascotWindow.isDestroyed()) return
  const snapped = snapToEdges(mascotWindow.getBounds() as Rect, workAreaFor(mascotWindow) as Rect)
  mascotWindow.setBounds({
    x: snapped.x,
    y: snapped.y,
    width: snapped.width,
    height: snapped.height,
  })
  prefs = writePrefs({ position: { x: snapped.x, y: snapped.y } })
  placeBubbleWindow()
}

function stopCursorFeed(): void {
  if (cursorTimer) clearInterval(cursorTimer)
  cursorTimer = null
}

/** 30 Hz while Satya is visible; the renderer only needs dx/dy and a near flag. */
function startCursorFeed(): void {
  stopCursorFeed()
  if (!mascotWindow || mascotWindow.isDestroyed() || !mascotWindow.isVisible()) return
  cursorTimer = setInterval(() => {
    if (!mascotWindow || mascotWindow.isDestroyed() || !mascotWindow.isVisible()) {
      stopCursorFeed()
      return
    }
    const point = screen.getCursorScreenPoint()
    const bounds = mascotWindow.getBounds()
    const dx = point.x - (bounds.x + bounds.width / 2)
    const dy = point.y - (bounds.y + bounds.height / 2)
    const dist = Math.hypot(dx, dy)

    if (!isDragging && manualClickThrough !== false) {
      // Satya is centered; 96 px radius covers his 176 px body with margin.
      // Clicks inside this circle are captured by Satya; clicks outside pass through.
      const overMascot = dist <= 96
      const shouldIgnore = !overMascot
      if (shouldIgnore !== mouseIgnored) {
        mouseIgnored = shouldIgnore
        mascotWindow.setIgnoreMouseEvents(shouldIgnore, { forward: true })
      }
    }

    mascotWindow.webContents.send('companion:cursor', {
      dx,
      dy,
      near: dist < 500,
    })
  }, 33)
}

// ---------------------------------------------------------------------------------------------
// Modes, capture and lifecycle
// ---------------------------------------------------------------------------------------------
function ensureCapture(): void {
  if (captureWindow && !captureWindow.isDestroyed()) return
  captureWindow = createCaptureWindow(preloadPath)
  captureWindow.on('closed', () => {
    captureWindow = null
  })
  try {
    // Kartikey's F10 module owns this file. Until it lands, the hidden window just exists.
    /* eslint-disable @typescript-eslint/no-var-requires */
    const captureModule = require(join(__dirname, 'capture.js')) as {
      registerCapture?: (options: { window: BrowserWindow; backend: BackendClient }) => void
    }
    captureModule.registerCapture?.({ window: captureWindow, backend })
  } catch {
    // capture.ts is not built yet (F10); the guardian simply does not start loopback capture.
  }
}

async function setUserMode(mode: UserMode): Promise<BridgeResult<CompanionState>> {
  try {
    userMode = mode
    if (mode === 'WATCHING') {
      const result = await backend.startSession('user_selected_loopback', 'Watching')
      lastStatus = 'Watching'
      showCompanionWindow()
      ensureCapture()
      refreshTray()
      return { ok: true, data: result.state }
    }
    await backend.stopSession()
    if (mode === 'OFF') {
      lastStatus = 'Off'
      stopCursorFeed()
      hideWindow(mascotWindow)
      hideCard()
    } else {
      lastStatus = 'Sleeping'
    }
    refreshTray()
    return { ok: true, data: await backend.getState() }
  } catch (error) {
    return { ok: false, error: errorOf(error) }
  }
}

function toggleSleep(): void {
  void setUserMode(userMode === 'WATCHING' ? 'SLEEPING' : 'WATCHING')
}

function emergencyStop(): void {
  send('companion:hotkey', 'stop')
  void setUserMode('SLEEPING')
}

function toggleVisible(): void {
  if (mascotWindow?.isVisible()) {
    void hideCompanion()
    return
  }
  showCompanionWindow()
}

async function stopSafely(): Promise<void> {
  try {
    // Fails closed on hide/quit: posts to POST /companion/session/stop.
    await backend.stopSession()
    lastStatus = 'Sleeping'
  } catch {
    // The backend may be down; the local session is already off from the renderer's view.
  }
  refreshTray()
}

async function hideCompanion(): Promise<void> {
  await stopSafely()
  stopCursorFeed()
  hideCard()
  hideWindow(mascotWindow)
}

async function quit(): Promise<void> {
  quitting = true
  await stopSafely()
  stopCursorFeed()
  backend.disconnect()
  app.quit()
}

function openWorkspace(_tab?: string): void {
  if (process.platform === 'darwin') {
    app.dock?.show()
  }
  if (workspaceWindow && !workspaceWindow.isDestroyed()) {
    workspaceWindow.show()
    workspaceWindow.focus()
    return
  }
  workspaceWindow = createWorkspaceWindow(preloadPath)
  workspaceWindow.on('closed', () => {
    workspaceWindow = null
    if (process.platform === 'darwin') {
      app.dock?.hide()
    }
  })
}

function checkClipboard(): void {
  showCompanionWindow()
  const text = clipboard.readText()
  const check = inspectClipboard(text)
  send('companion:tray-request', { kind: 'clipboard', check } satisfies TrayRequest)

  if (check.suspicious) {
    showCard({
      id: `clip-${Date.now()}`,
      kind: 'alert',
      band: 'HOLD',
      headline: `Suspicious: ${check.matches.join(' and ')}`,
      reasons: check.matches,
      chips: [],
      actions: [{ id: 'dismiss', variant: 'ghost' }],
    })
  } else if (text.trim().length > 0) {
    showCard({
      id: `clip-${Date.now()}`,
      kind: 'result',
      band: 'PASS',
      headline: 'Clipboard looks OK',
      reasons: ['No urgent payment tricks found in copied text'],
      actions: [{ id: 'dismiss', variant: 'ghost' }],
    })
  } else {
    showCard({
      id: `clip-${Date.now()}`,
      kind: 'toast',
      text_key: 'clipboard_empty',
      tone: 'neutral',
    })
  }
}

function replayScenario(scenario: string): void {
  showCompanionWindow()
  send('companion:tray-request', { kind: 'demo', scenario } satisfies TrayRequest)
}

function statusLabel(): string {
  return lastStatus
}

function registerShortcuts(): void {
  // Wake / sleep.
  globalShortcut.register('CommandOrControl+Shift+S', toggleSleep)
  // Emergency brake: stop listening from any state.
  const stopped = globalShortcut.register('CommandOrControl+Shift+.', emergencyStop)
  if (!stopped) globalShortcut.register('CommandOrControl+Shift+Period', emergencyStop)
  // Notebook.
  globalShortcut.register('CommandOrControl+Shift+N', () => openWorkspace())
  // Clipboard is read only on this press.
  globalShortcut.register('CommandOrControl+Shift+V', checkClipboard)
}

function handleEvent(event: CompanionEvent): void {
  if (event.payload.band) {
    lastStatus = `${MODE_LABELS[event.payload.state]} · ${event.payload.band}`
  } else {
    lastStatus = MODE_LABELS[event.payload.state]
  }
  send('companion:event', event)
  refreshTray()
}

const hasLock = app.requestSingleInstanceLock()
if (!hasLock) {
  app.quit()
} else {
  app.on('second-instance', showCompanionWindow)

  void app.whenReady().then(() => {
    if (process.platform === 'darwin') {
      app.dock?.hide()
    }
    app.setAppUserModelId('in.example.satyapan.companion')
    prefs = readPrefs()

    mascotWindow = createMascotWindow({
      preloadPath,
      prefs,
      onCompanionHidden: () => {
        stopCursorFeed()
        void stopSafely()
      },
    })
    mascotWindow.on('closed', () => {
      mascotWindow = null
    })
    mascotWindow.on('show', startCursorFeed)
    mascotWindow.on('hide', stopCursorFeed)
    mascotWindow.webContents.on('context-menu', (_event, params) => {
      const menu = Menu.buildFromTemplate([
        { label: `Satya · ${statusLabel()}`, enabled: false },
        { type: 'separator' },
        {
          label: userMode === 'WATCHING' ? 'Sleep' : 'Watch',
          click: () => void setUserMode(userMode === 'WATCHING' ? 'SLEEPING' : 'WATCHING'),
        },
        {
          label: 'Open Notebook',
          click: () => openWorkspace(),
        },
        {
          label: 'Check Clipboard',
          click: checkClipboard,
        },
        { type: 'separator' },
        {
          label: 'Off',
          click: () => void setUserMode('OFF'),
        },
        {
          label: 'Quit Satya',
          click: () => void quit(),
        },
      ])
      menu.popup({ window: mascotWindow ?? undefined, x: params.x, y: params.y })
    })
    startCursorFeed()

    bubbleWindow = createBubbleWindow(preloadPath)
    bubbleWindow.on('closed', () => {
      bubbleWindow = null
    })

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
      getPrefs: () => prefs,
      setPrefs: (patch) => {
        prefs = writePrefs(patch)
        if (patch.position && mascotWindow) {
          mascotWindow.setPosition(patch.position.x, patch.position.y)
        }
        return prefs
      },
      openExternal: async (url) => {
        await shell.openExternal(url)
      },
    })

    tray = createTray({
      showCompanion: showCompanionWindow,
      hideCompanion: () => {
        void hideCompanion()
      },
      openWorkspace: () => openWorkspace(),
      quit: () => {
        void quit()
      },
      sendRequest: (request) => {
        showCompanionWindow()
        send('companion:tray-request', request)
      },
      checkClipboard,
      statusLabel,
      getMode: () => userMode,
      setMode: (mode) => {
        void setUserMode(mode)
      },
      toggleVisible,
      isVisible: () => Boolean(mascotWindow?.isVisible()),
    })

    registerShortcuts()

    void backend.connect({
      onEvent: handleEvent,
      onConnection: (status) => {
        send('companion:connection', status)
        if (!status.connected && status.error) {
          lastStatus = 'Backend offline — replay only'
        }
        refreshTray()
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
