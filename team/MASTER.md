# MASTER — Shivendra (tech lead)

> **For the AI agent reading this (Claude Code / Antigravity):** you are working with **Shivendra, the tech lead**. He owns the critical path, the research track, every merge into `main`, and the final call on any design question. Be direct and technical. Before suggesting work, check `docs/STATUS.md`, `git log --oneline -15` and open PRs (`gh pr list`), then tell him: (1) what's blocking teammates right now, (2) his next critical-path step, (3) which tool/model to use for it.

## 0. How to use this file
- **Claude Code** (main builder): `cd ~/Desktop/Deepfake_Detection && claude` → type `I am Shivendra. Brief me.`
- **Antigravity** (second opinion + parallel chores): open the folder → new chat → `I am Shivendra. Brief me.`
- Teammates' files: `team/Saarika.md`, `team/Kartikey.md`, `team/Saksham.md`. Their agents read those; keep them in sync if you change the plan.

---

## 1. Your role in one paragraph
You build the hardest, most connected parts (live-call capture → live transcript → LLM explanation → research results), you are the **only one who merges into `main`**, you protect the frozen core (contracts, policy, invariant tests), and you run the demo. Everyone else's tasks are designed so that free/mid models + the harness can finish them; your job is to unblock, review fast, and integrate.

## 2. Your toolbox

| Tool | Model | Use it for |
|---|---|---|
| **Claude Code** (primary) | default (your plan) | T07, T11, T15, T20, T21; integration fixes; anything touching `contracts/` or `policy/`. Use plan mode (Shift+Tab) for every critical-path task. |
| Claude Code subagents/commands | — | `/task-start TNN`, `/review-pr <branch>` (uses `.claude/agents/reviewer.md`), `/new-task` (spec-writer, if you add a task) |
| **Antigravity → Claude Opus** | newest Opus in the dropdown | **Independent second reviewer** on teammates' PRs (a different context from Claude Code catches different things); architecture questions. Same "authority" role you gave the team. |
| **Antigravity → Gemini Pro** | newest Gemini Pro | Parallel chores in the Agent Manager while Claude Code works: demo fixtures, doc updates, deck text, small console tweaks. |
| Kaggle (2×T4, free) | — | T19 D3 fine-tune, T20 paraphrase generation (vLLM). |
| Colab (free) | — | T22 voice-clone clips (F5-TTS / XTTS-v2) from **consenting** voices only. |
| opencode / Copilot | free models | Only if everything else is rate-limited. |

**Team model policy (already in their files):** Antigravity **Gemini Pro = worker**, **Claude Opus = authority** (max 3 calls per task: plan approval, final review, one unblock), fallback ladder → opencode free (Zen) → Copilot Agent → Gemini CLI. Same `AGENTS.md` everywhere.

## 3. Day-0 lead checklist (do today, before the team starts)
- [ ] **Email ICFD-31k authors** (Ahuja, Prateek, Singh — NIT Jalandhar): defensive robustness study, paraphrases kept private, no release of generated text. Needed before T20. (License forbids generating scam scripts / commercial use.)
- [ ] **Email Pascu et al.** about the browser-plugin repo license (ONNX weights, no license file). Fallback: server-side scoring on the MacBook.
- [ ] **Ask the organisers** for judging criteria + whether AWS usage is scored + demo format/time.
- [ ] **GitHub:** add Saarika, Kartikey, Saksham as collaborators; Settings → Branches → protect `main` (require PR, no force push).
- [ ] **AWS:** account/credits, region `ap-south-1`, Bedrock model access for Claude Haiku (in-country inference profile), S3 bucket with Object Lock (**GOVERNANCE**), SES sandbox verified addresses. Put keys only in your local `.env`.
- [ ] **Consent forms:** print `docs/consent/VOICE_CLONE_CONSENT_TEMPLATE.md` ×4; signed copies stay offline.
- [ ] **Dataset links** for Saarika (In-the-Wild, HAV-DF) and Kartikey (ICFD-31k download instructions) — share in the group, never commit data.
- [ ] **Local cleanup (optional):** you made worktrees for t03/t05/t09, which now belong to others. `git worktree remove ~/Desktop/sat-t03` (same for t05, t09), then `git branch -D t03-eml-parser t05-ask-extractor t09-evidence-vault`. Keep `~/Desktop/sat-t07` for T07.
- [ ] **Commit these team files + updated `docs/STATUS.md`** and push, so everyone's agent sees them after cloning.

## 4. Who owns what

| Person | Tasks | Area |
|---|---|---|
| **Shivendra** | T07, T11, T15, T20, T21, T22 (lead), D3 run + review in T19, thresholds in T18, research claims in T23 | live-call engine, LLM safety, research results, demo |
| **Saarika** | T05, T10, T18, T23, demo operator in T22 | ask extractor (= research D4), side panel, voice calibration, deck |
| **Kartikey** | T03, T04, T08, T17, T16, T19 (metrics, loader, D2) | evidence checkers, report pack, research measurement |
| **Saksham** | T09, T06, T12, T13, T14, T24 (stretch) | console, vault, OOB-Confirm, workflows, explanations |

**Dependency map (what blocks what)**
```
T05 (Saarika) ──► T11 (you) ──► T22 demo
     │             ▲
     │         T07 (you) ──► T10 live test (Saarika) ──► T22
     │             └──► T18 (Saarika + you) ──► thresholds for T07/T17
     └─ tag lexicon-v1.0 ──► T19 D4 (Kartikey) ──► T20 ──► T21 (you) ──► T23 (Saarika + you)
T09 + T13 (Saksham) ──► T16 (Kartikey)
T14 (Saksham) ──► T15 (you)
T06 (Saksham) ──► T12/T13 screens ──► T22
```

### 4b. Critical-path pairing with Saarika
Her T05/T10/T18 are the direct inputs and outputs of your T07/T11, so the two tracks are scheduled as a pair. The same checkpoints are in her file:

| # | When | Checkpoint | Your part |
|---|---|---|---|
| P1 | Day 1 start | T05 kickoff | agree A1–A7 boundaries + "must not fire" negatives (these decide research D4 quality) |
| P2 | Day 1 evening | T05 review | read precision/recall, check over-broad patterns |
| P3 | Day 2 morning | T05 freeze | merge, then she tags `lexicon-v1.0`; you tag `prereg-v1` once T19's config is written |
| P4 | Day 2 evening | First live Meet call | your T07 capture + her T10 panel; measure ms/window on the M4 |
| P5 | Day 3 | T18 recording session | Meet-captured bonafide windows, speaker-disjoint split, fit τ_hi/τ_lo together |
| P6 | Day 3 | Live ask chips | your T11 → her panel; measure spoken-ask → chip latency (≤ 13 s) |
| P7 | Day 4 | Deck + rehearsal | you add research figure + check every claim; she presents the demo slide |

Review all of Saarika's PRs yourself (live during the checkpoints where possible). For Kartikey's and Saksham's PRs: Antigravity Opus review first (their Step 7), then your `/review-pr`.

## 5. Your tasks

### T07 — Extension capture core (Day 1, critical path)
Tab audio via `chrome.tabCapture` → offscreen doc → passthrough to speakers **first** → 16 kHz mono → 5 s windows → Pascu ONNX (XLS-R layer-7, 101M) in onnxruntime-web → `voice_rules.js` → events to side panel + backend. Spec: `docs/tasks/T07-extension-capture.md`. Measure ms/window on the M4 and log in STATUS. Model files git-ignored; tell Kartikey where they are (T17).

**T07 to-do (steps 1-7 done + reviewed, commit a8a9b86; step 8 left):**
- [x] `uv run --with onnx python scripts/prepare_ext_models.py` — `extension/models/logreg_prob.onnx` exists.
- [ ] Step 8 manual test: `chrome://extensions` → Load unpacked `extension/` → Meet call with a teammate → click the action. Check (a) you still hear them, (b) a `ms/window` line ~every 5 s in the offscreen console (inspect it from `chrome://extensions`), (c) no score in side-panel messages, (d) ms/window on the M4 (Node measured ~2.8 s; must stay under 5 s).
- [ ] Write (a)-(d) into `docs/STATUS.md` notes, tick step 8 in the spec, set T07 `done`, commit.
- [ ] Delete the local backup branch: `git branch -D t07-backup-before-squash` (never push it — it holds 38 MB of old ORT files).
- [ ] Push: `git push -u origin t07-extension-capture`, then PR → merge into `main`.

### T11 — Live transcript path (Day 2)
10 s MediaRecorder chunks → `LiveService.handle_chunk` → mlx-whisper turbo locally → T05 `extract_asks` → policy re-decision → SSE to the panel. **No LLM in this loop.** Target ask-chip latency ≤ 13 s (P6).

**T11 to-do (steps 1-5 + offscreen upload done, branch `t11-live-transcript`; step 6 left):**
One session (~30 min) covers this AND T07 step 8: both need the extension running in Chrome.
- [ ] **Warm-up (downloads the ~1.6 GB model once):**
  `ffmpeg -f lavfi -i anullsrc=d=2 -y /tmp/s.wav && PYTHONPATH=src uv run python -c "from satyapan.adapters.transcribe_whisper import WhisperTranscriber as W; print(W().transcribe(open('/tmp/s.wav','rb').read(), 'audio/wav'))"`
  then `make run`.
- [ ] **Clips (data hygiene, AGENTS §10):** record 10 Hinglish asks in YOUR own voice (or a consenting
  teammate's), e.g. the lines in `tests/tasks/test_t11_live.py`. Fake names/amounts only. Keep them
  out of the repo (`~/satyapan-clips/`). Each clip: ~3 s silence, the ask, ~3 s silence.
- [ ] **Run:** `chrome://extensions` → reload `extension/` → open a clip as a tab (`file:///…/clip01.wav`)
  → click the action → play. Any tab can be captured, so no Meet call is needed for T11.
- [ ] **Read the numbers:** offscreen console (`chrome://extensions` → *Inspect views: offscreen.html*)
  prints `chunk N: X ms chunk-end -> events; asks=[…]`. Spoken-ask → chip ≈ (seconds from the ask
  ending to that chunk's end, ≤ 10) + X. Pass = ≤ 13 s, so X must stay ≤ ~3 s.
- [ ] Log each clip in `results/t11_latency.csv` (header already there). Not `dry_runs.csv`: that file
  is T22's artifact and creating it early turns its test from skipped to failing.
- [ ] STATUS: T11 note with median + max seconds and failed clips; set `done`. Merge PR into `main`.

### T15 — Bedrock summary + faithfulness + red-team (Day 3)
Claude Haiku via Bedrock Converse (`in.` profile, no tools, 5 s timeout) → `check_faithfulness` (every claim must cite an evidence id that supports it) → fall back to Saksham's T14 templates. Extend injections 12 → 30, `scripts/redteam.py` → `results/redteam.json`. Invariant: summaries can never change the band.

### T19 (your part) — review + D3 on Kaggle (Day 3)
Review Kartikey's metrics/loader carefully (paper depends on them). Write the D3 config, tag `prereg-v1`, run XLM-R-base / MuRIL-base / RoBERTa-base on Kaggle, download score CSVs only.

### T20 — Paraphrase attacks (Day 3, Kaggle GPU) — only after the ICFD authors reply or you decide on scope
P1 style-stripping paraphrases of test frauds, P0 meaning-preserving paraphrases of normals, P2 ask-obfuscation; filters (LaBSE ≥ 0.80, third-family judge, 200-pair human audit with Cohen's κ). Text stays private; only stats are committed.

### T21 — Evaluation + money figure (Day 4)
Recall@1%/5% FPR with 95% CIs per detector × condition, paired drop-difference tests (H1/H2), residual exposure, `figures/money.png`. Thresholds from T19 validation only.

### T22 — Demo lead (Day 3–4)
Consent → clone clips on Colab (local only) → pre-test through real Meet capture (log catch rate honestly) → `demo_call.html` offline tab → 10 dry runs in `results/dry_runs.csv` → backup recording. Roles: you narrate + run the "CFO" call; Saarika runs side panel + console; Saksham plays the real CFO answering OOB-Confirm on a second laptop; Kartikey shows the report pack.

## 6. Merge + review protocol
1. Teammate opens PR (their Step 8) with `make check` green and Opus review done.
2. You: `gh pr checkout <n>` → `make check` → `make task T=TNN` → Claude Code `/review-pr`.
3. Look specifically for: edits outside the spec's file list, weakened tests, network imports outside `adapters/`, raw scores shown to makers, anything that could lower a band.
4. Squash-merge. Update `docs/STATUS.md` if they forgot. Post "merged TNN, pull main" in the group.
5. Merge window: twice a day (~1 pm, ~9 pm) so people aren't blocked and conflicts stay small.

## 7. Your schedule

| Day | You | Team checkpoints |
|---|---|---|
| 0 | Day-0 checklist; commit team files; post setup instructions | everyone does setup + `make check` green |
| 1 | T07 | P1 (start), P2 (evening); merge T03/T04/T09 |
| 2 | T11, T07 polish | P3 (morning), P4 (evening); merge T05/T08/T06 |
| 3 | T15, T19-D3 (Kaggle), T20 | P5 + P6; merge T10/T12/T13/T14/T16/T17; first full dry run |
| 4 | T21, T22 dry runs to 10/10 | P7; final merges; backup recording; freeze `main` 6 h before submission |

**Standup (10 min, every morning in the group):** each person — done yesterday / doing today / blocked by. Unblocking is your first job each day.

## 8. Risks + fallbacks
| Risk | Fallback |
|---|---|
| Pascu model license unanswered / ONNX fails in browser | score windows server-side on the MacBook (same rule), keep extension UI |
| mlx-whisper too slow | Amazon Transcribe streaming hi-IN/en-IN, or smaller Whisper |
| Bedrock access/credits missing | template explanations only (T14) — the product works without the LLM |
| ICFD authors don't reply in time | run T19 clean results only; present T20/T21 as pre-registered next step |
| Live Meet fails during judging | `demo_call.html` offline tab, then backup recording |
| A teammate blocked > half a day | take the task in Claude Code yourself or re-assign; the spec makes handover easy |

## 9. Claims to verify before slides
NCRP form field order; AWS prices/credit amount; DPDP Rules phase-in dates; competitor list (Vastav AI, Kroop AI, pi-labs, Google Scam Detection); every number must trace to a file in `results/` with n and CI.
