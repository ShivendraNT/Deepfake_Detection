# Saarika — your task file

> **For the AI agent reading this:** you are helping **Saarika**. Follow this file exactly. Explain one step at a time in simple language, tell Saarika which model to use for each step (section 2), and always say the exact command or prompt to use. Check `docs/STATUS.md` to see what is already done, then continue from the first unfinished item in section 4.

## 0. How to use this file
1. Open Antigravity in the `Deepfake_Detection` folder, new chat, model **Gemini Pro**, mode **Planning**.
2. Type: **`I am Saarika. What should I do now?`**
3. The agent reads this file + `docs/STATUS.md` and tells you your next step, which model to use, and the exact prompt. Do what it says, one step at a time.

## 1. Your role
You own the **language and live-call experience** of Satyapan:

- the **ask extractor** — spots *what* a scammer is asking for (OTP, new account, secrecy…). It powers the live-call alerts **and** it is detector "D4" in our research paper, so your code is literally what the paper measures;
- the **side panel** the finance person sees during a Meet/Teams call;
- the **voice-detector calibration** — the real thresholds and the honest accuracy numbers for our slides;
- the **pitch deck**, and you run the side panel during the live demo.

Your tasks sit on the critical path right next to Shivendra's live-call engine (T07 capture → T11 live transcript). Your output is his input and his is yours, so several steps are done **together** — they're marked 🤝 below. Plan your day around those checkpoints.

## 2. Your AI toolbox — which model, when

You have four tools. Use them in this order. **Do not switch randomly** — switching tools mid-step loses context.

| Role | Tool + model | Use it for | Do NOT use it for |
|---|---|---|---|
| 🧠 **Authority** (top boss) | **Antigravity → Claude Opus** (the newest "Claude Opus" in the model dropdown) | (1) approving your plan before you code, (2) final review before your PR, (3) unblocking you after 3 failed attempts | Writing code. Long chats. Anything Gemini can do. Its quota is small — save it. |
| 🔨 **Worker** (daily driver) | **Antigravity → Gemini Pro** (the newest "Gemini … Pro" in the dropdown) | Implementing your task step by step, running tests, fixing failures | Changing files your spec says "Do not touch" |
| 🔁 **Backup worker** | **opencode** with a free OpenCode Zen model (`/models` → pick one marked free, e.g. `big-pickle`) | When Antigravity says you are out of quota / rate-limited | — |
| ✍️ **Autocomplete + 2nd backup** | **GitHub Copilot** (Student plan) in VS Code — inline suggestions always; Copilot Chat "Agent" mode if opencode is also rate-limited | Small edits, finishing a line, explaining an error | Big multi-file changes |
| 🆘 Last resort | **Gemini CLI** (`gemini` in Terminal) | When everything above is rate-limited | — |

**The Authority rule (very important):**
- Claude Opus is used **max 3 times per task**: ① plan approval, ② final review, ③ one "I'm stuck" call.
- If Opus and Gemini disagree, **Opus wins**. If Opus and the spec disagree, **the spec wins** (and tell Shivendra).
- If Opus is out of quota, use the `reviewer` agent in opencode for ② and message Shivendra for ①/③.

**Model names change often.** If you don't see the exact name, pick the newest Gemini *Pro* (worker) and the newest Claude *Opus* (authority). Never use a "Flash"/"Lite" model for the plan or the final review.

**Rate-limit ladder:** Antigravity Gemini → opencode free model → Copilot Agent → Gemini CLI. The rules in `AGENTS.md` apply in every tool, so nothing breaks when you switch. When you switch, start the new tool with the "Resume" prompt in section 5.

## 3. One-time setup (do this once, ~45 minutes)

Do these in order. Tick each box. If a step fails, copy the exact error into Antigravity (Gemini) and ask "how do I fix this on my computer?".

**3.1 Install the basics** (macOS — open the **Terminal** app; on Windows see the note at the end of this section)
- [ ] Git + make: `xcode-select --install` (click Install in the popup)
- [ ] uv (Python manager): `curl -LsSf https://astral.sh/uv/install.sh | sh` → then close and reopen Terminal
- [ ] Node.js 20 or newer: download the LTS installer from https://nodejs.org → check with `node -v`
- [ ] Google Chrome (needed for the extension work)

**3.2 Get the code**
```bash
cd ~/Desktop
git clone https://github.com/ShivendraNT/Deepfake_Detection.git
cd Deepfake_Detection
make sync          # installs Python packages (takes a few minutes the first time)
make check         # must end with "make check: ALL GREEN"
```
If `make check` is not green on a fresh clone, stop and message Shivendra — don't fix it yourself.

Set your git name once (so commits show who did what):
```bash
git config user.name "Saarika"
git config user.email "<your email>"
```

**3.3 Antigravity (main tool)**
1. Download from https://antigravity.google/download and install. Sign in with your **personal** Google account.
2. `File → Open Folder…` → choose `Desktop/Deepfake_Detection`.
3. Open the **Agent** panel (right side). At the bottom of the chat box there are two dropdowns:
   - **Mode:** choose **Planning** (the agent makes a plan + task list you can review first). Use **Fast** only for tiny fixes.
   - **Model:** this is where you switch between **Gemini Pro** (worker) and **Claude Opus** (authority).
4. Settings → Agent → **Terminal command execution: "Request review"** (or "Ask"). You approve every command. Never set it to "Always proceed/Turbo".
5. Antigravity automatically reads `AGENTS.md` in this folder. Test it: open a new chat with Gemini Pro and type `hi`. It should ask **"Who am I working with?"**. Answer `Saarika`. ✅ Setup works.

**3.4 opencode (backup)**
```bash
npm install -g opencode-ai
cd ~/Desktop/Deepfake_Detection
opencode
```
Inside opencode: type `/connect` → choose **OpenCode Zen** → log in → type `/models` → pick a model marked *free*. Press **Tab** to switch between agents (`implementer` builds, `planner` plans). Our custom commands: `/task T05`, `/check`, `/review`, `/stuck`, `/plan`.

**3.5 GitHub Copilot (autocomplete)**
1. Get the free Student plan: https://education.github.com/pack (verify with your college ID / email).
2. Install **VS Code** → Extensions → install **GitHub Copilot** + **GitHub Copilot Chat** → sign in with GitHub.
3. Copilot reads `.github/copilot-instructions.md` from this repo automatically.

**3.6 Gemini CLI (last resort)**
```bash
npm install -g @google/gemini-cli
cd ~/Desktop/Deepfake_Detection && gemini      # log in with Google when asked
```

> **Windows?** Install **WSL** (open PowerShell as admin → `wsl --install` → restart), open the **Ubuntu** app, and do every command above inside Ubuntu (use `sudo apt install make git` instead of `xcode-select`). In Antigravity, open the folder through the WSL remote option, or keep the repo inside `\\wsl$`.

## 4. Your tasks (in this order)

| # | Task | What you build | Time | Can start | 🤝 With Shivendra |
|---|---|---|---|---|---|
| 1 | **T05** | Ask extractor A1–A7 (EN / Hinglish / Hindi) | ~1 day | now | kickoff, review, freeze |
| 2 | **T10** | Extension side panel (what the user sees mid-call) | ~1 day | now (built from a replay file) | first live Meet test with his T07 |
| 3 | **T18** | Voice-detector channel evaluation + thresholds | ~1 day | after T07 works | recording session + threshold fit |
| 4 | **T23** | Pitch deck (5 slides) + backup recording | ~½ day | after T18, T21, T22 | build + rehearse together |
| ★ | **T22** | Demo dry runs — you operate the side panel + console | Day 3–4 | after T10 | every dry run |

Spec files: `docs/tasks/T05-ask-extractor.md`, `T10-extension-sidepanel.md`, `T18-audio-channel-eval.md`, `T23-pitch-deck.md`, `T22-demo-assets-dry-runs.md`. The spec is always the final word on details.

### 4b. 🤝 Pair checkpoints with Shivendra (put these in your calendar)

| # | When | What happens | Bring | Time |
|---|---|---|---|---|
| P1 | Day 1, start | **T05 kickoff** — agree on A1–A7 examples and the "must NOT fire" sentences | 10 of your own sentences | 15 min |
| P2 | Day 1, evening | **T05 review** — he checks precision/recall and the tricky patterns | `make task T=T05` output | 20 min |
| P3 | Day 2, morning | **T05 freeze** — after his OK you create the tag `lexicon-v1.0`; from now on the lexicon never changes (the paper depends on it) | green PR | 10 min |
| P4 | Day 2, evening | **First live call** — his capture (T07) + your side panel (T10) on a real Meet tab. One of you is the "caller" | Chrome with the extension loaded | 30 min |
| P5 | Day 3 | **Recording session (T18)** — everyone signs consent, ~200 five-second clips through real Meet capture, then you two fit the thresholds | consent forms, quiet room | 1–1.5 h |
| P6 | Day 3 | **Live ask chips** — his T11 sends your T05 asks to your T10 panel; you measure "ask spoken → chip shown" time (target ≤ 13 s) | stopwatch, STATUS notes | 20 min |
| P7 | Day 4 | **Deck + demo rehearsal** — you build the slides, he adds research numbers; you present the demo part | `results/` files | 2 h |

If Shivendra is busy at a checkpoint, continue with the next non-🤝 step and come back.

## 4c. Task details

### T05 — Ask extractor (A1–A7)

**In simple words:** a scammer can fake a voice or write perfect English, but to steal money they still have to **ask** for something. We detect the ask, not the style. Seven ask types:

| Code | The ask | Example (Hinglish) |
|---|---|---|
| A1 | send money to a new / "safe" account | "naye account mein transfer kar do" |
| A2 | share OTP / PIN / password / CVV | "OTP batao jaldi" |
| A3 | install a remote-access / screen-share app | "AnyDesk download karo" |
| A4 | keep it secret / don't tell anyone | "Arjun ko mat batana" |
| A5 | skip the normal process | "approval ka wait mat karo, abhi bhejo" |
| A6 | pay by gift card / crypto / UPI collect | "Amazon gift card le aao" |
| A7 | change of payee or bank details | "humara bank account change ho gaya hai" |

You write rules (regular expressions + word lists) that find these in English, Hinglish (Roman letters) and Hindi (Devanagari).

**Why it matters:** Shivendra's live-call engine (T11) runs your extractor on every transcript chunk, and the research paper measures it as detector D4. That's why it is **frozen** after review.

**Files you change:** `src/satyapan/asks/lexicon.py`, `src/satyapan/asks/extractor.py`, `tests/tasks/data/t05_ask_sentences.jsonl` (you are allowed to extend this one), `research/LEXICON_LOG.md` (new).
**Never touch:** contracts, policy, any other test. **Never open ICFD *test* rows** (that would break the research).

**How, step by step**
1. 🤝 **P1 kickoff** with Shivendra (15 min).
2. **Write the test sentences yourself first** (not with AI — AI-written sentences make the test meaningless). Target: ≥ 80 lines, every ask type in both `en` and `hi-Latn`, ≥ 10 in Devanagari (`hi-Deva`), plus ~25 normal sentences with `"asks": []` (e.g. "please check last month's account statement"). Format, one per line:
   `{"text": "OTP batao jaldi", "asks": ["A2"], "lang": "hi-Latn"}`
   Speak like a real caller would. Mix asks in one sentence sometimes (`["A2","A4"]`).
3. Plan with 🧠 **Opus** (section 5, step 2).
4. Build with 🔨 **Gemini Pro**. Good build prompt:
   ```
   Implement normalise() and extract_asks() in src/satyapan/asks/extractor.py per docs/tasks/T05.
   Then extend LEXICON in lexicon.py: at least 8 patterns per ask type across en, hi-Latn, hi-Deva.
   No single-word patterns like "pin" or "account". Use re.IGNORECASE. For Devanagari do not use \b;
   use (?<!\S) and (?!\S) or plain substrings. Run `make task T=T05` after each ask type.
   ```
5. `make task T=T05` prints **precision** and **recall**. Target precision ≥ 0.90, recall ≥ 0.85. If precision is low, a pattern is too broad: ask Gemini "which sentences are false positives and which pattern caused each?". If recall is low, add patterns for the missed phrasing (not for the exact sentence — think of the general way people say it).
6. Log in `research/LEXICON_LOG.md` every ICFD *train* row you looked at for ideas (row id only, never the text).
7. Copy precision/recall into `docs/STATUS.md` notes. 🤝 **P2 review**.
8. 🤝 **P3 freeze**: after Shivendra approves and merges: `git tag lexicon-v1.0 && git push origin lexicon-v1.0`. No lexicon edits after this.

**Done when:** `make task T=T05` green with the targets, `make check` green, PR merged, tag pushed.
**Common mistakes:** patterns that fire on normal talk; copying patterns into test sentences; forgetting Devanagari; editing after the freeze.

---

### T10 — Extension side panel

**In simple words:** during a Meet/Teams call, a panel opens on the right side of Chrome. It shows: a voice meter (words, not numbers), live transcript lines, ask chips ("OTP request", "Keep it secret"), a suggested thing to say, and buttons "Confirm with…" and "Link to payment". It also clearly shows "Protection on".

**Why it matters:** this is the first thing judges see in the demo. Big, calm, readable — the user is mid-call.

**Files:** `extension/lib/panel_state.js` (pure reducer: `initialState`, `applyEvent`, `ASK_LABELS`), `extension/sidepanel.html` (remove `STUB(T10)`, add the required ids), `extension/sidepanel.js` (render + `?replay=1` dev mode), `extension/sidepanel.css`.
**Never touch:** `extension/tests/panel_state.test.mjs`, `extension/lib/voice_rules.js`, `extension/replay/sample_events.jsonl`, capture code (T07 — that's Shivendra's), backend.

**How**
1. You don't need a live call: the file `extension/replay/sample_events.jsonl` replays a fake call event by event.
2. Plan with 🧠 Opus, build with 🔨 Gemini. Start with the reducer (pure function, tested by `make ext-test`), then HTML, then JS rendering, then CSS.
3. Reducer rule: **never change the old state** — always return a new object (`{...state, asks: [...state.asks, x]}`), never `state.asks.push(x)`.
4. Show **words, never scores** ("Likely synthetic voice (2 windows)", not "0.97"). Don't rely on colour alone — add an icon/label.
5. See it in Chrome: `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → choose the `extension/` folder → open the side panel page with `?replay=1` at the end of its URL. Take a screenshot for the PR.
6. Tests: `make ext-test` and `make task T=T10`.
7. 🤝 **P4 first live call** once Shivendra's T07 capture works: real Meet tab, he plays a clip, you watch the panel. Note anything confusing and fix it.

**Done when:** `make ext-test` + `make task T=T10` green, screenshot in the PR, P4 done and noted in STATUS.

---

### T18 — Voice-detector channel evaluation + thresholds

**In simple words:** our voice-deepfake detector is less accurate on phone/WhatsApp-quality audio. You measure **how much** (EER — equal error rate — on clean / Opus 16 kbps / AMR-NB 8 kHz / G.711 audio, with confidence intervals) and set the two alert thresholds (τ_hi at 1% false alarms, τ_lo at 5%) on audio that really went through Meet.

**Why it matters:** it gives the honest voice number on our evidence slide, and the extension (T07) and voice uploads (T17) use your thresholds.

**Files:** `research/audio/channel_eval.py` (`reencode`, `speaker_disjoint_split`, `eer`, `fit_thresholds`, `bootstrap_eer_by_speaker`), `research/audio/run_audio_eval.py` (new CLI), `results/audio_eval.csv` (new), `config/voice_thresholds.json` (real values, `calibrated: true`).
**Never:** commit audio (team voices are personal data), touch `voice/rules.py`, contracts, tests.

**How**
1. Pure functions first (`eer`, `fit_thresholds`, `speaker_disjoint_split`, bootstrap) — 🔨 Gemini, `make task T=T18` after each.
2. Install ffmpeg: `brew install ffmpeg`. Check AMR support: `ffmpeg -codecs | grep amr`. If AMR-NB encoding is missing, note it in STATUS and tell Shivendra (needs a different ffmpeg build).
3. Datasets (In-the-Wild + HAV-DF subsets) go into `research/_data/` only — it's git-ignored. Shivendra shares the download links.
4. 🤝 **P5 recording session**: everyone signs `docs/consent/VOICE_CLONE_CONSENT_TEMPLATE.md` first (paper copies, not in git). ~200 five-second clips recorded through a **real Meet tab** with the extension's dev mode. Keep calibration speakers and test speakers **different** (no person in both).
5. You run the evaluation and write the CSV (columns are in the spec). Shivendra and you fit τ on the calibration speakers only and update `config/voice_thresholds.json`.

**Done when:** CSV with 4 channels + CIs committed, thresholds `calibrated: true`, tests green.
**Common mistakes:** same speaker in calibration and test; fitting on test data; EER without `n` and CI.

---

### T23 — Pitch deck + backup recording

**In simple words:** 5 slides — problem → our insight → live demo → evidence (with n and confidence intervals) → India + AWS + roadmap — plus a screen recording of one perfect demo run in case the live one fails.

**Files:** `docs/pitch/DECK_OUTLINE.md` (fill all 5, remove `STUB(T23)`), `docs/pitch/deck.pdf` (export from Google Slides/Canva), `docs/pitch/backup_recording.md` (link + date + what it shows).

**How**
1. Read `docs/DEMO_SCRIPT.md` and `docs/pitch/DECK_OUTLINE.md`.
2. Draft the outline with 🔨 Gemini: "Using only numbers from results/*.csv and results/*.json, fill DECK_OUTLINE.md. Every number must say n= or cite the paper."
3. Design the slides yourself (Google Slides/Canva). One idea per slide, big text.
4. 🤝 **P7**: Shivendra adds the research figure (`figures/money.png`) and checks every claim. You present the demo slide + run the side panel; he presents the research slide.
5. Record the backup video during a successful dry run.

**Rules:** no number that isn't in `results/`; never claim "no Indian competitors" (Vastav AI, Kroop AI, pi-labs, Google Scam Detection exist); never claim 1930/NCRP integration (there is no public API).

---

### ★ T22 — Demo dry runs (your role)
You operate the **side panel and console** during the demo. Every dry run gets one row in `results/dry_runs.csv`. Goal: 10 successful runs in a row. Learn the script in `docs/DEMO_SCRIPT.md` by heart.

## 5. The loop — exactly how to do every task

Same 9 steps for every task. Copy-paste the prompts (replace `TNN` with your task ID, e.g. `T05`).

**Step 1 — New branch, fresh chat**
```bash
cd ~/Desktop/Deepfake_Detection
git switch main && git pull
git switch -c tNN-short-name        # e.g. git switch -c t05-ask-extractor
```
Open a **new** Antigravity chat for every task (old chats drift). Edit `docs/STATUS.md`: set your task to `in-progress`.

**Step 2 — Plan (model: 🧠 Claude Opus, mode: Planning)**
```
I am Saarika. Read AGENTS.md, team/Saarika.md (my section for TNN), docs/tasks/TNN-*.md and
tests/tasks/test_tNN_*.py. Do NOT read any other files yet.
Write a plan of at most 8 small steps. For each step: which function you will write, which file,
and which test should turn green. List anything in the spec that is unclear. Do not write code.
```
Read the plan. If it touches a file under "Do not touch", reply "No — that file is off-limits, re-plan". Paste the approved plan into the spec's **Agent plan** section.

**Step 3 — Switch the model to 🔨 Gemini Pro.** Then:
```
Follow the approved plan in docs/tasks/TNN-*.md, one step at a time.
After each step run `make task T=TNN` and show me the result. Stop after each step and wait for me.
Never edit tests, contracts, policy, AGENTS.md or any file under "Do not touch".
```

**Step 4 — Red first.** The first `make task T=TNN` should FAIL (red). That's correct — it proves the tests are watching your task.

**Step 5 — Repeat** "continue with the next step" until `make task T=TNN` is all green. Approve terminal commands only if they are `make …`, `uv run …`, `npm …test`, `git status/diff/add/commit`. If the agent wants to run anything else (rm, curl, pip install, git push), click **Reject** and ask why.

**Step 6 — Whole project check**
```bash
make check        # must say ALL GREEN
make fmt          # if lint/format fails, this auto-fixes; then run make check again
```

**Step 7 — Final review (model: 🧠 Claude Opus)**
```
Review my changes for TNN (run `git diff main`). Check against docs/tasks/TNN-*.md:
acceptance criteria, "Do not touch" list, "Common mistakes" list, and AGENTS.md rules.
Reply with: PASS or a numbered list of problems. Do not edit files.
```
Fix every problem with Gemini, then re-run `make check`.

**Step 8 — Commit + push your branch**
```bash
git add -A
git status                     # make sure no audio/.env/data files are listed
git commit -m "TNN: <what you did in one line>"
git push -u origin tNN-short-name
```
Open a Pull Request on GitHub (use the template; fill every box). Update `docs/STATUS.md` → `done` + a one-line note (e.g. precision/recall numbers). **Never merge into `main` yourself** — Shivendra merges.

**Step 9 — Tell the team** in the group: "TNN done, PR #__, tests green, notes: …".

### Prompts for when things go wrong
**Test keeps failing (after 3 tries) — model: 🧠 Claude Opus**
```
I'm stuck on TNN. Here is the failing output of `make task T=TNN`: <paste>.
Here is what was tried: <list>. Read only the spec, the test file and the files I'm allowed to edit.
Explain the root cause in simple words and give the smallest fix. Do not edit tests.
```
If Opus can't fix it either: add `BLOCKED (date, model): what I tried, exact error, best guess` at the bottom of the spec, set STATUS to `blocked`, commit, and message Shivendra. **Then start your next task** — don't sit idle.

**Rate-limited / switching tools — "Resume" prompt**
```
I am Saarika. I'm continuing task TNN on branch tNN-…. Read AGENTS.md, team/Saarika.md,
docs/tasks/TNN-*.md (including the Agent plan section) and run `git diff main` to see what's done.
Then run `make task T=TNN` and continue with the next unfinished plan step.
```

**"Explain this to me"** (use Gemini — understanding your own code matters in the judges' Q&A)
```
Explain what <file/function> does in simple words, line by line, and why the test checks it.
```

## 6. Your day-by-day plan

| Day | Morning | Afternoon | Evening |
|---|---|---|---|
| 0 (today) | Setup (section 3) | Read `README.md`, `docs/ARCHITECTURE.md` sections 1–3, `docs/tasks/T05` | Write 30 test sentences |
| 1 | 🤝 P1 kickoff → finish sentences | T05 build (Gemini) | 🤝 P2 review |
| 2 | 🤝 P3 freeze → start T10 reducer | T10 HTML/JS/CSS | 🤝 P4 first live call |
| 3 | T18 pure functions + ffmpeg | 🤝 P5 recording + thresholds, 🤝 P6 ask chips | T18 CSV; first demo dry runs |
| 4 | T23 deck draft | 🤝 P7 deck + rehearsal | Dry runs to 10/10, backup recording |

## 7. Rules you never break

1. **Never edit or delete a test to make it pass.** Fix the code.
2. **Never touch** `src/satyapan/contracts/`, `src/satyapan/policy/`, `tests/`, `AGENTS.md`, `opencode.json` (unless your spec explicitly allows a file). If you think one is wrong, write it down and tell Shivendra.
3. **Never paste real data into any AI**: no real voices, phone numbers, bank accounts, Aadhaar/PAN, API keys, `.env`. Free models may train on what you send. Our demo data is fake on purpose (`*.example`, IFSC `FAK…`, accounts `9999…`).
4. **Never commit** audio files, ICFD dataset text, `.env`, or anything in `research/_data/`.
5. **Never `git push` to `main`, never `git push --force`, never `rm -rf`.**
6. **One task = one branch = one PR.** Small PRs get merged fast.
7. Stuck for more than 3 attempts or 45 minutes → use the stuck prompt → then tell Shivendra. Asking early is good, not weak.

## 8. Words you'll see
`band` = PASS / VERIFY / HOLD (how careful we must be) · `floor` = the minimum band set from trusted company data · `signal` = one piece of evidence that can only *raise* the band · `spec` = the task file in `docs/tasks/` · `fixture` = fake demo data used by tests · `PR` = pull request. More in `docs/GLOSSARY.md`.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `make: command not found` | macOS: `xcode-select --install`. Windows: work inside WSL Ubuntu. |
| `uv: command not found` | Re-run the uv install line, then close + reopen Terminal. |
| `make check` red on `main` before you changed anything | Not your fault. `git pull`, run again; still red → tell Shivendra. |
| Ruff/format errors | `make fmt`, then `make check` again. |
| Test says `NotImplementedError` | That's the part you still have to write. |
| Agent wants to edit a test or contract | Reject. Remind it: "AGENTS.md rule 11/12 — fix the code, not the test." |
| Agent reads the whole repo / goes in circles | Stop it. New chat. Use the Resume prompt. Give it only the spec + listed files. |
| Merge conflict | Don't guess. `git merge --abort` and message Shivendra. |
| Antigravity quota finished | Switch to opencode (section 2 ladder). Use the Resume prompt. |
| Not sure what to do next | Ask the agent: "I am Saarika. What's my next step?" — it reads this file + `docs/STATUS.md`. |
