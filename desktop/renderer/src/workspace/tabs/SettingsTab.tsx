import {
  Bell,
  Check,
  Globe2,
  Keyboard,
  QrCode,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { DEFAULT_SCOPES, type AppConfig, type Lang, type Prefs, type Scopes } from '../../../../shared/contracts'
import { api } from '../../shared/api'
// qrcode@1.5.4 ships no TypeScript declarations; Vite still resolves the runtime package.
// @ts-expect-error - the package has no bundled types and this project does not add @types/qrcode.
import QRCode from 'qrcode'
import Section from '../ui/Section'
import { FONT_MONO, focusRing, inset, surface, tone } from '../ui/theme'

const DEFAULT_PREFS: Prefs = {
  size: 'M',
  sounds: false,
  lang: 'en',
  notice_calls: true,
  source: 'replay',
}

function Toggle({
  checked,
  label,
  onChange,
}: {
  checked: boolean
  label: string
  onChange: (next: boolean) => void
}): JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`${focusRing} relative h-6 w-11 shrink-0 rounded-full transition`}
      style={{ backgroundColor: checked ? tone.watch : 'rgba(140,150,170,0.35)' }}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all ${
          checked ? 'left-[22px]' : 'left-0.5'
        }`}
        aria-hidden="true"
      />
    </button>
  )
}

function Segment({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: string
  onClick: () => void
}): JSX.Element {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`${focusRing} rounded-[8px] px-3 py-1.5 text-[12px] font-medium transition ${
        active ? `${surface.card} shadow-sm` : `${surface.muted} ${surface.hover}`
      }`}
    >
      {children}
    </button>
  )
}

function SettingRow({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: JSX.Element
}): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-[13px] font-medium">{title}</p>
        <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>{description}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

const LANGS: Array<{ value: Lang; label: string }> = [
  { value: 'en', label: 'EN' },
  { value: 'hinglish', label: 'Hinglish' },
  { value: 'hi', label: 'हिन्दी' },
]

const HOTKEYS = [
  { keys: 'Ctrl/⌘ + Shift + S', action: 'Wake or sleep Satya' },
  { keys: 'Ctrl/⌘ + Shift + .', action: 'Stop everything now (emergency)' },
  { keys: 'Ctrl/⌘ + Shift + L', action: 'Listen to the call I am on' },
  { keys: 'Ctrl/⌘ + Shift + K', action: 'Scan my screen now' },
  { keys: 'Ctrl/⌘ + Shift + Y', action: 'Check what I copied' },
  { keys: 'Ctrl/⌘ + Shift + U', action: 'Open the Notebook' },
  { keys: 'Ctrl/⌘ + Shift + D', action: 'Play the demo call (labelled replay)' },
]

const CALL_LANGS: Array<{ value: 'en' | 'hi' | 'auto'; label: string }> = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'auto', label: 'Auto-detect' },
]

export default function SettingsTab(): JSX.Element {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS)
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [saved, setSaved] = useState(false)
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null)
  const oobUrl = config?.oob_url ?? ''

  useEffect(() => {
    let active = true
    void Promise.all([api.getPrefs(), api.getConfig()]).then(([stored, nextConfig]) => {
      if (!active) return
      setPrefs({ ...DEFAULT_PREFS, ...stored })
      setConfig(nextConfig)
    })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    if (!oobUrl) {
      setQrDataUrl(null)
      return () => {
        active = false
      }
    }
    void QRCode.toDataURL(oobUrl, {
      width: 160,
      margin: 1,
      color: { dark: '#2A2238', light: '#FFFFFF' },
    })
      .then((url: string) => {
        if (active) setQrDataUrl(url)
      })
      .catch(() => {
        if (active) setQrDataUrl(null)
      })
    return () => {
      active = false
    }
  }, [oobUrl])

  async function update(patch: Partial<Prefs>): Promise<void> {
    setPrefs((current) => ({ ...DEFAULT_PREFS, ...current, ...patch }))
    try {
      const stored = await api.setPrefs(patch)
      setPrefs({ ...DEFAULT_PREFS, ...stored })
      setSaved(true)
      window.setTimeout(() => setSaved(false), 1600)
    } catch {
      // Preferences are local. If storage is unavailable, the current tab keeps them.
    }
  }

  const size = prefs.size ?? 'M'
  const lang = prefs.lang ?? 'en'
  const sounds = prefs.sounds ?? prefs.sound ?? false
  const scopes = { ...DEFAULT_SCOPES, ...(prefs.scopes ?? {}) }

  async function updateScopes(next: Scopes): Promise<void> {
    await update({ scopes: next })
    await api.setScopes?.(next)
  }

  return (
    <div className="space-y-4">
      <Section title="Satya" description="Small changes, saved on this laptop only.">
        <div className="divide-y divide-[rgba(42,34,56,0.08)] dark:divide-[rgba(237,232,245,0.08)]">
          <SettingRow title="Mascot size" description="How large Satya sits on your screen.">
            <div className={`flex items-center gap-1 rounded-[10px] border p-1 ${surface.line} ${inset}`}>
              {(['S', 'M', 'L'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={size === option}
                  aria-label={`Mascot size ${option}`}
                  onClick={() => void update({ size: option })}
                  className={`${focusRing} grid h-8 w-9 place-items-center rounded-[8px] text-[12px] font-semibold transition ${
                    size === option ? `${surface.card} shadow-sm` : surface.muted
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </SettingRow>

          <SettingRow
            title="Sound effects"
            description="A soft chime when a check finishes. Off by default."
          >
            <Toggle
              checked={sounds}
              label="Sound effects"
              onChange={(next) => void update({ sounds: next })}
            />
          </SettingRow>
        </div>
      </Section>

      <Section title="Language" description="Satya's cards and explanations follow this choice.">
        <div className={`inline-flex items-center gap-1 rounded-[10px] border p-1 ${surface.line} ${inset}`}>
          {LANGS.map((option) => (
            <Segment
              key={option.value}
              active={lang === option.value}
              onClick={() => void update({ lang: option.value })}
            >
              {option.label}
            </Segment>
          ))}
        </div>
        <p className={`mt-3 flex items-center gap-1.5 text-[12px] ${surface.muted}`}>
          <Globe2 size={13} aria-hidden="true" />
          Hindi and Hinglish copy is shared with the mascot cards.
        </p>
      </Section>

      <Section title="Watching" description="What Satya may notice, and where it comes from.">
        <div className="divide-y divide-[rgba(42,34,56,0.08)] dark:divide-[rgba(237,232,245,0.08)]">
          <SettingRow
            title="Notice calls automatically"
            description="A small card asks before Satya listens. The microphone stays closed."
          >
            <Toggle
              checked={scopes.meetings}
              label="Notice calls automatically"
              onChange={(next) => void updateScopes({ ...scopes, meetings: next })}
            />
          </SettingRow>

        <SettingRow
            title="Glance at my screen for payment tricks"
            description="On-device text reading every few seconds. Nothing is stored."
          >
            <Toggle
              checked={scopes.screen}
              label="Glance at my screen"
              onChange={(next) => void updateScopes({ ...scopes, screen: next })}
            />
          </SettingRow>
          <SettingRow
            title="Hide Satya from screen sharing and recordings"
            description="A caller watching your shared screen never sees the warning. Turn off to record a demo video."
          >
            <Toggle
              checked={prefs.hide_from_capture !== false}
              label="Hide Satya from screen sharing"
              onChange={(next) => void update({ hide_from_capture: next })}
            />
          </SettingRow>
        </div>
        <p className={`mt-3 text-[12px] font-medium ${surface.muted}`}>Call language</p>
        <div className={`mt-2 inline-flex rounded-[10px] p-1 ${inset}`}>
          {CALL_LANGS.map((item) => (
            <Segment
              key={item.value}
              active={(prefs.call_language ?? 'en') === item.value}
              onClick={() => void update({ call_language: item.value })}
            >
              {item.label}
            </Segment>
          ))}
        </div>
        <p className={`mt-2 text-[12px] ${surface.muted}`}>
          Only helps the speech engine. Language and accent are never a risk signal.
        </p>
      </Section>

      <Section title="Hotkeys" description="Global shortcuts. They work even when the Notebook is closed.">
        <ul className="space-y-2">
          {HOTKEYS.map((hotkey) => (
            <li key={hotkey.keys} className="flex items-center justify-between gap-4 text-[12px]">
              <span className={surface.muted}>{hotkey.action}</span>
              <kbd
                className={`rounded-[6px] border px-2 py-1 text-[12px] ${surface.line} ${inset}`}
                style={{ fontFamily: FONT_MONO }}
              >
                {hotkey.keys}
              </kbd>
            </li>
          ))}
        </ul>
        <p className={`mt-3 flex items-center gap-1.5 text-[12px] ${surface.muted}`}>
          <Keyboard size={13} aria-hidden="true" />
          Stop listening is always available.
        </p>
      </Section>

      <Section title="Approver's phone" description="Open this on the approver's phone (same Wi-Fi or hotspot). Satya asks there, not on the call.">
        <div className={`flex items-start gap-4 rounded-[14px] border p-4 ${surface.line} ${inset}`}>
          <div
            className="grid h-24 w-24 shrink-0 place-items-center rounded-[12px] border bg-white p-1"
            style={{ borderColor: 'rgba(42,34,56,0.12)' }}
          >
            {qrDataUrl ? (
              <img
                src={qrDataUrl}
                alt="Scan with phone"
                width={88}
                height={88}
                className="h-full w-full rounded-[8px] object-contain"
              />
            ) : (
              <QrCode size={48} style={{ color: tone.ink }} aria-hidden="true" />
            )}
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-medium">Scan with the approver's phone</p>
            <p className={`mt-1 text-[12px] leading-relaxed ${surface.muted}`}>
              Scan this code to open the approval page on the approver's own phone. The approver and
              the channel come only from the employee directory.
            </p>
            <code
              className={`mt-2 block break-all rounded-[6px] border px-2 py-1 text-[12px] ${surface.line} ${surface.card}`}
              style={{ fontFamily: FONT_MONO }}
            >
              {oobUrl || 'No approver URL configured yet'}
            </code>
          </div>
        </div>
      </Section>

      <div className="flex h-5 items-center justify-end gap-1.5 text-[12px]" aria-live="polite">
        {saved ? (
          <>
            <Check size={13} style={{ color: tone.green }} aria-hidden="true" />
            <span className={surface.muted}>Saved on this laptop</span>
          </>
        ) : (
          <>
            <Bell size={13} className={surface.muted} aria-hidden="true" />
            <span className={surface.muted}>Changes apply immediately</span>
          </>
        )}
      </div>
    </div>
  )
}
