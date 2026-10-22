/** System tray: the calm control surface when the mascot is hidden (T25). */

import { join } from 'node:path'

import { Menu, Tray, nativeImage } from 'electron'

import { SOURCE_LABELS, type CompanionSource, type TrayRequest } from '../shared/contracts'

export interface TrayDependencies {
  showCompanion: () => void
  hideCompanion: () => void
  openWorkspace: () => void
  quit: () => void
  sendRequest: (request: TrayRequest) => void
  checkClipboard: () => void
  statusLabel: () => string
}

const SOURCE_ORDER: CompanionSource[] = [
  'demo_replay',
  'user_selected_loopback',
  'user_selected_microphone',
  'user_selected_email',
]

const DEMOS: Array<{ key: string; label: string }> = [
  { key: 'beneficiary_change', label: 'Beneficiary change → VERIFY' },
  { key: 'urgent_bypass', label: 'Secrecy + remote access → HOLD' },
]

export function createTray(deps: TrayDependencies): Tray {
  const iconPath = join(__dirname, '../../resources/trayTemplate.png')
  const image = nativeImage.createFromPath(iconPath)
  if (process.platform === 'darwin') image.setTemplateImage(true)
  const tray = new Tray(image)
  tray.setToolTip('Satya — Satyapan companion')

  const refresh = () => {
    tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: `Satya — ${deps.statusLabel()}`, enabled: false },
        { type: 'separator' },
        { label: 'Show Satya', click: () => deps.showCompanion() },
        {
          label: 'Start watching…',
          submenu: SOURCE_ORDER.map((source) => ({
            label: SOURCE_LABELS[source],
            click: () => deps.sendRequest({ kind: 'start', source }),
          })),
        },
        {
          label: 'Run demo replay',
          submenu: DEMOS.map((demo) => ({
            label: demo.label,
            click: () => deps.sendRequest({ kind: 'demo', scenario: demo.key }),
          })),
        },
        { label: 'Stop watching', click: () => deps.hideCompanion() },
        { label: 'Hide companion', click: () => deps.hideCompanion() },
        { type: 'separator' },
        {
          label: 'Check clipboard for risk',
          accelerator: 'CommandOrControl+Shift+V',
          click: () => deps.checkClipboard(),
        },
        { label: 'Case details', click: () => deps.openWorkspace() },
        { type: 'separator' },
        { label: 'Quit Satya', click: () => deps.quit() },
      ]),
    )
  }

  refresh()
  tray.on('click', () => {
    if (process.platform === 'darwin') refresh()
    deps.showCompanion()
  })
  ;(tray as Tray & { refreshMenu: () => void }).refreshMenu = refresh
  return tray
}
