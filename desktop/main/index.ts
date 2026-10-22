/**
 * Electron main process for Satya (T25).
 *
 * Starts in Sleep / DND: no capture, no session, no backend subscription until the app is ready.
 * The renderer must show a visible consent card before the start IPC is accepted. Hiding or
 * quitting always stops the consented session first.
 */

import { join } from 'node:path'

import { app, BrowserWindow, clipboard, globalShortcut } from 'electron'

import { MODE_LABELS, type CompanionEvent, type TrayRequest } from '../shared/contracts'
import { BackendClient } from './backend'
import { inspectClipboard, registerIpc } from './ipc'
import { createTray } from './tray'
import { createCompanionWindow, createWorkspaceWindow, showCompanion } from './windows'

const backend = new BackendClient()
const preloadPath = join(__dirname, '../preload/index.js')

let companionWindow: BrowserWindow | null = null
let workspaceWindow: BrowserWindow | null = null
let tray: ReturnType<typeof createTray> | null = null
let quitting = false
let lastStatus = 'Sleep / DND'

function send(channel: string, payload: unknown): void {
  for (const win of [companionWindow, workspaceWindow]) {
    if (win && !win.isDestroyed()) win.webContents.send(channel, payload)
  }
}

function showCompanionWindow(): void {
  showCompanion(companionWindow)
}

function openWorkspace(): void {
  if (workspaceWindow && !workspaceWindow.isDestroyed()) {
    workspaceWindow.show()
    workspaceWindow.focus()
    return
  }
  workspaceWindow = createWorkspaceWindow(preloadPath)
  workspaceWindow.on('closed', () => {
    workspaceWindow = null
  })
}

async function stopSafely(): Promise<void> {
  try {
    // Fails closed on hide/quit: posts to /companion/session/stop
    await backend.stopSession()
    lastStatus = 'Sleep / DND'
  } catch {
    // The backend may be down; the local session is already off from the renderer's view.
  }
}

async function hideCompanion(): Promise<void> {
  await stopSafely()
  companionWindow?.hide()
}

async function quit(): Promise<void> {
  quitting = true
  await stopSafely()
  backend.disconnect()
  app.quit()
}

function checkClipboard(): void {
  showCompanionWindow()
  const check = inspectClipboard(clipboard.readText())
  send('companion:tray-request', { kind: 'clipboard', check } satisfies TrayRequest)
}

function statusLabel(): string {
  return lastStatus
}

function registerShortcuts(): void {
  globalShortcut.register('CommandOrControl+Shift+S', () => {
    showCompanionWindow()
    send('companion:hotkey', 'sleep-toggle')
  })
  globalShortcut.register('CommandOrControl+Shift+V', checkClipboard)
  globalShortcut.register('CommandOrControl+Shift+D', () => {
    showCompanionWindow()
    send('companion:hotkey', 'demo')
  })
}

function handleEvent(event: CompanionEvent): void {
  if (event.payload.band) {
    lastStatus = `${MODE_LABELS[event.payload.state]} · ${event.payload.band}`
  } else {
    lastStatus = MODE_LABELS[event.payload.state]
  }
  send('companion:event', event)
  const refreshable = tray as (ReturnType<typeof createTray> & { refreshMenu?: () => void }) | null
  refreshable?.refreshMenu?.()
}

const hasLock = app.requestSingleInstanceLock()
if (!hasLock) {
  app.quit()
} else {
  app.on('second-instance', showCompanionWindow)

  app.whenReady().then(() => {
    app.setAppUserModelId('in.example.satyapan.companion')
    companionWindow = createCompanionWindow({
      preloadPath,
      onCompanionHidden: () => {
        void stopSafely()
      },
    })
    companionWindow.on('closed', () => {
      companionWindow = null
    })

    registerIpc({
      backend,
      getCompanion: () => companionWindow,
      openWorkspace,
      hideCompanion,
      quit,
    })

    tray = createTray({
      showCompanion: showCompanionWindow,
      hideCompanion: () => {
        void hideCompanion()
      },
      openWorkspace,
      quit: () => {
        void quit()
      },
      sendRequest: (request) => {
        showCompanionWindow()
        send('companion:tray-request', request)
      },
      checkClipboard,
      statusLabel,
    })

    registerShortcuts()

    void backend.connect({
      onEvent: handleEvent,
      onConnection: (status) => {
        send('companion:connection', status)
        if (!status.connected && status.error) {
          lastStatus = 'Backend offline — replay only'
        }
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
  app.on('will-quit', () => globalShortcut.unregisterAll())
}
