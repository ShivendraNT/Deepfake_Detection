# Live demo runbook — a real call, flagged in real time

This is how we show Satya working **live** in front of the judges: a real Google Meet call between
two laptops, a teammate playing a deepfake "CFO", and the approver's real phone. Nothing is
pre-recorded unless we say so out loud (the labelled DEMO REPLAY is the fallback, not the plan).

```
 Laptop B ("CFO", attacker)          Laptop A (Priya, presenter)                Phone (real Rajesh)
 joins Google Meet  ── internet ──►  Meet in Chrome, sound ON                    same hotspot as A
 reads the script                    Satya: hears system audio (never the mic)   opens the QR link
                                     local Whisper → asks → policy band ──OOB──► "Did you ask for this?"
```

## 1. Night before (each presenter laptop, needs internet once)

```bash
make sync            # Python deps (keeps the speech engine if it is already installed)
make asr             # local speech engine + model download + a speed check
make demo-audio      # the labelled DEMO REPLAY call (synthetic Piper voice, git-ignored)
make doctor          # must end with "✓ Fast enough for live captions"
cd desktop && npm install && npm run build
```

`make doctor` transcribes the replay call sentence by sentence and prints the asks it hears. On an
8+ core laptop it uses Whisper `small`, on smaller ones `base`; Apple Silicon uses `mlx-whisper`.
If the slowest sentence takes more than ~2.5 s, run the demo with `SATYAPAN_ASR_MODEL=base`.

**Permissions (do this the night before, then restart the app):**

| OS | What Satya needs | Where |
|---|---|---|
| macOS 13+ (14.2+ best) | Screen & System Audio Recording (system audio, meeting window names, Screen Guard OCR) | System Settings → Privacy & Security → Screen & System Audio Recording. Enable **the app that launches Satya**: started from Terminal / iTerm / VS Code, macOS asks on behalf of *that* app. Or launch Electron itself after `npm run build`: `open node_modules/electron/dist/Electron.app --args "$(pwd)"` and allow Electron. |
| Windows 10/11 | nothing for audio; an English OCR language pack for Screen Guard | Settings → Time & language → Language |
| Linux | dev only: the replay works; system-audio capture depends on PipeWire/PulseAudio | — |

**Prove the ears on the stage laptop (2 minutes, do not skip):** wake Satya, play any YouTube
talk, press `Ctrl/⌘+Shift+L`. Captions must appear in Notebook → Now within a few seconds. Silence
on macOS → re-check the permission above (then quit and relaunch), and see `team/Kartikey.md`
step 0 (Info.plist `NSAudioCaptureUsageDescription`). System-audio capture was verified on Linux
with the replay; it has to be rehearsed on the actual demo laptop.

**Network:** venue Wi-Fi usually isolates devices, so the phone could not reach the laptop. Use a
**phone hotspot** that laptop A and the approver's phone both join (Meet runs over it too).

## 2. Before the judges arrive (5 minutes)

1. Terminal 1: `make live` (no auto-reload; the model warms up in the background).
2. Terminal 2: `cd desktop && npm run preview` (the built app; `npm run dev` for rehearsals).
3. Open the Notebook (`Ctrl/⌘+Shift+U`) → **Now** → **Ready for a live call?** Everything green:
   local engine, ears (engine · model · ready), vendor master. The voice-clone detector row is
   optional and stays amber (model files are not shipped, see §6).
4. The approver scans the QR on that card with their phone (it encodes
   `http://<laptop-A-ip>:8000/oob`). The page says "Waiting for a request…".
   Run `make oob-check` once after `make live`: it creates a demo request, opens the served page
   and answers "I did not request this", so you know the phone path works before the judges arrive.
5. Laptop B creates the Meet; laptop A joins it in Chrome. **Sound on**, volume above ~30%.
   Speakers or headphones both work: Satya taps what the laptop plays, never the microphone, so he
   hears only the other side of the call.
6. Presenter menu (tray icon): if the projector gets laptop A's screen through a screen-sharing or
   recording tool (not a plain HDMI mirror), untick **Hide Satya from screen sharing &
   recordings**, or the judges will not see him. With HDMI mirroring, leave it on.
7. Put Satya to sleep (`Ctrl/⌘+Shift+S`). He starts every demo asleep: consent first.

## 3. The run (about 3 minutes)

| # | Presenter does | What the judges see |
|---|---|---|
| 1 | `Ctrl/⌘+Shift+S`, then tick the scopes on the consent card and accept | Satya wakes up, stretches, waves. Nothing is captured before this yes. |
| 2 | (Meet already open) | Satya notices the Meet window: "You're in a Google Meet call. Want me to listen for payment tricks? I won't record it." |
| 3 | Click **Listen** (or `Ctrl/⌘+Shift+L`) | Headphones on. Live card: "Listening to Google Meet". |
| 4 | Laptop B reads the script below, pausing between sentences | Captions appear about a second after each sentence; asks and cues light up; Satya goes alert. |
| 5 | — | Band: **Verify first**, then **On hold** once two different tricks are heard. The alert quotes the exact words. |
| 6 | Click **Verify with Rajesh Iyer** | The approver's phone buzzes with the exact question. |
| 7 | Approver taps **I did not request this** | Satya holds up his shield: "Rajesh Iyer says they didn't ask for this. I've put the payment on hold." |
| 8 | Notebook → **Reports** → "It left just now", type a fake UTR (`FAKEUTR998877`), **Write my report pack** | Golden-hour timer, 1930 script, NCRP fields, bank recall letter, typed live. "Drafts only. Nothing has been sent." |
| 9 | Notebook → **Cases** → **Expert view: how the policy decided** | Floor from the vendor master, each raise-only signal, what clears it. No scores. |
| 10 | Optional: open `data/demo/emails/02_bec_bank_change_narmada.eml` in a text editor, press `Ctrl/⌘+Shift+K` | Screen Guard: "I noticed something on your screen": Narmada's "updated bank details" and "new account", an account (••••9917) that is not in the vendor master, and the rush ("today itself"). |

**Script for laptop B** (say it naturally; fictional people and amounts):

> Hi Priya, this is Rajesh. I'm stuck in a board meeting, so I can't talk long.
>
> We are closing a confidential acquisition today. I need you to transfer forty-eight lakh
> rupees to a new escrow account.
>
> I'll send you the account details on chat. Please don't loop in Arjun, keep this between us.
>
> Skip the usual approval. I'll sign it off later.

Ad-libs that also work: "the old account is blocked, use the new details", "read me the code you
just got", "install AnyDesk so I can help", "buy gift cards", Hinglish ("kisi ko mat batana",
"baad mein sign kar dunga"). A spoken warning ("never share your OTP") is filtered out and does
not raise anything.

**Make it a deepfake (optional):** laptop B can run a real-time voice changer, or a voice clone of
a teammate who signed `docs/consent/`. Satya's live flag does not depend on recognising the fake
voice: it flags what the caller *asks for* against the payment. That is the point of the demo.

### 3b. Consumer variant (Stage 2 "live user journey"): a "digital arrest" call

Start the engine with `make live-personal` (Windows: `uv run python scripts/satya.py
live-personal`): no company approver, so the alert speaks to a person. Laptop B calls laptop A
on any app and says, in English or Hinglish:

> This is CBI. Your Aadhaar is linked to money laundering. You are under digital arrest.
> Don't tell anyone. Transfer fifty thousand rupees to the RBI safe account and read me the OTP.

| # | What the judges see |
|---|---|
| 1 | Captions; chips for the new / "safe" account, secrecy, OTP |
| 2 | Alert: **"Stop: don't pay or share any code on this call"**, the exact words quoted, and why: real police, banks and officials never ask for money, a code or secrecy on a call |
| 3 | Actions: *Copy a safe reply, then hang up* · *Money sent? Call 1930* (opens the dialler) · *Prepare my report* (opens `/check#money`: UTR → 1930 script, bank message, portal fields) |
| 4 | Same script as a screenshot, a voice note or a video on `http://127.0.0.1:8000/check` (or a phone on the same Wi-Fi) → the same answer; a genuine bank OTP SMS → PASS |

Checked in code: `tests/finale/test_companion_finale.py::test_a_personal_call_gets_consumer_actions_not_an_approver`.

## 4. Fallbacks, in order

1. **Satya hears nothing** (no captions after two sentences): check volume and the macOS
   permission. Still nothing and the call is Meet in Chrome → the Chrome extension's side panel
   (`extension/`, tab capture) runs the same live engine on the Meet tab. Last resort →
   `Ctrl/⌘+Shift+D` plays the DEMO REPLAY through Satya's pipeline (audible, labelled
   "DEMO REPLAY — NOT LIVE CAPTURE"). Say so out loud.
2. **Captions too slow:** restart terminal 1 with `SATYAPAN_ASR_MODEL=base make live`
   (`tiny.en` if still slow).
3. **Phone cannot reach the laptop:** open `http://127.0.0.1:8000/oob` in a browser window on
   laptop A and answer there.
4. **Engine crashed:** after two failed sentences Satya says "I can't reach my brain" and goes to
   sleep (fail closed). Restart `make live`, then wake him again.
5. **Emergency stop** at any moment: `Ctrl/⌘+Shift+.` stops listening and reading at once.

## 5. Hotkeys

| Keys | Action |
|---|---|
| `Ctrl/⌘+Shift+S` | wake / sleep |
| `Ctrl/⌘+Shift+L` | listen to the call I am on |
| `Ctrl/⌘+Shift+K` | scan my screen now |
| `Ctrl/⌘+Shift+Y` | check what I copied |
| `Ctrl/⌘+Shift+U` | open the Notebook |
| `Ctrl/⌘+Shift+D` | play the labelled demo replay |
| `Ctrl/⌘+Shift+.` | stop everything now |

## 6. What is real, and what is not (say this if asked)

- **Real, live:** system-audio capture of the call, on-device Whisper (no audio leaves the
  laptop), utterance cutting at pauses, ask and cue detection, the policy band, the OOB question
  on the approver's own phone, the report pack drafts, Screen Guard OCR on this laptop.
- **Voice clone:** the voice model is built locally with `make voice` (licensed, selected by the
  benchmark in `docs/VOICE_DEEPFAKE.md`); without it the answer says "voice clone: not checked
  here". The band never depended on it.
- **Never:** no microphone capture; no transcript stored (captions live in memory for the call and
  never cross the companion bus); no auto-reporting (there is no public 1930/NCRP API; a human
  submits every draft); no band set anywhere but `satyapan.policy`, and evidence can only raise it.
