/**
 * CompanionApiClient — the renderer's transport abstraction.
 *
 * `BridgeClient` talks to Electron main through `window.satyapan`; `MockCompanionClient`
 * lets the UI run with no backend at all (labelled replay). Both implement the same interface.
 */

export type {
  BridgeResult,
  CaseSummary,
  CommandResult,
  CompanionApiClient,
  CompanionEvent,
  CompanionHandlers,
  CompanionSource,
  CompanionState,
  ConnectionStatus,
  DraftArtifact,
  EvidenceResult,
  SessionResult,
  WorkspaceSnapshot,
} from '../../../shared/contracts'

import type {
  BridgeResult,
  CaseSummary,
  CommandResult,
  CompanionApiClient,
  CompanionEvent,
  CompanionHandlers,
  CompanionSource,
  CompanionState,
  DraftArtifact,
  EvidenceResult,
  SessionResult,
  WorkspaceSnapshot,
} from '../../../shared/contracts'
import { MockCompanionClient } from './mockClient'

function unwrap<T>(result: BridgeResult<T>): T {
  if (!result.ok) throw new Error(result.error)
  return result.data
}

export class BridgeClient implements CompanionApiClient {
  private bridge = window.satyapan
  private cleanups: Array<() => void> = []

  private get api() {
    if (!this.bridge) throw new Error('window.satyapan is not available')
    return this.bridge
  }

  async connect(handlers: CompanionHandlers): Promise<void> {
    this.disconnect()
    this.cleanups = [
      this.api.onEvent(handlers.onEvent),
      this.api.onConnection(handlers.onConnection),
      this.api.onTrayRequest(handlers.onTrayRequest),
      this.api.onHotkey(handlers.onHotkey),
    ]
  }

  disconnect(): void {
    for (const cleanup of this.cleanups) cleanup()
    this.cleanups = []
  }

  async getState(): Promise<CompanionState> {
    return unwrap(await this.api.getState())
  }

  async startSession(source: CompanionSource, label?: string): Promise<SessionResult> {
    return unwrap(await this.api.startSession(source, label))
  }

  async stopSession(): Promise<SessionResult> {
    return unwrap(await this.api.stopSession())
  }

  async command(type: string, payload: Record<string, unknown> = {}): Promise<CommandResult> {
    return unwrap(await this.api.command(type, payload))
  }

  async draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<DraftArtifact> {
    return unwrap(await this.api.draft(kind, caseId))
  }

  async workspace(caseId?: string): Promise<WorkspaceSnapshot> {
    return unwrap(await this.api.workspace(caseId))
  }

  async listCases(): Promise<CaseSummary[]> {
    return unwrap(await this.api.listCases())
  }

  async submitEvidence(text: string): Promise<EvidenceResult> {
    return unwrap(await this.api.submitEvidence(text))
  }

  async copyText(text: string): Promise<void> {
    if (this.bridge) {
      unwrap(await this.bridge.copyText(text))
      return
    }
    await navigator.clipboard.writeText(text)
  }

  async openWorkspace(): Promise<void> {
    if (this.bridge) {
      await this.bridge.openWorkspace()
      return
    }
    window.open('?view=workspace', '_blank')
  }

  async hide(): Promise<void> {
    if (this.bridge) {
      unwrap(await this.bridge.hideCompanion())
      return
    }
    window.close()
  }
}

export function createCompanionClient(): CompanionApiClient {
  if (typeof window !== 'undefined' && window.satyapan) return new BridgeClient()
  return new MockCompanionClient()
}

export type { CompanionEvent as CompanionEventShape }
