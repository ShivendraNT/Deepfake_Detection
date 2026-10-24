import { describe, expect, it } from 'vitest'

import { DEMO_REPLAY_LABEL, MODE_LABELS } from '../shared/contracts'

describe('desktop smoke tests', () => {
  it('exports required mode and replay labels', () => {
    expect(DEMO_REPLAY_LABEL).toBe('DEMO REPLAY — NOT LIVE CAPTURE')
    expect(MODE_LABELS.SLEEP).toBe('Sleep / DND')
    expect(MODE_LABELS.ACTIVE).toBe('Watching')
  })
})
