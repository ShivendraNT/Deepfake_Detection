/** Frameless companion + details windows (T25). Security defaults are deliberate. */

import { join } from 'node:path'

import { BrowserWindow, screen } from 'electron'

const COMPANION_WIDTH = 380
const COMPANION_HEIGHT = 500

export interface WindowFactoryOptions {
  preloadPath: string
  onCompanionHidden: () => void
}

function rendererUrl(query: Record<string, string>): string | null {
  const devUrl = process.env.ELECTRON_RENDERER_URL
  if (!devUrl) return null
  const url = new URL(devUrl)
  for (const [key, value] of Object.entries(query)) url.searchParams.set(key, value)
  return url.toString()
}

function load(win: BrowserWindow, query: Record<string, string>): void {
  const dev = rendererUrl(query)
  if (dev) {
    void win.loadURL(dev)
    return
  }
  void win.loadFile(join(__dirname, '../renderer/index.html'), { query })
}

function harden(win: BrowserWindow): void {
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  win.webContents.on('will-navigate', (event, url) => {
    const allowed =
      url.startsWith('file://') ||
      /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\//.test(url)
    if (!allowed) event.preventDefault()
  })
}

export function createCompanionWindow(options: WindowFactoryOptions): BrowserWindow {
  const area = screen.getPrimaryDisplay().workArea
  const win = new BrowserWindow({
    width: COMPANION_WIDTH,
    height: COMPANION_HEIGHT,
    x: area.x + area.width - COMPANION_WIDTH - 24,
    y: area.y + area.height - COMPANION_HEIGHT - 24,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    roundedCorners: false,
    alwaysOnTop: true,
    title: 'Satya — Satyapan companion',
    webPreferences: {
      preload: options.preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
      devTools: true,
    },
  })

  win.setAlwaysOnTop(true, 'floating')
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  if (process.platform === 'darwin') win.setWindowButtonVisibility(false)
  harden(win)

  win.once('ready-to-show', () => win.showInactive())
  win.on('close', (event) => {
    event.preventDefault()
    win.hide()
    options.onCompanionHidden()
  })
  load(win, { view: 'companion' })
  return win
}

export function createWorkspaceWindow(preloadPath: string): BrowserWindow {
  const win = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 820,
    minHeight: 600,
    show: false,
    title: 'Satya — Case details',
    backgroundColor: '#070d12',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  })
  harden(win)
  load(win, { view: 'workspace' })
  win.once('ready-to-show', () => win.show())
  return win
}

export function showCompanion(win: BrowserWindow | null): void {
  if (!win) return
  win.show()
  win.focus()
}
