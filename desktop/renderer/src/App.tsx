import { Component, type ErrorInfo, type ReactNode } from 'react'

import Companion from './companion/Companion'
import Workspace from './workspace/Workspace'

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

export default function App(): JSX.Element {
  const view = new URLSearchParams(window.location.search).get('view') ?? 'companion'
  return <Boundary>{view === 'workspace' ? <Workspace /> : <Companion />}</Boundary>
}
