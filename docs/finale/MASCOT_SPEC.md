# Satya — mascot, motion and copy spec

> Owner: **Saarika** (mascot + bubble). Notebook styling: **Saksham** (uses §2 tokens).
> Read this before writing any UI code. **Copy the numbers exactly.** Cuteness here comes from the
> spec, not from the model's imagination. If something isn't specified, ask; don't improvise.

---

## 1. Who Satya is

- **Satya** (सत्य, "truth") — a small, round guardian spirit with big listening ears. Think: a
  chubby little chowkidar who is proud of his job, a bit sleepy, never scary.
- **Personality:** calm, warm, slightly earnest. He *pauses* you; he never panics or shouts.
- **Voice:** short sentences, "I" statements, no jargon, no exclamation marks except when
  something good happens.
- **Original character.** Do not make him look like any existing brand mascot or cartoon.
  No owls (too close to a well-known app), no robots, no shields-with-faces.

**Silhouette test:** a round body + two tall rounded ears + two big eyes. If the silhouette alone
reads as "cute round creature with big ears", it works.

---

## 2. Design tokens (put these in `desktop/renderer/src/shared/tokens.ts`)

```ts
export const color = {
  body: '#E9B783',      // warm caramel
  bodyDark: '#D49A62',  // feet, paws
  tummy: '#FFF3E0',
  earInner: '#F6A79B',
  ink: '#2A2238',       // eyes, mouth, brows
  blush: '#FF8FA3',
  sticker: '#FFFFFF',   // outline so he reads on ANY wallpaper
  shadow: 'rgba(26,20,48,0.18)',
  // one accent per state — never two at once
  watch: '#1FB5A3',     // teal: watching / listening
  verify: '#FFB020',    // amber: VERIFY / alert
  hold: '#FF6B5E',      // coral: HOLD
  write: '#9C8CFF',     // lavender: scribe
  good: '#3CCB7F',      // green: relief / PASS
  sleep: '#8C96AA',     // slate: sleeping / off
} as const

export const ui = {
  light: { card: 'rgba(255,252,247,0.97)', text: '#2A2238', muted: '#6B6478',
           line: 'rgba(42,34,56,0.10)', paper: '#FBF8F3', sidebar: '#F3EEE6' },
  dark:  { card: 'rgba(28,24,40,0.96)', text: '#EDE8F5', muted: '#A8A0B8',
           line: 'rgba(237,232,245,0.10)', paper: '#16131F', sidebar: '#1D1928' },
  radius: { card: 18, button: 10, chip: 999 },
  shadow: '0 12px 32px rgba(20,16,40,0.22)',
  font: { sans: 'Inter, "Noto Sans Devanagari", system-ui, sans-serif',
          mono: '"JetBrains Mono", ui-monospace, monospace' },
} as const

export const motion = {
  soft:   { type: 'spring', stiffness: 220, damping: 18 },
  snappy: { type: 'spring', stiffness: 420, damping: 24 },
  enter:  { duration: 0.18, ease: [0.2, 0.8, 0.2, 1] },
  exit:   { duration: 0.12, ease: 'easeIn' },
} as const

export const size = { S: 72, M: 96, L: 128 } as const   // rendered px; window stays 280×280
```

Fonts are already in the repo (`docs/pitch/round1/src/fonts/`: Inter, Noto Sans Devanagari,
JetBrains Mono). Copy them into `desktop/renderer/src/assets/fonts/` and load with `@font-face`.
**No Google Fonts at runtime** — the demo must work offline.

---

## 3. The drawing (SVG, viewBox `0 0 200 200`)

Draw layers in this order (first = back). Each layer is a `<motion.g id="…">` so it can animate
on its own. Transform origins are given for the groups that rotate or scale.

| # | id | Shape | Fill / stroke |
|---|---|---|---|
| 1 | `shadow` | `ellipse cx=100 cy=188 rx=44 ry=7` | `color.shadow` |
| 2 | `aura` | `circle cx=100 cy=120 r=80`, no fill | stroke = state accent, width 3, opacity 0 by default |
| 3 | `ear-l` (origin 76 80) | outer `M58 84 C50 62 50 42 56 28 C70 34 86 48 94 66 Z` + inner `M64 76 C59 60 59 46 62 38 C71 44 80 53 85 64 Z` | outer `body`, inner `earInner`; outer stroke `sticker` 5 |
| 4 | `ear-r` (origin 124 80) | outer `M142 84 C150 62 150 42 144 28 C130 34 114 48 106 66 Z` + inner `M136 76 C141 60 141 46 138 38 C129 44 120 53 115 64 Z` | same as ear-l |
| 5 | `body` (origin 100 180) | `M100 58 C141 58 164 84 166 120 C168 156 142 180 100 180 C58 180 32 156 34 120 C36 84 59 58 100 58 Z` | `body`, stroke `sticker` 5, `paint-order: stroke` |
| 6 | `tummy` | `M100 132 C122 132 136 146 136 160 C136 172 120 178 100 178 C80 178 64 172 64 160 C64 146 78 132 100 132 Z` | `tummy` |
| 7 | `feet` | `ellipse 80 180 15 7` and `ellipse 120 180 15 7` | `bodyDark` |
| 8 | `cheeks` | `ellipse 64 128 10 6` and `ellipse 136 128 10 6` | `blush`, opacity 0.6 |
| 9 | `eyes` (origin 100 112) | left `ellipse 80 112 10 12`, right `ellipse 120 112 10 12`; highlights `circle 84 107 r3.5`, `circle 77 116 r1.6` (and +40 x for the right eye) | `ink`; highlights `#fff` |
| 10 | `brows` (hidden by default) | `M70 96 Q80 92 89 97` and `M111 97 Q120 92 130 96` | stroke `ink` 3, round caps |
| 11 | `mouth` | default `M94 126 Q100 131 106 126` | stroke `ink` 2.6, round, no fill |
| 12 | `paws` (hidden by default) | `ellipse 62 150 9 8` and `ellipse 138 150 9 8` | `bodyDark`, stroke `sticker` 3 |
| 13 | accessories | see §4 (`zzz`, `rings`, `shield`, `glasses`, `quill`, `sparkles`) | per pose |

Mouth variants (swap the `d`): `smile` (default) · `o` = `M97 127 a3 3.5 0 1 0 6 0 a3 3.5 0 1 0 -6 0` ·
`flat` = `M94 128 L106 128` · `happy` = `M92 124 Q100 134 108 124` · `tiny` = `M98 128 Q100 129.5 102 128`.

Eye variants: `open` (as drawn) · `closed` = arcs `M70 114 Q80 120 90 114` + `M110 114 Q120 120 130 114`
(stroke ink 3) · `happy` = arcs `M70 116 Q80 106 90 116` + mirror · `wide` = rx 11 ry 14.

Whole-figure filter (static, never animated): `drop-shadow(0 4px 10px rgba(20,16,40,0.25))`.

---

## 4. Poses (`Pose` from `contracts.ts`)

`Mascot` gets `{ pose, audioLevel, look, size, reducedMotion }` and renders the pose from a data
table in `companion/poses.ts`. **Every pose is data, not new JSX.**

| Pose | Eyes | Ears (deg, L/R) | Body | Mouth | Accessory | Aura | Loop |
|---|---|---|---|---|---|---|---|
| `sleep` | closed | −18 / +18 (droop) | scaleY 0.96 | tiny | `zzz` | — | breathe 4.8 s, 1 → 1.035 |
| `idle` | open, look-at on | 0 / 0 | 1 | smile | — | — | breathe 3.6 s, 1 → 1.025; blink; random ear twitch 8–15 s |
| `listen` | open, ry 13 | −6 / +6, y −4 (perked) | 1 | smile | `rings` (follow `audioLevel`) | `watch` 0.25 | head tilt ±4° every 6 s; blink |
| `think` | open, look up-right (+3, −3) | 0 / 0 | sway ±2°, 1.2 s | flat | 3 dots above head | — | dots pulse 0.9 s stagger 0.15 s |
| `alert` | wide | −2 / +2 (straight up) | one hop (−12 px) then still | flat | `shield` in right paw, `brows` on (concerned) | `verify` (or `hold`) pulse ×2 then steady 0.5 | no loop after the hop. **No shaking.** |
| `relief` | happy | +8 / −8 (relaxed) | hop −8 px | happy | `sparkles` ×3 | `good` fade out 1.2 s | returns to `idle` after 3 s |
| `write` | open, look down (0, +3) | −4 / +4 | 1 | tiny | `glasses` + `quill` in right paw + paper strip at feet | `write` 0.25 | quill draws small loops 0.6 s; a line appears on the paper every 0.8 s |
| `catch` | wide, look at the dragged file | −6 / +6 | scaleY 1.05 (stretch up) | o | `paws` up | — | on drop: squash to 0.9 then spring back (snappy) |
| `wave` | happy | 0 / 0 | 1 | happy | right paw waves 3× (rotate ±20°, 0.25 s) | — | once, on enable |
| `off` | closed | droop | waves, then scale → 0 + fade 0.35 s | tiny | right paw wave | — | once, on Off |

**Accessories (draw simply — flat shapes, 2–3 colours, sticker outline 3 px):**
- `zzz`: three "z" in `ink` 40% opacity, 10/12/14 px, float from (132, 62) up-right 24 px, fade
  out, loop 2.4 s, staggered 0.8 s.
- `rings`: two arcs each side next to the ears (e.g. `M40 70 Q30 90 40 110`, scaled copies).
  `scale = 1 + 0.35 × level`, `opacity = 0.25 + 0.6 × level`, colour `watch`. Smooth with
  `motion.soft`.
- `shield`: rounded shield ~30×34 px at (138, 140), fill `verify` (or `hold`), with a **white
  ring** in the middle (circle r 7, stroke 3). It means "let's check", not "danger". No "!" mark.
- `glasses`: two circles r 12 around the eyes, stroke `ink` 2.5, bridge `M92 112 L108 112`.
- `quill`: a simple feather (lavender) ~34 px, angled 30°, tip near (146, 160).
- `sparkles`: three 4-point stars, 8–12 px, `good`, pop in with `snappy`, fade 1.2 s.

---

## 5. Motion rules

| Behaviour | Spec |
|---|---|
| Blink | every random 2.5–6 s; eyes scaleY 1 → 0.08 → 1 over 140 ms; 20 % chance of a double blink. Not in `sleep`/`off`. |
| Look-at | eyes translate `x = clamp(dx/40, −4, 4)`, `y = clamp(dy/40, −3, 3)` with `motion.soft`. Only when `look.near` (< 500 px); otherwise drift back to centre. |
| Ear twitch | one ear rotates +8° and back in 220 ms. On hover; random in `idle`; in `listen` on audio peaks > 0.6, max once per 1.5 s. |
| Press | body scaleY 0.94 while pointer is down. |
| Drag | tilt = `clamp(vx × 0.4, −8°, 8°)`, scaleY 0.96. On release: wobble back with `motion.soft`. |
| Radial menu | 5 petals (40 px circles, icon 18 px) from the centre out to radius 78 px, scale 0 → 1, stagger 35 ms, `motion.snappy`. Close: reverse in 120 ms. Near a screen edge use a 180° arc facing inward. Tooltip label after 400 ms hover. |
| Bubble card | enter: opacity 0 → 1, y 8 → 0, scale 0.98 → 1, `motion.enter`. Exit `motion.exit`. Card swap = exit then enter (never two visible). |
| Reduced motion | if `prefers-reduced-motion`: no loops, no hops, no look-at; pose changes become 150 ms fades. |

**Performance (must hold on the stage laptop):**
- Animate only `transform` and `opacity`. Never animate `filter`, `width/height`, or SVG `d`
  strings every frame (swap `d` only on pose change).
- One `requestAnimationFrame` loop at most (look-at). Framer Motion handles the rest.
- Mascot window idle CPU < 3 % on the M4 (check Activity Monitor). If higher, kill the loop that
  costs most.

---

## 6. Sound

Off by default, except an optional soft chime for file results. Use `companion/chime.ts`
(WebAudio, no files).
- `chime.result`: sine 660 Hz → 880 Hz, 90 ms each, gain 0.08.
- `chime.relief`: 880 Hz → 1320 Hz, same.
- **No sound while Listening to a call** (the caller could hear it on speakers, and it is
  distracting). Alerts during calls are visual only.

---

## 7. Bubble card design

- Width 340 (window 360 leaves room for the tail). Radius 18. Padding 16. Background `ui.*.card`,
  1 px border `ui.*.line`, shadow `ui.shadow`. Follow the OS light/dark theme.
- **Tail**: 12 px triangle on the side that faces Satya.
- **Header row**: tiny state dot (accent colour) + title 15 px / 600. Body 13.5 px / 1.45.
- **Chips**: 12 px, pill, padding 4×10, background = accent at 14 % opacity, text = ink.
  All ask chips use the same colour (no rainbow).
- **Buttons**: max 3. Full-width, stacked, 36 px tall, radius 10, primary first.
  Primary = filled with the state accent and white text; outline; ghost.
- Close "×" (ghost, 28 px) top-right only on dismissible cards.
- Numbers: Indian format `₹48,50,000`. Accounts always masked `••••4821` unless revealed.

**Anti-slop rules (reviewers reject anything that breaks these):**
no gradients on cards · no glassmorphism blur · no emoji in UI text · one accent colour per card ·
no ALL CAPS (except the `DEMO REPLAY — NOT LIVE CAPTURE` label) · no "AI-powered" wording ·
no lorem ipsum · 8 px spacing grid · no more than 2 font weights per card · no text below 12 px.

---

## 8. Copy (`desktop/renderer/src/shared/copy.ts`)

Keys → EN / Hinglish / हिन्दी. Satya speaks as "he". `{x}` = placeholder.
Saarika writes the file; **Saksham proofreads Hindi** (he did T14).

| Key | EN | Hinglish | हिन्दी |
|---|---|---|---|
| `consent.title` | Can I keep watch? | Kya main nazar rakhun? | क्या मैं नज़र रखूँ? |
| `consent.body` | I'll notice when a call starts and ask before I listen. I only look for payment tricks. Nothing is saved unless you say so. | Call shuru hote hi main pehle poochhunga, phir hi sununga. Main sirf payment wale dhokhe dhoondhta hoon. Aapke kahe bina kuch save nahi hota. | कॉल शुरू होने पर मैं पहले पूछूँगा, फिर ही सुनूँगा। मैं सिर्फ़ पेमेंट से जुड़े धोखे ढूँढता हूँ। आपकी इजाज़त के बिना कुछ भी सेव नहीं होता। |
| `consent.scope.notice` | Notice calls (no recording) | Call notice karna (recording nahi) | कॉल पहचानना (रिकॉर्डिंग नहीं) |
| `consent.scope.listen` | Listen to a call when you say yes | Aapki haan par call sunna | आपकी हाँ पर कॉल सुनना |
| `consent.scope.files` | Check files you give me | Aapki di hui files check karna | आपकी दी हुई फ़ाइलें जाँचना |
| `action.start_watching` | Start watching | Nazar rakhna shuru karo | नज़र रखना शुरू करें |
| `action.not_now` | Not now | Abhi nahi | अभी नहीं |
| `call.title` | Sounds like a call. | Lagta hai call chal rahi hai. | लगता है कॉल चल रही है। |
| `call.body` | Want me to listen for payment tricks? I won't record it. | Payment wale dhokhon ke liye sunun? Main record nahi karunga. | क्या मैं पेमेंट से जुड़े धोखों के लिए सुनूँ? मैं रिकॉर्ड नहीं करूँगा। |
| `action.listen_call` | Listen to this call | Yeh call suno | यह कॉल सुनें |
| `action.not_this_call` | Not this one | Is baar nahi | इस बार नहीं |
| `live.title` | Listening… | Sun raha hoon… | सुन रहा हूँ… |
| `coverage.degraded` | Audio is unclear — I won't judge the voice. | Awaaz saaf nahi — main awaaz par faisla nahi karunga. | आवाज़ साफ़ नहीं है — मैं आवाज़ पर फ़ैसला नहीं करूँगा। |
| `seal.not_verified` | Voice not verified by Seal | Awaaz Seal se verified nahi | आवाज़ सील से सत्यापित नहीं |
| `ask.A1` | New account | Naya account | नया खाता |
| `ask.A2` | OTP / PIN | OTP / PIN | ओटीपी / पिन |
| `ask.A3` | Screen sharing | Screen share | स्क्रीन शेयर |
| `ask.A4` | Keep it secret | Kisi ko mat batao | किसी को मत बताओ |
| `ask.A5` | Skip approval | Approval chhod do | मंज़ूरी छोड़ दो |
| `ask.A6` | Gift card / crypto / UPI collect | Gift card / crypto / UPI collect | गिफ़्ट कार्ड / क्रिप्टो / यूपीआई कलेक्ट |
| `ask.A7` | Change bank details | Bank details badlo | बैंक विवरण बदलो |
| `alert.title` | Pause before you pay. | Paise bhejne se pehle ek second ruko. | पैसे भेजने से पहले एक पल रुकिए। |
| `alert.body` | This call asked for: {chips}. That doesn't prove who is speaking — let's check with {approver} on their own phone. | Is call mein maanga gaya: {chips}. Isse yeh pakka nahi hota ki bol kaun raha hai — chalo {approver} se unke apne phone par confirm karte hain. | इस कॉल में माँगा गया: {chips}। इससे यह पक्का नहीं होता कि बोल कौन रहा है — चलिए {approver} से उनके अपने फ़ोन पर पुष्टि करते हैं। |
| `action.verify` | Verify with {approver} | {approver} se verify karo | {approver} से पुष्टि करें |
| `action.copy_reply` | Copy a safe reply | Safe jawab copy karo | सुरक्षित जवाब कॉपी करें |
| `safe_reply` | I'll verify this through our registered process and call you back. | Hum ise registered process se verify karke aapko wapas call karenge. | हम इसे अपनी रजिस्टर्ड प्रक्रिया से सत्यापित करके आपको वापस कॉल करेंगे। |
| `action.open_notebook` | Open Notebook | Notebook kholo | नोटबुक खोलें |
| `oob.wait` | Asked {approver} on their own phone. Waiting… | {approver} se unke phone par poochha hai. Intezaar… | {approver} से उनके फ़ोन पर पूछा है। इंतज़ार… |
| `oob.approved` | {approver} confirmed this exact payment. You can continue. | {approver} ne isi payment ko confirm kiya. Aap aage badh sakte hain. | {approver} ने इसी पेमेंट की पुष्टि की। आप आगे बढ़ सकते हैं। |
| `oob.not_requested` | {approver} says they didn't ask for this. I've put the payment on hold. | {approver} ne kaha unhone yeh nahi maanga. Maine payment hold par daal di hai. | {approver} ने कहा कि उन्होंने यह नहीं माँगा। मैंने पेमेंट होल्ड पर डाल दिया है। |
| `oob.expired` | No answer from {approver} — that is not a yes. Keep it on hold. | {approver} ka jawab nahi aaya — iska matlab haan nahi. Hold par rakho. | {approver} का जवाब नहीं आया — इसका मतलब हाँ नहीं है। होल्ड पर रखें। |
| `file.title` | Should I read this? | Kya main ise padhun? | क्या मैं इसे पढ़ूँ? |
| `file.body` | I'll check "{name}" and keep its fingerprint in your Notebook. | Main "{name}" check karke uska fingerprint aapki Notebook mein rakhunga. | मैं "{name}" जाँचकर उसका फ़िंगरप्रिंट आपकी नोटबुक में रखूँगा। |
| `action.check_it` | Check it | Check karo | जाँचें |
| `action.no_thanks` | No thanks | Rehne do | रहने दें |
| `result.PASS` | Looks OK. | Theek lag raha hai. | ठीक लग रहा है। |
| `result.VERIFY` | Verify first. | Pehle verify karo. | पहले पुष्टि करें। |
| `result.HOLD` | Hold this payment. | Yeh payment roko. | यह पेमेंट रोकें। |
| `scribe.ask` | Money already left? I can prepare your report pack now. Every minute counts. | Paise chale gaye? Main abhi report pack bana deta hoon. Har minute keemti hai. | पैसे जा चुके हैं? मैं अभी रिपोर्ट पैक तैयार कर देता हूँ। हर मिनट क़ीमती है। |
| `action.prepare` | Prepare it | Bana do | तैयार करें |
| `scribe.writing` | Writing your report pack… | Report pack likh raha hoon… | रिपोर्ट पैक लिख रहा हूँ… |
| `scribe.done` | Done. 5 drafts ready — you review and submit. | Ho gaya. 5 drafts taiyaar — aap check karke submit karein. | हो गया। 5 ड्राफ़्ट तैयार — आप जाँचकर सबमिट करें। |
| `toast.sleep` | Sleeping. I'm not listening. | So raha hoon. Kuch nahi sun raha. | सो रहा हूँ। कुछ नहीं सुन रहा। |
| `toast.stopped` | I stopped listening: {reason}. | Maine sunna band kiya: {reason}. | मैंने सुनना बंद किया: {reason}। |
| `toast.off` | Bye! Bring me back from the menu bar. | Bye! Menu bar se wapas bula lena. | अलविदा! मेन्यू बार से वापस बुला लें। |
| `toast.no_backend` | I can't reach my brain, so I went to sleep. | Mera dimaag (backend) nahi mil raha, isliye so gaya. | मेरा दिमाग़ (बैकएंड) नहीं मिल रहा, इसलिए सो गया। |
| `menu.watch` / `menu.sleep` / `menu.check` / `menu.notebook` / `menu.off` | Watch / Sleep / Check something / Notebook / Turn off | Nazar rakho / So jao / Kuch check karo / Notebook / Band karo | नज़र रखें / सो जाएँ / कुछ जाँचें / नोटबुक / बंद करें |

---

## 9. Visual QA checklist (screenshot each, attach to your PR / commit message)

Open `?view=gallery` (all poses side by side) and `?view=bubble&card=<kind>` for each card.

- [ ] All 10 poses render at S, M, L on a **white** and on a **black** wallpaper; outline visible on both.
- [ ] Blink, breathe, look-at, ear twitch visible in `idle`; nothing moves in reduced-motion mode.
- [ ] `listen` rings react to a fake level slider (0 → 1).
- [ ] `alert` hops once, then stays still. No shaking.
- [ ] Radial menu opens in < 250 ms; arcs inward at the screen edges.
- [ ] Every bubble card kind renders in EN, Hinglish and हिन्दी without overflow at 340 px.
- [ ] Light and dark OS theme both look right.
- [ ] Idle CPU of the mascot window < 3 % (Activity Monitor).
