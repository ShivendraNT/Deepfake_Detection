# Saksham — your task file

> **For the AI agent reading this:** you are helping **Saksham**. Follow this file exactly. Explain one step at a time in simple language, tell Saksham which model to use for each step (section 2), and always say the exact command or prompt to use. Check `docs/STATUS.md` to see what is already done, then continue from the first unfinished item in section 4.

## 0. How to use this file
1. Open Antigravity in the `Deepfake_Detection` folder, new chat, model **Gemini Pro**, mode **Planning**.
2. Type: **`I am Saksham. What should I do now?`**
3. The agent reads this file + `docs/STATUS.md` and tells you your next step, which model to use, and the exact prompt. Do what it says, one step at a time.

## 1. Your role
You own the **Payment Verification Desk** — the web console the finance team actually uses — and the safety workflows behind it:

- the **evidence vault** (every file hashed and logged before anyone reads it),
- the console UI (case list, case view, role switcher),
- **OOB-Confirm** — the one-tap "Did you ask for this payment?" sent to the real CFO,
- callbacks, checker approvals and the watchlist,
- the plain-language **explanations** in English and Hindi,
- and, if time allows, the public **Scam Check** page.

You are the person who makes Satyapan look and feel like a real product.

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
git config user.name "Saksham"
git config user.email "<your email>"
```

**3.3 Antigravity (main tool)**
1. Download from https://antigravity.google/download and install. Sign in with your **personal** Google account.
2. `File → Open Folder…` → choose `Desktop/Deepfake_Detection`.
3. Open the **Agent** panel (right side). At the bottom of the chat box there are two dropdowns:
   - **Mode:** choose **Planning** (the agent makes a plan + task list you can review first). Use **Fast** only for tiny fixes.
   - **Model:** this is where you switch between **Gemini Pro** (worker) and **Claude Opus** (authority).
4. Settings → Agent → **Terminal command execution: "Request review"** (or "Ask"). You approve every command. Never set it to "Always proceed/Turbo".
5. Antigravity automatically reads `AGENTS.md` in this folder. Test it: open a new chat with Gemini Pro and type `hi`. It should ask **"Who am I working with?"**. Answer `Saksham`. ✅ Setup works.

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

| # | Task | What you build | Time | Can start | Needs from |
|---|---|---|---|---|---|
| 1 | **T09** | Evidence vault: storage, intake, anchor | ~4 h | now | — |
| 2 | **T06** | Console UI (React) | ~1 day | now | — |
| 3 | **T12** | OOB-Confirm (backend + CFO inbox screen) | ~5 h | backend now; screen after T06 | your T06 |
| 4 | **T13** | Callbacks, checker flows, watchlist | ~6 h | backend now; screen after T06 | your T06 |
| 5 | **T14** | Explanation templates EN + HI | ~3 h | now | — |
| 6 | **T24** | Citizen Scam Check page (stretch) | ~4 h | only if the main demo works by end of Day 3 | Saarika's T05 |

Spec files: `docs/tasks/T09-…`, `T06-…`, `T12-…`, `T13-…`, `T14-…`, `T24-…`. The spec is always the final word on details.

> **Only the tasks in this table are yours** (T09, T06, T12, T13, T14, T24). Never start, edit or open a PR for anyone else's task — not even to help. Not yours: Saarika's: T05, T10, T18, T23; Kartikey's: T03, T04, T08, T16, T17, T19; Shivendra's: T07, T11, T15, T20, T21. If an agent suggests one of these, stop and ask Shivendra.

### 4b. Hand-offs (who needs what from whom)
- **You → Kartikey:** your T09 (vault) and T13 (statuses) are used in his T16 report pack. Merge them early; 10-min sync with him on Day 3.
- **You → Shivendra:** your T14 templates are the fallback text for his LLM summary (T15) — finish T14 by Day 3 morning.
- **You → whole team:** the console is the demo's main screen. Show a screenshot in the group when the case view works.
- **Saarika → you:** the ask extractor (T05) for T24 (stretch).

## 4c. Task details

### T09 — Evidence vault (storage, intake, anchor)
**In simple words:** when someone uploads an email/PDF/voice note, we first take its fingerprint (SHA-256 hash) **before** opening it, save it, and write a line in a tamper-evident log (the "custody chain" — already built). Then we "anchor" the latest log fingerprint outside our database, so nobody can quietly rewrite history.
**Files:** `src/satyapan/vault/storage.py` (`LocalStorage.put/get`, `get_storage`), `vault/intake.py` (`intake`), `vault/anchor.py` (`anchor_head`), `src/satyapan/adapters/s3_store.py` (`S3Storage` — the only file allowed to import `boto3`).
**Never touch:** `vault/hashing.py`, `vault/custody.py` (already done), contracts, tests, API routes.
**Key ideas:** hash **before** parsing. Reject sneaky file keys like `../../etc/passwd`. If S3 fails, fall back to local storage. Never overwrite an anchor. If you try real S3: Object Lock in **GOVERNANCE** mode, never COMPLIANCE (you can't delete it for years). Keys come from `.env` — never paste them into an AI.
**Test:** `make task T=T09`. ⏱ ~4 h.

---

### T06 — Console UI
**In simple words:** the website the finance team uses. A list of cases; click one → the **transaction card first** (who, how much, which account — masked like `••••1234`), then the band badge (PASS / VERIFY / HOLD with an icon + word, not just colour), the reasons in plain words, what must be done to clear it, and the evidence list. A role switcher (maker / checker / CFO / security).
**Files:** `console/src/App.tsx` (remove `STUB(T06)`), new components in `console/src/components/`: `CaseList`, `CaseView`, `BandBadge`, `TransactionCard`, `ReasonCodes`, `EvidenceList`, `RoleSwitcher`. You may add tests in `console/src/__tests__/`.
**Never touch:** `console/src/types.ts`, `console/src/api.ts` (they mirror the backend — ask Shivendra if something is missing), anything in `src/` or `extension/`.
**Run it (two Terminal tabs):**
```bash
make run                          # tab 1: backend API at http://127.0.0.1:8000/docs
cd console && npm install && npm run dev   # tab 2: console at the URL it prints (usually http://localhost:5173)
```
**Key ideas:** call the API through `/api` (Vite proxy) — never hard-code `http://127.0.0.1:8000`. The **maker** role never sees scores. Clean and readable beats fancy.
**Test:** `make console-test` and `make task T=T06` (all 12 fixture cases must render). ⏱ ~1 day.

---

### T12 — OOB-Confirm
**In simple words:** if a "CFO" on a call asks for an urgent payment, the maker taps one button. The **real** CFO gets a message in their own login: "Did you ask for ₹X to account ••••1234? Yes / No". "No" → the case goes to HOLD as suspected fraud. This defeats a perfect deepfake, because the faker can't log in as the real CFO.
**Files:** `src/satyapan/workflows/oob.py` (`OOBService.create/respond`), `src/satyapan/adapters/ses_mailer.py` (`SesMailer`), `console/src/components/OobInbox.tsx` (CFO screen with Yes/No).
**Key ideas:** single-use token, expires in 10 minutes, bound to case + amount + beneficiary. Store only the token's **hash**, never the raw token, never log it. Use `secrets`, not `random`. Only the logged-in requester can answer. "Yes" does **not** clear a HOLD — only the checker can.
**Test:** `make task T=T12`. ⏱ ~5 h.

---

### T13 — Callbacks, checker flows, watchlist
**In simple words:** the rules for clearing a case. A callback counts only if it was made to the number **from our own vendor master / employee directory** — never a number from the message. Only the right role can clear or change status. Urgent override needs two different approvers. Flagged senders go on a 30-day watchlist.
**Files:** `src/satyapan/workflows/callbacks.py`, `status.py`, `watchlist.py`, `console/src/components/VerifyPanel.tsx`.
**Never touch:** `policy/permissions.py`, `policy/clearance.py` (use them), contracts, tests.
**Key ideas:** clearing changes the case **status**, never the **band**. Nobody except a human checker sets CONFIRMED_FRAUD. The same person can't approve an override twice.
**Test:** `make task T=T13`. ⏱ ~6 h.

---

### T14 — Explanation templates (English + Hindi)
**In simple words:** for every reason code (e.g. "new bank account not in vendor master"), write one short, plain sentence in English and in Hindi (Devanagari) telling the maker what is wrong and **what to do** ("Call the vendor on the number on file before paying").
**Files:** `src/satyapan/explain/templates.py` (`REASON_TEXT` for all codes, `reason_text`, `explain_template`).
**Key ideas:** ≤ 300 characters each. **Never reassuring words**: no "safe / legitimate / verified / genuine" (or सुरक्षित / वैध / सत्यापित / असली / प्रामाणिक) — a test checks this. Always "number on file", never "the number in the message". Simple everyday Hindi — check every machine translation yourself.
**Test:** `make task T=T14`. ⏱ ~3 h.

---

### T24 — Citizen Scam Check (stretch — only if the main demo works by end of Day 3)
**In simple words:** a simple mobile web page in Hindi/English: paste a suspicious message → see only the band and what to do, a tap-to-call 1930 button, NCRP and Chakshu links, and "share with a family member on WhatsApp". No scores, no technical details.
**Files:** `src/satyapan/citizen/rules.py` (`IMPOSSIBLE_CLAIMS`, `scam_check`), `console/public/scam-check.html`.
**Key ideas:** never say "safe"; never claim it protects live phone calls; never show scores (attackers could use them to tune their scams).
**Test:** `make task T=T24`. ⏱ ~4 h.

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
I am Saksham. Read AGENTS.md, team/Saksham.md (my section for TNN), docs/tasks/TNN-*.md and
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
I am Saksham. I'm continuing task TNN on branch tNN-…. Read AGENTS.md, team/Saksham.md,
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
| 0 (today) | Setup (section 3) | Read `README.md`, `docs/ARCHITECTURE.md` sections 1–3, `docs/tasks/T09` | `npm install` in `console/` |
| 1 | T09 | T06 start (case list + transaction card) | screenshot to the group |
| 2 | T06 finish | T12 (backend → inbox screen) | T12 PR |
| 3 | T14 (Shivendra needs it) | T13 (+10-min sync with Kartikey) | demo dry run with the team |
| 4 | T24 if the demo works, else polish console | dry runs | — |

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
| Not sure what to do next | Ask the agent: "I am Saksham. What's my next step?" — it reads this file + `docs/STATUS.md`. |
