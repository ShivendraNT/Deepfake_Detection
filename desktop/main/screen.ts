/**
 * On-device Screen Guard for Satya.
 *
 * Captures screen via native macOS screencapture and runs Apple Vision OCR locally.
 * Strictly offline, on-device only. Inspects on-screen content for:
 * 1. Urgency / secrecy language & approval bypass attempts
 * 2. New bank accounts, changed IFSCs, or suspicious wire requests
 * 3. Remote access scam tools (AnyDesk, TeamViewer, QuickSupport)
 * 4. Credential theft attempts
 */

import { execFile } from 'node:child_process'
import { existsSync, unlinkSync, writeFileSync } from 'node:fs'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)

export interface ScreenScanResult {
  suspicious: boolean
  headline: string
  matches: string[]
  reasons: string[]
  preview: string
  accounts: string[]
  ifscs: string[]
  rawText: string
}

const FRAUD_PATTERNS = [
  {
    category: 'urgency & secrecy',
    pattern: /\b(urgent|immediately|right away|confidential|keep (it )?secret|between us|do not disclose|strictly private)\b/i,
    label: 'Urgent secrecy request',
  },
  {
    category: 'approval bypass',
    pattern: /\b(bypass|skip (normal )?approval|cfo is traveling|cfo traveling|authorized directly|don'?t call|do not call)\b/i,
    label: 'Approval bypass attempt',
  },
  {
    category: 'bank change',
    pattern: /\b(new bank account|updated account|change beneficiary|new payee details|transfer to new account)\b/i,
    label: 'Bank account change instruction',
  },
  {
    category: 'remote access scam',
    pattern: /\b(anydesk|teamviewer|quicksupport|rustdesk|ultraviewer|screen share to verify)\b/i,
    label: 'Remote access tool detected',
  },
  {
    category: 'credential theft',
    pattern: /\b(send (me )?(your )?(otp|pin|password|cvv)|share screen for otp)\b/i,
    label: 'Credential or OTP request',
  },
]

export function analyzeScreenText(text: string): ScreenScanResult {
  const matches: string[] = []
  const reasons: string[] = []

  for (const rule of FRAUD_PATTERNS) {
    if (rule.pattern.test(text)) {
      matches.push(rule.label)
      reasons.push(rule.label)
    }
  }

  // Account numbers (9-18 digits). Filter out common timestamps / resolutions.
  const rawAccounts = text.match(/\b\d{9,18}\b/g) ?? []
  const accounts = rawAccounts.filter((acc) => !acc.startsWith('202') && !acc.startsWith('1920'))

  // Indian IFSC codes (e.g. FAKC0001234, HDFC0001234, SBIN0001234).
  const ifscs = text.match(/\b[A-Z]{4}0[A-Z0-9]{6}\b/g) ?? []

  if (accounts.length > 0 && ifscs.length > 0) {
    matches.push('Bank account & IFSC on screen')
  }

  const suspicious =
    matches.length >= 2 ||
    matches.some(
      (m) =>
        m.includes('Remote access') ||
        m.includes('Credential') ||
        m.includes('Approval bypass'),
    )

  let headline = 'Screen looks OK'
  if (suspicious) {
    if (matches.some((m) => m.includes('Remote access'))) {
      headline = 'Remote access scam risk on screen'
    } else if (matches.some((m) => m.includes('Approval bypass'))) {
      headline = 'Urgent payment bypass on screen'
    } else {
      headline = `Suspicious payment instruction on screen`
    }
  }

  const preview = text
    .replace(/\b\d{9,18}\b/g, (val) => `••••${val.slice(-4)}`)
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 200)

  return {
    suspicious,
    headline,
    matches,
    reasons: reasons.length > 0 ? reasons : ['No payment fraud indicators detected on screen.'],
    preview,
    accounts,
    ifscs,
    rawText: text,
  }
}

const SWIFT_OCR_SOURCE = `import Cocoa
import Vision

guard CommandLine.arguments.count > 1 else { exit(1) }
let path = CommandLine.arguments[1]
let imageURL = URL(fileURLWithPath: path)
guard let image = NSImage(contentsOf: imageURL),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    exit(1)
}

let request = VNRecognizeTextRequest { req, _ in
    guard let obs = req.results as? [VNRecognizedTextObservation] else { return }
    let strings = obs.compactMap { $0.topCandidates(1).first?.string }
    print(strings.joined(separator: "\\n"))
}
request.recognitionLevel = .fast
let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])
`

const SCRIPT_PATH = '/tmp/satyapan_ocr.swift'
const BINARY_PATH = '/tmp/satyapan_ocr_helper'

async function ensureOcrEngine(): Promise<string> {
  if (existsSync(BINARY_PATH)) {
    return BINARY_PATH
  }

  try {
    if (!existsSync(SCRIPT_PATH)) {
      writeFileSync(SCRIPT_PATH, SWIFT_OCR_SOURCE, 'utf-8')
    }
    // Attempt one-time compile for maximum speed (~150ms OCR vs ~600ms interpreter)
    await execFileAsync('/usr/bin/swiftc', ['-O', SCRIPT_PATH, '-o', BINARY_PATH], { timeout: 8000 })
    if (existsSync(BINARY_PATH)) {
      return BINARY_PATH
    }
  } catch {
    // If compilation fails, interpreter fallback is used
  }

  return SCRIPT_PATH
}

export async function scanScreen(): Promise<ScreenScanResult> {
  const tmpImage = `/tmp/satyapan_screen_${Date.now()}.png`
  try {
    // 1. Capture screen silently via macOS screencapture
    await execFileAsync('/usr/sbin/screencapture', ['-x', tmpImage], { timeout: 3000 })

    // 2. Locate or compile OCR engine
    const enginePath = await ensureOcrEngine()
    let text = ''

    if (enginePath === BINARY_PATH) {
      const { stdout } = await execFileAsync(BINARY_PATH, [tmpImage], { timeout: 4000 })
      text = stdout
    } else {
      const { stdout } = await execFileAsync('/usr/bin/swift', [SCRIPT_PATH, tmpImage], { timeout: 6000 })
      text = stdout
    }

    return analyzeScreenText(text)
  } catch (error) {
    return {
      suspicious: false,
      headline: 'Screen scan error',
      matches: [],
      reasons: [error instanceof Error ? error.message : String(error)],
      preview: '',
      accounts: [],
      ifscs: [],
      rawText: '',
    }
  } finally {
    try {
      if (existsSync(tmpImage)) unlinkSync(tmpImage)
    } catch {}
  }
}
