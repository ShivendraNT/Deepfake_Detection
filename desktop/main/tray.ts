/** System tray: the calm control surface, and how you bring Satya back when he is Off. */

import { join } from 'node:path'

import { Menu, Tray, nativeImage, type MenuItemConstructorOptions } from 'electron'

import { USER_MODE_LABELS, type UserMode } from '../shared/contracts'

export interface TrayDependencies {
  showCompanion: () => void
  hideCompanion: () => void
  openWorkspace: () => void
  quit: () => void
  statusLabel: () => string
  getMode: () => UserMode
  setMode: (mode: UserMode) => void
  toggleVisible: () => void
  isVisible: () => boolean
  inCall: () => boolean
  listenNow: () => void
  stopListening: () => void
  playDemoCall: () => void
  scanScreen: () => void
  checkClipboard: () => void
  hideFromCapture: () => boolean
  toggleHideFromCapture: () => void
}

export function createTray(deps: TrayDependencies): Tray {
  const image = nativeImage.createFromPath(join(__dirname, '../../resources/trayTemplate.png'))
  if (process.platform === 'darwin') image.setTemplateImage(true)
  const tray = new Tray(image)

  const refresh = (): void => {
    const mode = deps.getMode()
    const watching = mode === 'WATCHING'
    tray.setToolTip(`Satya — ${USER_MODE_LABELS[mode]}`)
    const items: MenuItemConstructorOptions[] = [
      { label: `Satya — ${deps.statusLabel()}`, enabled: false },
      { type: 'separator' },
      watching
        ? { label: 'Sleep (stop everything)', accelerator: 'CommandOrControl+Shift+.', click: () => deps.setMode('SLEEPING') }
        : { label: mode === 'OFF' ? 'Bring Satya back' : 'Wake up', accelerator: 'CommandOrControl+Shift+S', click: () => deps.setMode('WATCHING') },
    ]
    if (watching) {
      items.push(
        deps.inCall()
          ? { label: 'Stop listening', click: () => deps.stopListening() }
          : { label: 'Listen to a call now', accelerator: 'CommandOrControl+Shift+L', click: () => deps.listenNow() },
        { label: 'Scan my screen now', accelerator: 'CommandOrControl+Shift+K', click: () => deps.scanScreen() },
        { label: 'Check what I copied', accelerator: 'CommandOrControl+Shift+Y', click: () => deps.checkClipboard() },
      )
    }
    items.push(
      { type: 'separator' },
      { label: deps.isVisible() ? 'Hide Satya' : 'Show Satya', click: () => deps.toggleVisible() },
      { label: 'Open Notebook', accelerator: 'CommandOrControl+Shift+U', click: () => deps.openWorkspace() },
      {
        label: 'Presenter',
        submenu: [
          {
            label: 'Play the demo call (DEMO REPLAY)',
            accelerator: 'CommandOrControl+Shift+D',
            enabled: watching && !deps.inCall(),
            click: () => deps.playDemoCall(),
          },
          {
            label: 'Hide Satya from screen sharing & recordings',
            type: 'checkbox',
            checked: deps.hideFromCapture(),
            click: () => deps.toggleHideFromCapture(),
          },
        ],
      },
      { type: 'separator' },
      ...(mode !== 'OFF' ? [{ label: 'Turn off', click: () => deps.setMode('OFF') } as MenuItemConstructorOptions] : []),
      { label: 'Quit Satya', click: () => deps.quit() },
    )
    tray.setContextMenu(Menu.buildFromTemplate(items))
  }

  refresh()
  tray.on('click', () => {
    refresh()
    deps.showCompanion()
  })
  tray.on('right-click', () => {
    refresh()
    tray.popUpContextMenu()
  })
  ;(tray as Tray & { refreshMenu: () => void }).refreshMenu = refresh
  return tray
}
