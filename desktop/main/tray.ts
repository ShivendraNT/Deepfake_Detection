/** System tray: the calm control surface when the mascot is hidden (docs/GRAND_FINALS §4.4). */

import { join } from 'node:path'

import { Menu, Tray, nativeImage } from 'electron'

import { SOURCE_LABELS, USER_MODE_LABELS, type CompanionSource, type TrayRequest, type UserMode } from '../shared/contracts'

export interface TrayDependencies {
  showCompanion: () => void
  hideCompanion: () => void
  openWorkspace: () => void
  quit: () => void
  sendRequest: (request: TrayRequest) => void
  checkClipboard: () => void
  statusLabel: () => string
  // Finale (F02)
  getMode?: () => UserMode
  setMode?: (mode: UserMode) => void
  toggleVisible?: () => void
  isVisible?: () => boolean
}

const SOURCE_ORDER: CompanionSource[] = [
  'demo_replay',
  'user_selected_loopback',
  'user_selected_microphone',
  'user_selected_email',
]

const DEMOS: Array<{ key: string; label: string }> = [
  { key: 'cfo_call', label: 'Deepfake CFO call (full story)' },
  { key: 'vendor_email', label: 'Vendor email + invoice → VERIFY' },
  { key: 'money_left', label: 'Money already left → Scribe' },
]

export function createTray(deps: TrayDependencies): Tray {
  const iconPath = join(__dirname, '../../resources/trayTemplate.png')
  const image = nativeImage.createFromPath(iconPath)
  if (process.platform === 'darwin') image.setTemplateImage(true)
  const tray = new Tray(image)
  tray.setToolTip('Satya — Satyapan companion')

  const mode = (): UserMode => deps.getMode?.() ?? 'SLEEPING'

  const refresh = () => {
    const current = mode()
    const visible = deps.isVisible?.() ?? true
    tray.setToolTip(`Satya — ${USER_MODE_LABELS[current]}`)
    tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: `Satya — ${USER_MODE_LABELS[current]}`, enabled: false },
        { label: deps.statusLabel(), enabled: false },
        { type: 'separator' },
        ...(current === 'OFF'
          ? [{ label: 'Bring Satya back', click: () => deps.setMode?.('SLEEPING') }]
          : [
              { label: 'Watch', click: () => deps.setMode?.('WATCHING') },
              { label: 'Sleep', click: () => deps.setMode?.('SLEEPING') },
            ]),
        {
          label: visible ? 'Hide Satya' : 'Show Satya',
          click: () => (deps.toggleVisible ? deps.toggleVisible() : deps.showCompanion()),
        },
        { label: 'Open Notebook', accelerator: 'CommandOrControl+Shift+N', click: () => deps.openWorkspace() },
        { type: 'separator' },
        {
          label: 'Start watching…',
          submenu: SOURCE_ORDER.map((source) => ({
            label: SOURCE_LABELS[source],
            click: () => deps.sendRequest({ kind: 'start', source }),
          })),
        },
        {
          label: 'Demo replay',
          submenu: DEMOS.map((demo) => ({
            label: demo.label,
            click: () => deps.sendRequest({ kind: 'demo', scenario: demo.key }),
          })),
        },
        {
          label: 'Check clipboard for risk',
          accelerator: 'CommandOrControl+Shift+V',
          click: () => deps.checkClipboard(),
        },
        { type: 'separator' },
        { label: 'Turn off', click: () => deps.setMode?.('OFF') },
        { label: 'Quit Satya', click: () => deps.quit() },
      ]),
    )
  }

  refresh()
  tray.on('click', (event) => {
    if (event.shiftKey) {
      deps.openWorkspace()
      return
    }
    refresh()
    deps.showCompanion()
  })
  // Native context menu on right-click (macOS opens the menu on a normal click too).
  tray.on('right-click', () => {
    refresh()
    tray.popUpContextMenu()
  })
  ;(tray as Tray & { refreshMenu: () => void }).refreshMenu = refresh
  return tray
}
