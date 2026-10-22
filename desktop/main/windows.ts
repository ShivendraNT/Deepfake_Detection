/**
 * Four decoupled windows, one main process (docs/GRAND_FINALS_ARCHITECTURE.md §4).
 *
 * mascot (`?view=companion`) 280×280, transparent, frameless, click-through, never in the Dock.
 * bubble (`?view=bubble`)     360 × auto, transparent, appears beside Satya, hidden at start.
 * workspace (`?view=workspace`) the Notebook, a normal resizable window.
 * capture  (`?view=capture`)  1×1, hidden, never throttled; F10 fills in the audio path.
 *
 * Security defaults are deliberate and must stay: contextIsolation, sandbox, no Node in the
 * renderer, and a narrow navigation allow-list.
 */

import { join } from 'node:path'

import { BrowserWindow, screen, type Rectangle } from 'electron'

import type { Prefs } from '../shared/contracts'
import { clampToWorkArea, type Rect } from './placement'

export const MASCOT_WIDTH = 280
export const MASCOT_HEIGHT = 280
export const BUBBLE_WIDTH = 360
export const MASCOT_MARGIN = 24
export const BUBBLE_MIN_HEIGHT = 96
export const BUBBLE_MAX_HEIGHT = 480

export interface WindowFactoryOptions {
  preloadPath: string
  prefs?: Prefs
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

function secureWebPreferences(preloadPath: string): Electron.WebPreferences {
  return {
    preload: preloadPath,
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true,
    webSecurity: true,
    spellcheck: false,
  }
}

/** Bottom-right with a 24 px margin, unless the user dragged Satya somewhere else. */
export function mascotPosition(
  workArea: Rect,
  prefs?: Prefs,
): { x: number; y: number } {
  const saved = prefs?.position
  const rect: Rect = saved
    ? { x: saved.x, y: saved.y, width: MASCOT_WIDTH, height: MASCOT_HEIGHT }
    : {
        x: workArea.x + workArea.width - MASCOT_WIDTH - MASCOT_MARGIN,
        y: workArea.y + workArea.height - MASCOT_HEIGHT - MASCOT_MARGIN,
        width: MASCOT_WIDTH,
        height: MASCOT_HEIGHT,
      }
  const clamped = clampToWorkArea(rect, workArea)
  return { x: clamped.x, y: clamped.y }
}

export function createMascotWindow(options: WindowFactoryOptions): BrowserWindow {
  const area = screen.getPrimaryDisplay().workArea
  const position = mascotPosition(area, options.prefs)

  const win = new BrowserWindow({
    width: MASCOT_WIDTH,
    height: MASCOT_HEIGHT,
    x: position.x,
    y: position.y,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    roundedCorners: false,
    alwaysOnTop: true,
    title: 'Satya — Satyapan companion',
    webPreferences: {
      ...secureWebPreferences(options.preloadPath),
      devTools: true,
    },
  })

  win.setAlwaysOnTop(true, 'screen-saver', 1)
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  // Almost all of the window is empty: clicks pass through to the app behind until the renderer
  // says the pointer is over Satya or a menu petal.
  win.setIgnoreMouseEvents(true, { forward: true })
  if (process.platform === 'darwin') win.setWindowButtonVisibility(false)
  harden(win)

  win.once('ready-to-show', () => {
    win.setAlwaysOnTop(true, 'screen-saver', 1)
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
    win.showInactive()
  })
  win.on('close', (event) => {
    event.preventDefault()
    win.hide()
    options.onCompanionHidden()
  })
  load(win, { view: 'companion' })
  return win
}

/** Backwards-compatible alias for the T25 name. */
export function createCompanionWindow(options: WindowFactoryOptions): BrowserWindow {
  return createMascotWindow(options)
}

export function createBubbleWindow(preloadPath: string): BrowserWindow {
  const win = new BrowserWindow({
    width: BUBBLE_WIDTH,
    height: 180,
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
    title: 'Satya says',
    webPreferences: secureWebPreferences(preloadPath),
  })
  win.setAlwaysOnTop(true, 'screen-saver', 1)
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  harden(win)
  win.once('ready-to-show', () => {
    win.setAlwaysOnTop(true, 'screen-saver', 1)
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  })
  win.on('close', (event) => {
    event.preventDefault()
    win.hide()
  })
  load(win, { view: 'bubble' })
  return win
}

export function createWorkspaceWindow(preloadPath: string): BrowserWindow {
  const win = new BrowserWindow({
    width: 900,
    height: 650,
    minWidth: 800,
    minHeight: 560,
    show: false,
    title: 'Satya — Notebook',
    backgroundColor: '#070d12',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: secureWebPreferences(preloadPath),
  })
  harden(win)
  load(win, { view: 'workspace' })
  win.once('ready-to-show', () => win.show())
  return win
}

export function createCaptureWindow(preloadPath: string): BrowserWindow {
  const win = new BrowserWindow({
    width: 1,
    height: 1,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    webPreferences: {
      ...secureWebPreferences(preloadPath),
      backgroundThrottling: false,
    },
  })
  harden(win)
  load(win, { view: 'capture' })
  return win
}

export function showCompanion(win: BrowserWindow | null): void {
  if (!win || win.isDestroyed()) return
  win.setAlwaysOnTop(true, 'screen-saver', 1)
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  win.showInactive()
}

export function hideWindow(win: BrowserWindow | null): void {
  if (!win || win.isDestroyed()) return
  win.hide()
}

/** Work area of the display that currently contains the window. */
export function workAreaFor(win: BrowserWindow): Rectangle {
  return screen.getDisplayMatching(win.getBounds()).workArea
}
