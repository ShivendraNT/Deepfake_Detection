import { Component, type ErrorInfo, type ReactNode } from 'react'

import Companion from './companion/Companion'
import Gallery from './satya/SatyaGallery'
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

class Boundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Satya renderer error', error, info)
  }

  render(): ReactNode {
    const { error } = this.state
    if (error) {
      return (
        <div className="grid h-full place-items-center overflow-auto p-6 text-center text-sm text-white/60">
          <div className="w-full max-w-[420px]">
            <p className="m-0 font-medium text-white/80">
              Satya hit a rendering error. Quit from the tray and open again.
            </p>
            <pre className="mt-3 max-h-[60vh] w-full overflow-auto whitespace-pre-wrap break-words rounded bg-black/40 p-3 text-left text-[11px] leading-snug text-red-200">
              {error.message}
              {error.stack ? `\n\n${error.stack}` : ''}
            </pre>
          </div>
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
