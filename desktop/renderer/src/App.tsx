import { Component, type ErrorInfo, type ReactNode } from 'react'

import Companion from './companion/Companion'
import Gallery from './companion/Gallery'
import MascotApp from './companion/MascotApp'
import BubbleApp from './companion/bubble/BubbleApp'
import CaptureApp from './capture/CaptureApp'
import Stage from './stage/Stage'
import Workspace from './workspace/Workspace'

export type View =
  | 'companion'
  | 'bubble'
  | 'workspace'
  | 'capture'
  | 'gallery'
  | 'stage'
  | 'legacy'

const VIEWS: View[] = [
  'companion',
  'bubble',
  'workspace',
  'capture',
  'gallery',
  'stage',
  'legacy',
]

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Satya renderer error', error, info)
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <div className="grid h-full place-items-center p-6 text-center text-sm text-white/60">
          Satya hit a rendering error. Quit from the tray and open again.
        </div>
      )
    }
    return this.props.children
  }
}

function currentView(): View {
  const requested = new URLSearchParams(window.location.search).get('view') ?? 'companion'
  return (VIEWS as string[]).includes(requested) ? (requested as View) : 'companion'
}

/**
 * One renderer, six views, selected by `?view=`:
 * `companion` (mascot window), `bubble`, `workspace` (Notebook), `capture` (hidden),
 * `gallery` (pose QA) and `stage` (mock rehearsal).
 *
 * The `Companion` shell stays the default mascot view until F07 replaces it with MascotApp.
 * `Workspace` is the Notebook (F14). `BubbleApp` shows exactly one card.
 */
export default function App(): JSX.Element {
  const view = currentView()
  return <Boundary>{renderView(view)}</Boundary>
}

function renderView(view: View): JSX.Element {
  switch (view) {
    case 'bubble':
      return <BubbleApp />
    case 'workspace':
      return <Workspace />
    case 'capture':
      return <CaptureApp />
    case 'gallery':
      return <Gallery />
    case 'stage':
      return <Stage />
    case 'legacy':
      return <Companion />
    default:
      return <MascotApp />
  }
}
