/** ReportDraftClient — fake Section 63 / 1930 drafts for instant UI work (T25 §3). */

import type { DraftArtifact } from '../../../shared/contracts'

export interface ReportDraftClient {
  draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<DraftArtifact>
}

export class FakeReportDraftClient implements ReportDraftClient {
  async draft(kind: 'section63' | 'helpline_1930', caseId: string): Promise<DraftArtifact> {
    return {
      version: '1',
      draft_id: `draft_local_${kind}`,
      kind,
      case_id: caseId,
      status: 'DRAFT_REQUIRES_HUMAN_REVIEW',
      submission: 'MANUAL_ONLY',
      auto_submit: false,
      generated_at: new Date().toISOString(),
      fields:
        kind === 'section63'
          ? {
              record_description: 'USER_CONFIRMED_DESCRIPTION_REQUIRED',
              prescribed_form_version: 'COUNSEL_VERIFIED_VERSION_REQUIRED',
              signatory: null,
            }
          : {
              submission: 'MANUAL_ONLY',
              utr: null,
              utr_missing: true,
              loss_amount_inr: null,
              pronunciation_helper: '1930 → one nine three zero',
            },
      disclaimers: [
        'Draft only. A human must review every field before any official use.',
        'Nothing is dialled, transmitted or filed automatically.',
      ],
    }
  }
}
