# Satya Pocket — the phone app

> The same Satya, on a phone, on the same hotspot as the laptop.
> It is a **client**, not a second brain: the band still comes only from `satyapan.policy` on the
> laptop.

---

## 1. Open it

On the laptop:

```bash
make live
ipconfig getifaddr en0          # macOS; ipconfig / ip addr on Windows/Linux
```

On the phone, same Wi-Fi/hotspot:

```text
http://<laptop-ip>:8000/pocket
```

Or **Notebook → Now → On your phone → Satya Pocket** and scan the QR.

### Put it on the home screen

| Phone | Steps |
|---|---|
| iPhone | Safari → Share → **Add to Home Screen** |
| Android | Chrome → menu → **Add to Home screen** |

It opens without browser chrome, with the Satya icon. The shell still loads from the laptop, so
keep the laptop awake and on the same hotspot.

---

## 2. The four tabs

| Tab | What it does | Where the work happens |
|---|---|---|
| **Check** | Paste a message, take a photo, or pick a screenshot / voice note / PDF / video. Shows PASS / VERIFY / HOLD, why, what was checked, what could not be checked, and the safe next step. | Laptop engine (`/api/scam-check`, `/api/scam-check/file`) |
| **Live** | The call alert: chips, exact quotes, the policy band, **Verify with Rajesh**, **Stop listening**, cases. | Laptop engine + `/companion/events` |
| **Report** | UTR + amount → 1930 call script, bank recall message, NCRP fields, steps. | Laptop engine (`/api/scam-check/money-sent`) |
| **Help** | Honest limits, 1930 / cybercrime.gov.in / Chakshu links, install steps. | Static |

Every result is coarse on purpose: **band + why + next step**, never a raw score.

---

## 3. Two-minute demo

1. Laptop: `make live`. Open the QR card in **Notebook → Now**.
2. Judge scans **Satya Pocket** and adds it to the home screen (optional).
3. Tap **Digital arrest** sample → **HOLD**, with the exact reasons and the 1930 link.
4. Tap **Genuine OTP** sample → **PASS**, showing that a bank's own OTP SMS is not treated as a scam.
5. Tap **Take a photo** and photograph a fake invoice / message on the table → the same check runs
   on the laptop engine.
6. Open **Live** while the laptop is on the CFO call → chips and the band appear; tap
   **Verify with Rajesh** → the approver's `/oob` page gets the exact question.
7. Open **Report**, type a fake UTR (`FAKEUTR998877`) and an amount → the 1930 script, bank
   message and NCRP fields are drafted. Say: *“Drafts only. A human calls 1930 and presses Submit.”*

Fallback if the phone cannot reach the laptop: use `http://127.0.0.1:8000/pocket` in a browser on
laptop A. The app shows “engine offline” rather than inventing an answer.

---

## 4. What is a phone app allowed to do?

| Claim | Truth |
|---|---|
| **It listens to my phone calls** | **No.** iOS and Android do not let an app capture call audio. The laptop companion captures system audio (the other side) after a per-call yes. The phone never opens the microphone. |
| **It runs the full detector stack on the phone** | It calls the same engine on the laptop over the hotspot. Text, voice, face, OCR and the policy stay in one place. |
| **It sets the band** | Never. `satyapan.policy` sets `Decision.band`; the phone only displays it. |
| **It files my complaint** | Never. Every draft is `MANUAL_ONLY`; there is no public 1930/NCRP API. |
| **It stores my messages** | No check writes to the vault. The page keeps nothing after you close it. |
| **It works without the laptop** | Not today: the app shell loads from the laptop and every check calls it. A fully on-device text model would be a second band authority; that needs parity tests and a policy decision. |

---

## 5. Failure modes

| What you see | What to do |
|---|---|
| “engine offline” | Check the laptop is running `make live`; check phone and laptop are on the same hotspot; re-scan the QR. |
| Phone cannot open the URL | The laptop IP changed (VPN/hotspot). Run `ipconfig getifaddr en0`; set `SATYAPAN_OOB_URL=http://<ip>:8000/oob` before launching the desktop app so the QR matches. |
| “Could not check here: voice model” | `make voice` on the laptop, or accept the abstention: it never says “safe” for a missing model. |
| Photo/voice takes long | It runs on the laptop; a 30 s voice note takes about that long. Text is instant. |
| Add to Home Screen missing | iOS Safari only (not Chrome); Android Chrome menu. The app still works in the browser. |

---

## 6. Safety invariants kept

- Only `src/satyapan/policy/` sets a band.
- Signals raise only; LLM/style are capped at VERIFY.
- No microphone, no phone-call capture, no audio upload off the laptop.
- OOB approver comes from the employee directory, never from the message.
- Every report is `MANUAL_ONLY`; no auto-submit.
- Makers never see raw scores.

---

## 7. Why not a native APK/IPA today?

A native wrapper (Capacitor/React Native) is a packaging job, not a brain transplant: it would
still call the laptop engine, because moving the Python engine (or reimplementing the policy)
would create a second band authority and break the safety contract. The PWA gives the same
experience now, with no store review and no signing. The one thing no phone app can add is
call-audio capture; that is an OS restriction.
