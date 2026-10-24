/**
 * Local FastAPI client used by the Electron main process (T25).
 *
 * The renderer never opens the network itself: it gets events through the narrow preload bridge.
 * This keeps the sandbox/CSP surface small and gives us one place to attach demo identity
 * headers. No score is parsed or stored here.
 */

import { networkInterfaces } from 'node:os'

import type {
  AppConfig,
  CaseSummary,
  CommandResult,
  CompanionEvent,
  CompanionHandlers,
  CompanionSource,
  CompanionState,
  DraftArtifact,
  EvidenceResult,
  SessionResult,
  WorkspaceSnapshot,
} from '../shared/contracts'

const DEFAULT_URL = 'http://127.0.0.1:8000'
const RECONNECT_MS = 2500

function getLocalIp(): string {
  try {
    const nets = networkInterfaces()
    for (const name of Object.keys(nets)) {
      for (const net of nets[name] ?? []) {
        if (net.family === 'IPv4' && !net.internal) {
          return net.address
        }
      }
    }
  } catch {}
  return '127.0.0.1'
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export class BackendClient {
  readonly baseUrl: string
  readonly demoUser: string
  readonly demoRole: string
  private controller: AbortController | null = null
  private lastEventId: string | null = null
  private stopped = false

  constructor(
    baseUrl = process.env.SATYAPAN_API_URL ?? DEFAULT_URL,
    demoUser = process.env.SATYAPAN_DEMO_USER ?? 'emp_priya',
    demoRole = process.env.SATYAPAN_DEMO_ROLE ?? 'maker',
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
    this.demoUser = demoUser
    this.demoRole = demoRole
  }

  config(): AppConfig {
    const localIp = getLocalIp()
    const defaultOobUrl =
      localIp !== '127.0.0.1' ? `http://${localIp}:8000/oob` : `${this.baseUrl}/oob`
    return {
      backendUrl: this.baseUrl,
      demoUser: this.demoUser,
      demoRole: this.demoRole,
      platform: process.platform,
      version: '1.0.0',
      oob_url: process.env.SATYAPAN_OOB_URL ?? defaultOobUrl,
    }
  }

  private headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'X-Demo-User': this.demoUser,
      'X-Demo-Role': this.demoRole,
    }
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: { ...this.headers(), ...(init.headers ?? {}) },
      signal: AbortSignal.timeout(10_000),
    })
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`
      try {
        const body = (await response.json()) as { detail?: string }
        if (body.detail) detail = body.detail
      } catch {
        // keep the status text
      }
      throw new Error(detail)
    }
    return (await response.json()) as T
  }

  async health(): Promise<Record<string, unknown>> {
    return this.request('/companion/health')
  }

  async getState(): Promise<CompanionState> {
    return this.request('/companion/state')
  }

  async listCases(): Promise<CaseSummary[]> {
    return this.request('/companion/cases')
  }

  async startSession(source: CompanionSource, label?: string): Promise<SessionResult> {
    return this.request('/companion/session/start', {
      method: 'POST',
      body: JSON.stringify({ version: '1', consent: true, source, ...(label ? { label } : {}) }),
    })
  }

  async stopSession(): Promise<SessionResult> {
    return this.request('/companion/session/stop', { method: 'POST' })
  }

  async startCall(
    consentId: string,
    source: string = 'user_selected_loopback',
  ): Promise<{ call_id: string; case_id: string; events: CompanionEvent[] }> {
    return this.request('/companion/calls/start', {
      method: 'POST',
      body: JSON.stringify({
        version: '1',
        consent_id: consentId,
        source,
        maker: this.demoUser,
      }),
    })
  }

  async stopCall(callId?: string): Promise<{ call_id: string }> {
    return this.request('/companion/calls/stop', {
      method: 'POST',
      body: JSON.stringify({
        version: '1',
        ...(callId ? { call_id: callId } : {}),
      }),
    })
  }

  async command(type: string, payload: Record<string, unknown> = {}): Promise<CommandResult> {
    return this.request('/companion/commands', {
      method: 'POST',
      body: JSON.stringify({
        version: '1',
        request_id: `req_${Date.now().toString(36)}`,
        type,
        payload,
      }),
    })
  }

  async submitEvidence(text: string, evidenceId?: string): Promise<EvidenceResult> {
    const state = await this.getState()
    return this.request('/companion/evidence', {
      method: 'POST',
      body: JSON.stringify({
        version: '1',
        request_id: `req_ev_${Date.now().toString(36)}`,
        session_id: state.session_id,
        source: state.source ?? 'user_selected_email',
        consent: true,
        evidence_id: evidenceId ?? `ev_text_${Date.now().toString(36)}`,
        text,
      }),
    })
  }

  async draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<DraftArtifact> {
    return this.request('/companion/drafts', {
      method: 'POST',
      body: JSON.stringify({ version: '1', kind, case_id: caseId }),
    })
  }

  async workspace(caseId?: string): Promise<WorkspaceSnapshot> {
    const suffix = caseId ? `?case_id=${encodeURIComponent(caseId)}` : ''
    return this.request(`/companion/workspace${suffix}`)
  }

  async submitTextToBackend(text: string, evidenceId?: string): Promise<EvidenceResult> {
    return this.submitEvidence(text, evidenceId)
  }

  /** Connect the SSE stream and keep it alive until disconnect(). Failures are reported, not thrown. */
  async connect(handlers: CompanionHandlers): Promise<void> {
    this.stopped = false
    while (!this.stopped) {
      this.controller = new AbortController()
      try {
        const response = await fetch(`${this.baseUrl}/companion/events`, {
          headers: {
            Accept: 'text/event-stream',
            'X-Demo-User': this.demoUser,
            'X-Demo-Role': this.demoRole,
            ...(this.lastEventId ? { 'Last-Event-ID': this.lastEventId } : {}),
          },
          signal: this.controller.signal,
        })
        if (!response.ok || !response.body) {
          throw new Error(`event stream ${response.status}`)
        }
        handlers.onConnection({ connected: true, backendUrl: this.baseUrl, mock: false })
        await this.consume(response.body, handlers)
      } catch (error) {
        if (this.stopped) return
        handlers.onConnection({
          connected: false,
          backendUrl: this.baseUrl,
          mock: false,
          error: messageOf(error),
        })
      }
      if (this.stopped) return
      await new Promise((resolve) => setTimeout(resolve, RECONNECT_MS))
    }
  }

  disconnect(): void {
    this.stopped = true
    this.controller?.abort()
    this.controller = null
  }

  private async consume(body: ReadableStream<Uint8Array>, handlers: CompanionHandlers) {
    const reader = body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        this.handleBlock(block, handlers)
        boundary = buffer.indexOf('\n\n')
      }
    }
  }

  private handleBlock(block: string, handlers: CompanionHandlers) {
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      if (line.startsWith('id:')) this.lastEventId = line.slice(3).trim()
    }
    if (data.length === 0) return
    try {
      const event = JSON.parse(data.join('\n')) as CompanionEvent
      if (event.event_id) this.lastEventId = event.event_id
      handlers.onEvent(event)
    } catch {
      // Ignore a malformed frame; the next reconnect replays from the last good id.
    }
  }
}
