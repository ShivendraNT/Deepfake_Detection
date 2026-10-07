# Kartikey — your task file

> **For the AI agent reading this:** you are helping **Kartikey**. Follow this file exactly. Explain one step at a time in simple language, tell Kartikey which model to use for each step (section 2), and always say the exact command or prompt to use. Check `docs/STATUS.md` to see what is already done, then continue from the first unfinished item in section 4.

## 0. How to use this file
1. Open Antigravity in the `Deepfake_Detection` folder, new chat, model **Gemini Pro**, mode **Planning**.
2. Type: **`I am Kartikey. What should I do now?`**
3. The agent reads this file + `docs/STATUS.md` and tells you your next step, which model to use, and the exact prompt. Do what it says, one step at a time.

## 1. Your role
You own the **evidence checkers** — the code that reads an email, an invoice PDF or a voice note and turns what it finds into *signals* — plus the **report pack** a company uses in the "golden hour" after fraud, and the **measurement code** of our research paper.

Your modules are mostly backend Python with very clear tests. Each one is independent, so you can always move to the next one if you're waiting on someone.

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
git config user.name "Kartikey"
git config user.email "<your email>"
```

**3.3 Antigravity (main tool)**
1. Download from https://antigravity.google/download and install. Sign in with your **personal** Google account.
2. `File → Open Folder…` → choose `Desktop/Deepfake_Detection`.
3. Open the **Agent** panel (right side). At the bottom of the chat box there are two dropdowns:
   - **Mode:** choose **Planning** (the agent makes a plan + task list you can review first). Use **Fast** only for tiny fixes.
   - **Model:** this is where you switch between **Gemini Pro** (worker) and **Claude Opus** (authority).
4. Settings → Agent → **Terminal command execution: "Request review"** (or "Ask"). You approve every command. Never set it to "Always proceed/Turbo".
5. Antigravity automatically reads `AGENTS.md` in this folder. Test it: open a new chat with Gemini Pro and type `hi`. It should ask **"Who am I working with?"**. Answer `Kartikey`. ✅ Setup works.

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
| 1 | **T03** | `.eml` email parser | ~3 h | now | — |
| 2 | **T04** | Look-alike domains + email signals | ~3 h | `domains.py` now; `signals.py` after T03 | your T03 |
| 3 | **T08** | Invoice / PDF checker | ~4 h | now | — |
| 4 | **T17** | Voice-note uploads (WhatsApp voice notes, recordings) | ~6 h | now (tests use fakes) | model files from Shivendra's T07 for the real run |
| 5 | **T16** | Report pack (1930 script, bank email, NCRP draft, evidence index) | ~5 h | now (on fixture `case_s12`) | Saksham's T09 + T13 for the final wiring |
| 6 | **T19** | Research metrics, dataset loader, TF-IDF baseline (D2) | ~1.5 days | metrics now; D4 part after T05 freeze | Saarika's T05 tag `lexicon-v1.0`; Shivendra runs D3 on Kaggle |

Spec files: `docs/tasks/T03-…`, `T04-…`, `T08-…`, `T17-…`, `T16-…`, `T19-…`. The spec is always the final word on details.

> **Only the tasks in this table are yours** (T03, T04, T08, T17, T16, T19). Never start, edit or open a PR for anyone else's task — not even to help. Not yours: Saarika's: T05, T10, T18, T23 — T05 is done, never touch `src/satyapan/asks/`; Saksham's: T06, T09, T12, T13, T14, T24; Shivendra's: T07, T11, T15, T20, T21. If an agent suggests one of these, stop and ask Shivendra.

### 4b. Hand-offs (who needs what from whom)
- **You → Saksham:** none blocking. **Saksham → you:** his T09 (vault) and T13 (statuses) are used by your T16. Write T16 against the fixture first; when his PRs merge, `git pull` and run `make task T=T16` again. Sync with him for 10 min on Day 3.
- **Saarika → you:** the tag `lexicon-v1.0` (end of Day 2). Until then do the metrics + loader parts of T19.
- **Shivendra → you:** model files for T17's real-audio check (he'll tell you where they are), and he reviews T19 and runs D3 on Kaggle.
- **You → Shivendra:** T19 metrics + loader + D2 by Day 4 morning — his research results (T21) depend on them.

## 4c. Task details

### T03 — `.eml` email parser
**In simple words:** an `.eml` file is a raw email. You turn it into a clean `ParsedEmail` object: who sent it (domains), what the **trusted** mail server said about it (SPF/DKIM/DMARC in the `Authentication-Results` header), the plain-text body with hidden text removed, and attachment info.
**Files:** `src/satyapan/email/parser.py` (`parse_eml`, `parse_auth_results`, `extract_attachments`). **Never touch:** contracts, tests, `data/demo/emails/`.
**Key ideas (tell the agent):**
- Attackers can add their own fake `Authentication-Results` header. Trust **only the topmost one with our server id** — use `msg.get_all(...)`, not `msg.get(...)`.
- Remove hidden text from the body (HTML comments, `display:none`) — that's where prompt-injection hides (fixture `09_prompt_injection.eml`).
- Missing `From` → raise `ValueError`. Missing Reply-To → `None` (not the string `"None"`).
- No network/DNS lookups.
**Test:** `make task T=T03` (10 fixture emails). ⏱ ~3 h.

---

### T04 — Domain checks + email signals
**In simple words:** catch tricks like `acme-supp1ies.example` pretending to be `acme-supplies.example`, a "bank" not on `.bank.in` (RBI rule for Indian banks), Gmail pretending to be a company, Reply-To going somewhere else.
**Files:** `src/satyapan/email/domains.py` (`levenshtein`, `normalise_domain`, `is_lookalike`, `claims_to_be_bank`, `is_bank_in`, `is_freemail`) — can start right away; `src/satyapan/email/signals.py` (`email_signals`) — after your T03.
**Key ideas:** look-alike = edit distance ≤ 2 **or** Unicode confusables, but an exact match is NOT a look-alike. The bank rule uses display name + domain, **not the subject** (vendors legitimately write "updated bank details"). Build every signal with `Signal.make(...)`. Ignore normal email-service bounce domains (e.g. `amazonses.com`).
**Test:** `make task T=T04` (25 table tests + 10 fixtures). ⏱ ~3 h.

---

### T08 — Invoice / PDF checker
**In simple words:** read the invoice PDF's text, pull out IFSC, account number, UPI ID, GSTIN, amount, invoice number (regex — patterns are given in the spec), read the PDF's edit history (was it edited after creation?), and compare with the company's vendor master. Different bank details than the vendor master = strong signal.
**Files:** `src/satyapan/document/extract.py`, `pdf.py`, `checker.py`.
**Key ideas:** "PDF was edited" alone is weak — show it as *inconclusive*, not fraud. Amounts are whole rupees as `int`. An email address is not a UPI ID; a phone number is not an account. Never put a full account number in a `detail` text (mask it). No OCR (out of scope).
**Test:** `make task T=T08` (6 fixture PDFs, 2 edited). ⏱ ~4 h.

---

### T17 — Voice-note uploads
**In simple words:** someone uploads a WhatsApp voice note "from the CFO". You convert it to 16 kHz mono, cut it into 5-second windows, score each window with the same voice model the extension uses, apply the **same window rule** (`classify_windows`), transcribe it, and run the ask extractor on the transcript.
**Files:** `src/satyapan/voice/audio_io.py`, `detector.py`, `upload.py`, `src/satyapan/adapters/transcribe_aws.py`.
**Key ideas:** never commit audio — tests generate tones. Any crash in the scorer becomes a **grey** "DETECTOR_ERROR" reason, never an exception and never a PASS. Under 3 seconds of speech → `SPEECH_TOO_SHORT`. Garbage bytes → `ValueError`. Network code only in `adapters/`.
**Test:** `make task T=T17`. Real-model check later with Shivendra's model files. ⏱ ~6 h.

---

### T16 — Report pack
**In simple words:** after a fraud, the first hour matters most. Banks can freeze money if they quickly get the **UTR** (transaction reference) and account details. You generate drafts a human sends: a 1930 call script (UTR on line 1), a bank fraud-desk email (subject starts "URGENT: fraud"), an NCRP complaint draft (copyable fields in the portal's order), a Chakshu note, an evidence index (JSON + printable HTML with file hashes) and a BSA Sec 63 helper.
**Files:** `src/satyapan/report/pack.py` (`format_inr`, `build_report_pack`, `render_html`), optional `report/templates.py`.
**Key ideas:** transaction facts first, media hashes later. **No submit button and no HTTP call to any government site** — there is no public 1930/NCRP API; a test enforces this. Escape HTML (attacker text could inject code). Indian number format (₹1,23,456).
**Test:** `make task T=T16`. Start on fixture `case_s12`. ⏱ ~5 h.

---

### T19 — Research: metrics, loader, D2 baseline
**In simple words:** the measuring tape of our paper. You write correct metric functions (recall at a fixed false-positive rate, bootstrap confidence intervals), a loader for the ICFD-31k dataset's official splits, and a simple TF-IDF + logistic-regression detector (D2) that runs on your laptop.
**Files:** `research/metrics.py`, `research/data/icfd.py`, `research/baselines/d2_tfidf.py`, `research/run_clean.py` (new), `results/thresholds.json`, `results/research_clean.csv`. (`d3_finetune.py` is run by Shivendra on Kaggle.)
**Golden rules of research (the agent must follow these):**
- Thresholds and settings are chosen on **validation** data only — never on test.
- Use the dataset's official conversation-level splits (never mix chunks of one conversation across splits).
- **Never paste ICFD conversations into any AI tool** and never commit ICFD text. Data lives in `research/_data/` (git-ignored).
**Order:** metrics with unit tests first (pure numpy — get these exactly right) → JSONL loader → `load_icfd` → D2 → D4 scores via `ask_score` (after `lexicon-v1.0`) → `run_clean.py`.
**Test:** `make task T=T19`. Install research extras once: `uv sync --extra research`. ⏱ ~1.5 days.

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
I am Kartikey. Read AGENTS.md, team/Kartikey.md (my section for TNN), docs/tasks/TNN-*.md and
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
I am Kartikey. I'm continuing task TNN on branch tNN-…. Read AGENTS.md, team/Kartikey.md,
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
| 0 (today) | Setup (section 3) | Read `README.md`, `docs/ARCHITECTURE.md` sections 1–3, `docs/tasks/T03` | — |
| 1 | T03 | T04 (`domains.py` → `signals.py`) | PRs for T03/T04 |
| 2 | T08 | T17 | T17 PR |
| 3 | T16 (fixture first; 10-min sync with Saksham) | T19 metrics + loader | demo dry run with the team |
| 4 | T19 D2 + D4 + `run_clean.py` | hand results to Shivendra | dry runs |

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
| Not sure what to do next | Ask the agent: "I am Kartikey. What's my next step?" — it reads this file + `docs/STATUS.md`. |
