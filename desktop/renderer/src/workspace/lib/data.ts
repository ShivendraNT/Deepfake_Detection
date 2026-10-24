/**
 * Read-only loaders for the Notebook.
 *
 * The bridge is the only transport. Where F01 has already added `audit()` / `custody()` we use
 * them; until then we fall back to the audit rows and evidence hashes carried by
 * `workspace(caseId)`. No score is ever read, shown or derived.
 */

import type {
  AuditRow,
  BridgeResult,
  CaseSummary,
  CompanionBridge,
  CustodyRow,
  EvidenceRef,
  WorkspaceSnapshot,
} from '../../../../shared/contracts'
import { api } from '../../shared/api'

interface NotebookBridge extends CompanionBridge {
  audit?: () => Promise<BridgeResult<AuditRow[]>>
  custody?: (caseId: string) => Promise<BridgeResult<CustodyRow[]>>
}

const bridge = api as NotebookBridge

export function unwrap<T>(result: BridgeResult<T>): T {
  if (!result.ok) throw new Error(result.error)
  return result.data
}

export interface CaseWorkspace {
  summary: CaseSummary
  snapshot: WorkspaceSnapshot
}

export async function loadCaseWorkspaces(): Promise<CaseWorkspace[]> {
  const cases = unwrap(await api.listCases())
  const settled = await Promise.allSettled(
    cases.map(async (summary) => ({
      summary,
      snapshot: unwrap(await api.workspace(summary.case_id)),
    })),
  )
  return settled.flatMap((item) => (item.status === 'fulfilled' ? [item.value] : []))
}

export async function loadAuditRows(): Promise<AuditRow[]> {
  if (bridge.audit) {
    try {
      return unwrap(await bridge.audit())
    } catch {
      // Fall through to the workspace snapshot: an audit read must never blank the tab.
    }
  }
  const workspaces = await loadCaseWorkspaces()
  return workspaces.flatMap(({ snapshot }) => snapshot.audit)
}

export interface EvidenceBundle {
  evidence: EvidenceRef
  caseId: string
  caseTitle: string
  custody: CustodyRow[]
}

export function evidenceKey(item: Pick<EvidenceBundle, 'caseId' | 'evidence'>): string {
  return `${item.caseId}:${item.evidence.evidence_id}`
}

export async function loadEvidence(): Promise<EvidenceBundle[]> {
  const workspaces = await loadCaseWorkspaces()
  const bundles: EvidenceBundle[] = []

  for (const { snapshot } of workspaces) {
    let caseCustody: CustodyRow[] | null = null
    if (bridge.custody) {
      try {
        caseCustody = unwrap(await bridge.custody(snapshot.case_id))
      } catch {
        caseCustody = null
      }
    }

    for (const evidence of snapshot.evidence) {
      const matching = caseCustody?.filter((row) => row.evidence_id === evidence.evidence_id) ?? []
      const custody =
        matching.length > 0
          ? matching
          : snapshot.audit.map((row) => ({
              evidence_id: evidence.evidence_id,
              at: row.at,
              actor: row.actor,
              action: row.action,
              sha256_short: evidence.sha256_short,
            }))
      bundles.push({
        evidence,
        caseId: snapshot.case_id,
        caseTitle: snapshot.title,
        custody,
      })
    }
  }

  return bundles
}
