/** Local preferences in `userData/satya.json`. Never sent anywhere. */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

import { app } from 'electron'

import type { Prefs } from '../shared/contracts'

export const DEFAULT_PREFS: Prefs = {
  size: 'M',
  sound: false,
  sounds: false,
  lang: 'en',
  notice_calls: true,
  source: 'loopback',
}

export function prefsPath(): string {
  return join(app.getPath('userData'), 'satya.json')
}

/** Pure shallow merge with a copied `position` so callers never share the object. */
export function mergePrefs(base: Prefs, patch: Partial<Prefs>): Prefs {
  const next: Prefs = { ...base, ...patch }
  if (patch.position) next.position = { x: patch.position.x, y: patch.position.y }
  return next
}

export function readPrefs(): Prefs {
  try {
    const raw = readFileSync(prefsPath(), 'utf8')
    const parsed = JSON.parse(raw) as Partial<Prefs>
    return mergePrefs(DEFAULT_PREFS, parsed)
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export function writePrefs(patch: Partial<Prefs>): Prefs {
  const next = mergePrefs(readPrefs(), patch)
  try {
    const file = prefsPath()
    mkdirSync(dirname(file), { recursive: true })
    writeFileSync(file, `${JSON.stringify(next, null, 2)}\n`, 'utf8')
  } catch {
    // A read-only profile must not crash the guardian; the window still moves.
  }
  return next
}
