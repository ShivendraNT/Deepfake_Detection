import * as React from 'react'
import { beforeAll, describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

// Provide globals needed in Node test environment before importing renderer modules
;(globalThis as any).React = React

beforeAll(() => {
  if (typeof globalThis.window === 'undefined') {
    const win = {
      location: { search: '', href: 'http://localhost:5174/?view=workspace' },
      addEventListener: () => {},
      removeEventListener: () => {},
      localStorage: {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
      },
    }
    ;(globalThis as any).window = win
    ;(globalThis as any).localStorage = win.localStorage
  }
})

function textOf(html: string): string {
  return html.replace(/<[^>]+>/g, ' ')
}

describe('Workspace Notebook (F14)', () => {
  it('1. renders BandBadge with human words and never raw scores', async () => {
    const { default: BandBadge } = await import('../renderer/src/workspace/ui/BandBadge')
    const passHtml = renderToString(React.createElement(BandBadge, { band: 'PASS' }))
    const verifyHtml = renderToString(React.createElement(BandBadge, { band: 'VERIFY' }))
    const holdHtml = renderToString(React.createElement(BandBadge, { band: 'HOLD' }))

    expect(passHtml).toContain('Looks OK')
    expect(verifyHtml).toContain('Verify first')
    expect(holdHtml).toContain('On hold')

    // Invariant: Visible text never contains raw score numbers
    expect(textOf(passHtml)).not.toMatch(/0\.\d+/)
    expect(textOf(verifyHtml)).not.toMatch(/0\.\d+/)
    expect(textOf(holdHtml)).not.toMatch(/0\.\d+/)
  })

  it('2. masks bank account numbers and formats INR currency', async () => {
    const { maskAccount, formatInr } = await import('../renderer/src/workspace/lib/format')
    expect(maskAccount('999912344821')).toBe('••••4821')
    expect(maskAccount('••••4821')).toBe('••••4821')
    expect(formatInr(4850000)).toBe('₹48,50,000')
  })

  it('3. renders NowTab with local privacy assurance and without raw scores', async () => {
    const { default: NowTab } = await import('../renderer/src/workspace/tabs/NowTab')
    const { EMPTY_LIVE } = await import('../renderer/src/workspace/lib/live')
    const html = renderToString(
      React.createElement(NowTab, {
        state: null,
        live: EMPTY_LIVE,
        onOpenCase: () => {},
      })
    )
    expect(html).toContain('Live monitoring')
    expect(html).toContain('What Satya can see')
    expect(html).toContain('What he never does')
    expect(textOf(html)).not.toMatch(/0\.\d+/)
  })

  it('4. renders PrivacyTab with the non-negotiable local audio guarantee', async () => {
    const { default: PrivacyTab } = await import('../renderer/src/workspace/tabs/PrivacyTab')
    const html = renderToString(
      React.createElement(PrivacyTab, {
        state: null,
      })
    )
    expect(html).toContain('Satya runs on this laptop')
    expect(html).toContain('He never uses your microphone')
    expect(html).toContain('Call audio stays in memory')
  })

  it('5. renders SettingsTab and displays OOB approver phone section', async () => {
    const { default: SettingsTab } = await import('../renderer/src/workspace/tabs/SettingsTab')
    const html = renderToString(React.createElement(SettingsTab))
    expect(html).toContain('Approver&#x27;s phone')
    expect(html).toContain('Scan with the approver&#x27;s phone')
    expect(html).toContain('Notice calls automatically')
  })
})

