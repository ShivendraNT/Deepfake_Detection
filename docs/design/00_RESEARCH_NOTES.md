# Session 1 research findings (4 Oct 2026)

Status: targeted verification pass. Full 6-agent research was cancelled for usage reasons.
Next session: continue the "Still to research" list at the bottom.

## Verified facts
- DeepSeek V4 preview released 24 Apr 2026: V4-Pro 1.6T/49B active, V4-Flash 284B/13B active, 1M ctx, open weights, OpenAI+Anthropic compatible API, works with OpenCode. deepseek-chat/reasoner retired after 24 Jul 2026. https://api-docs.deepseek.com/news/news260424
- Bedrock: DeepSeek-V3.1 officially fully managed (Sep 2025). V4-Pro on Bedrock only in 3rd-party blogs (findskill.ai) — check console.
- opencode agents: `.opencode/agents/` or `~/.config/opencode/agents/`; fields description (req), mode primary/subagent/all, model provider/id, temperature, top_p, steps, permission (edit/bash allow/ask/deny + globs), color, disable. https://opencode.ai/docs/agents/
- Deepfake-Eval-2024 (Chandra et al., arXiv 2503.02857): open-source SOTA AUC drops ~50% video, 48% audio, 45% image vs academic benchmarks.
- GOTCHA (Mittal et al., arXiv 2210.06186), code github.com/mittalgovind/GOTCHA-Deepfakes. Audio version: arXiv 2402.18085.

## New findings (detectors & data)
- **Browser-plugin on-device audio deepfake detector** (Pascu, Oneata, Cucu, Müller; arXiv 2606.30780, 2026): XLS-R-300M truncated at layer 7 (101M params), ONNX Runtime in a browser extension, 5 s audio in ~3.4–4.2 s on a single CPU core. EER: ITW 6.6%, ASVspoof19 0.8%, MLAAD 14.4%, OOD avg 8.4% (vs AASIST 11.3%). Code: https://github.com/OctavianPascu97/Audio-Deepfakes-Browser-Plugin  → near-perfect base for our live-call agent (privacy + on-device).
- 2026 audio leaders (couldthisbetrue.com summary, May 2026; verify primary sources): Fake-Mamba (XLS-R + PN-BiMamba) 0.97% EER ASVspoof21 LA, 1.74% DF; WavLM-based ASVspoof5 systems ~3.3% EER but >10% on older sets; wav2vec2+AASIST MIT-licensed ~18% on Speech DF Arena. ADD-C benchmark: codecs (AMR-WB, EVS, Opus) degrade detectors ~5.3 EER points on average. New TTS (Eleven v3, Sesame) not covered by public benchmarks. AudioSeal watermark: streaming, survives MP3/AAC. SynthID Detector portal public.
- **IndieFake** (Kumar, Verma, More; arXiv 2506.19014): 27.17 h, 50 Indian English speakers, balanced real/fake; harder than ASVspoof21 DF. https://indie-fake-dataset.netlify.app/
- **HAV-DF** (arXiv 2411.15457): Hindi audio-video deepfake dataset (faceswap, lipsync, voice cloning); existing detectors score lower than on FF-DF/DFDC. Kaggle: https://www.kaggle.com/datasets/naman3007/hav-df-dataset
- SEA-Spoof (arXiv 2509.19865): multilingual South-East Asia spoof dataset (not Indian).
- CVPR 2026: Boldisor et al., "Investigating Self-Supervised Representations for Audio-Visual Deepfake Detection".

## Hackathon
- Could not find this exact problem statement online (searched 4 Oct). Ask organisers for judging criteria.

## Still to research (next session)
1. Visual/document SOTA 2025-26 (successors to SBI/UnivFD/TruFor; VLM explainable detectors).
2. Competitors: Reality Defender (on AWS), Pindrop, Indian players — "how are we different".
3. India incidents + RBI/SEBI/MeitY 2025-26 rules (synthetic media labelling, bank.in).
4. Scam-call transcript datasets (Hinglish), LLM vishing detection papers.
5. Verify older classic paper titles.

## Documents (big finding — strongly supports verified-at-origin)
- **AIForge-Doc** (Wu et al., arXiv 2602.20569, 2026): 4,061 receipts/forms (CORD, WildReceipt, SROIE, XFUND; 9 languages), numeric fields altered with AI inpainting (Gemini 2.5 Flash Image, Ideogram v2 Edit). TruFor AUC 0.751 (vs 0.96 on classic forgeries), DocTamper 0.563 (vs 0.98), GPT-4o 0.509 (chance). "AI-forged values are indistinguishable to automated detectors and VLMs."
- **DOCFORGE-BENCH** (Zhao et al., arXiv 2603.01433, 2026): 14 methods x 8 datasets, zero-shot. Pixel-AUC >=0.76 but near-zero Pixel-F1; tampered region only 0.27–4.17% of pixels; root cause = calibration failure. Adapting thresholds with just 10 in-domain images recovers 39–55% of the gap. No method works reliably out of the box.
- Implication: pixel forensics alone cannot protect invoices -> cross-check extracted values (amount, account, IFSC, UPI ID) against the counterparty registry/history + signed payment requests. Calibrate thresholds per document type with ~10 samples.

## Competitors (resemble.ai 2026 list — vendor-written, biased)
- Pure detection: Pindrop (contact-centre audio + meetings), Reality Defender (upload screening, runs on AWS), Sensity, Hive, Aurigin. Provenance/workflow: Resemble (watermark), Attestiv (fingerprint evidence chains, insurance), GetReal, iProov/Sumsub (KYC liveness). No India-specific players in that list.
- Our differentiation: action-aware risk + safety floor + signed payment requests + India (Hinglish, 1930/NCRP report pack, BSA Sec 63 evidence) + on-device privacy.

## India regulation
- MeitY IT Amendment Rules 2026: notified 10 Feb 2026, compliance by 20 Feb 2026. "Synthetically generated information" must be prominently labelled (audio: prefixed disclosure); takedown response cut to 3 hours; SSMIs must take user declarations + technical verification before publishing; platforms must embed permanent metadata / provenance identifiers "to the extent technically feasible". https://www.medianama.com/2026/02/223-meity-amendments-it-rules-synthetic-media-deepfakes/
  -> pitch angle: our provenance/metadata checker reads exactly these labels/identifiers.

## Scam-call content detection
- "It Warned Me Just at the Right Moment": LLM-based real-time phone-scam detection (arXiv 2502.03964) — accuracy vs alert-timing trade-off.
- "Talking Like a Phisher" (arXiv 2507.16291): GPT-4o rewrites of real Korean vishing transcripts cut ML classifier accuracy by up to 30.96% while keeping meaning (high BERTScore); <9 s per rewrite. -> supports our threat model: cue-based text classifiers are evadable; anchor on non-forgeable signals.
- Others to read next session: Vishing-Tactics-Bench (arXiv 2609.07151), Explainable agentic conversational-scam detector with summary memory (arXiv 2607.11707), privacy-preserving real-time scam detection + scambaiting (arXiv 2509.05362), AI automating vishing (arXiv 2607.09970).

## Video (2026)
- **GenD** "Deepfake Detection that Generalizes Across Benchmarks" (Yermakov, Cech, Matas, Fritz; WACV 2026; arXiv 2508.06248): fine-tune only LayerNorm (0.03% params) of a pretrained vision encoder + L2-normalised hyperspherical features + metric learning; SOTA avg cross-dataset AUROC over 14 benchmarks (2019-2025). Code https://github.com/yermandy/GenD (CC BY 4.0). Needs paired real/fake from same source video to avoid shortcuts.
- **DF26** "We Cannot Tell Fake From Real Anymore" (Shykula, Yermakov et al.; arXiv 2609.07369, Sep 2026): 2,691 clips (271 real, 2,420 fake) from 7 modern T2V/I2V generators. Humans 52.6% on fakes (vs 74.5% CelebDF++). Best detector 69.7% AUROC; temporal detectors 94.3% -> 48.2%; open-source generators 57.4% AUROC vs commercial 34.5% (worse than chance). -> passive video detection is NOT a reliable defence in 2026; challenge-response + action floor are essential.
- Also: Omni-Fake (CVPR 2026, unified multimodal social-media deepfake benchmark), DeepfakeBench-MM.

## India banking
- RBI: exclusive '.bank.in' domain for banks, registrar IDRBT (under NIXI/MeitY), migration deadline 31 Oct 2025; '.fin.in' planned for non-bank financial entities. -> email check: legit Indian bank mail/links should be on *.bank.in; anything else claiming to be a bank = strong signal.

## GST e-invoice signed QR (validates verified-at-origin idea)
- Invoice Registration Portal (IRP) digitally signs a QR in JWT form with: supplier GSTIN, buyer GSTIN, invoice no., date, invoice value, IRN (hash). Public keys published (e.g., https://einvoice6.gst.gov.in/content/public-keys/); offline verify app exists. Mandatory for B2B above a turnover threshold (source says Rs 500 cr initially; it has been lowered since — believed Rs 5 cr from Aug 2023, VERIFY). https://www.mastersindia.co/blog/signed-qr-code-e-invoicing-system/
- KEY GAP: the signed QR does NOT include the beneficiary bank account -> classic invoice-redirection fraud (same genuine invoice, changed bank details in email) passes. Our Signed Payment Request covers exactly this gap. Demo: verify real GST QR JWT signature + flag bank-account change.

## Free coding agents (checked 4 Oct 2026, evening)
- OpenCode Zen free models (limited-time, list changes; run /models): big-pickle (data may be used for training), space-bunny-free & longcat-2.5-preview-free (zero-retention), mimo-v2.6-flash-free, mimo-v2.5-free, ling-3.1-flash-free, nemotron-3-ultra-free (trial, no confidential data), fledge-alpha-free, muse-spark-1.3-contributor-free, jev-1.13-free. Use as opencode/<id>. https://opencode.ai/docs/zen/
- Zen paid DeepSeek: V4 Flash $0.14/$0.28 per 1M in/out; V4 Pro $1.74/$3.48.
- Gemini CLI: free with personal Google account, 1,000 requests/user/day, model auto-selected. https://geminicli.com/docs/resources/quota-and-pricing/  Gemini API free tier (AI Studio key, Apr 2026 article): 2.5 Flash 15 RPM/1,500 RPD, Pro 5 RPM/50 RPD; free-tier prompts may be used for training. opencode docs do not list Gemini AI Studio key provider.
- GitHub Copilot Student: free for verified students (sign-ups reopened 17 Jun 2026); unlimited completions + 200 AI credits/month for chat/agent/CLI; auto model selection only since 24 Jun 2026. opencode supports GitHub Copilot via /connect (device login).
- Qwen Code free OAuth tier discontinued 15 Apr 2026.
- OpenRouter: free models (~50 req/day without credits; ~1,000/day after one-time $10 credit), /connect in opencode.
- Ollama local works in opencode via @ai-sdk/openai-compatible baseURL http://localhost:11434/v1 (raise num_ctx for tool calls).

## Scam-call datasets found (NOT yet read)
- ICFD-31k (Ahuja 2026) https://rishia.in/rsh/ahuja2026icfd31k/
- HF DatasetNewUser/Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset ; HF anmolshrivastav/scam_ham_india_14_languages ; Kaggle mealss/call-transcripts-scam-determinations
- Open projects: github.com/Romil10/jaanchlo ; github.com/MOHAMEDPARVEZMAHAROOF/scamlens

## Scam-call datasets (READ)
- **ICFD-31k** (Ahuja, Prateek, Singh — NIT Jalandhar; IJCAI-ECAI 2026, doi 10.24963/ijcai.2026/786): 31k+ conversational transcripts, Indian English + Hinglish, 10 fraud categories (incl. financial impersonation), chunk-level streaming labels for real-time detection + explanatory rationales. Systematically generated (synthetic). RoBERTa: 99.40 F1 in-domain, 92.97 F1 on unseen scam types. Code/data: https://github.com/SPELLAILab/ICFD-31k ; paper https://www.ijcai.org/proceedings/2026/0786.pdf
- HF Indian_Cyber_Scam_PhoneCall_Hinglish_Dataset: ~10k text records (SMS/WhatsApp/call transcripts), Hinglish, synthetic-looking, Apache-2.0; categories digital arrest, police impersonation, customs/courier, KYC, OTP theft...; fields caller_type, urgency_level, scam_category.
- HF scam_ham_india_14_languages: 14k balanced SMS (7k/7k), 14 Indian languages incl. Hinglish, synthetic, MIT, 12.6k/1.4k split.
- RESEARCH ANGLE: all are synthetic; "Talking Like a Phisher" shows LLM rewrites cut classifiers ~31%. Novel experiment = train on ICFD-31k, test robustness to LLM-rewritten Hinglish scams (adaptive attacker) -> quantify why the action floor is needed.

## Verified (4 Oct evening)
- GST e-invoicing mandatory above Rs 5 crore turnover (multiple 2026 sources).
- Titles verified: Tak et al. Odyssey 2022 (code github.com/TakHemlata/SSL_Anti-spoofing); AASIST (Jung et al., ICASSP 2022); TruFor (Guillaro et al., CVPR 2023); DocTamper "Towards Robust Tampered Text Detection in Document Image: New Dataset and New Solution" (Qu et al., CVPR 2023, github.com/qcf-568/DocTamper); Feng, Chen, Owens "Self-Supervised Video Forensics by Audio-Visual Anomaly Detection" (CVPR 2023).

## Conversational scam agents (READ)
- "An Explainable Agentic System for Detection of Conversational Scams with Summary-Based Memory" (Adnan, Manjunath, Khare — Univ. of New Haven; arXiv 2607.11707, 2026): multi-agent = single-message detector + sender-authenticity verifier (URLs/phones/emails) + conversation investigator with incremental summarisation (not full replay) + adaptive scheduling (analyse more often as threat rises). Open-weight models (DeepSeek-V3.1, Qwen3-VL) for privacy. ConScamBench-278: 97.8% acc, 98.4% scam recall; LoveFraud02: 100% recall, median detection at 6 turns. User studies N=100, N=45: higher trust/confidence (p<0.001), SUS 74.7.
- "Vishing-Tactics-Bench: Forecasting Exploitation Trajectories in Voice Phishing Calls" (Lee, Sul, Yun, Huang — ETRI; arXiv 2609.07151): predicts WHICH harm an ongoing call is heading to (info theft vs financial exploitation) and WHEN to intervene; 5,645 synthetic Chinese calls, 35,340 tactic-labelled utterances, 6-tactic taxonomy adapted from MITRE ATT&CK; tactic-trajectory features give much earlier warnings — before the money demand. Dataset gated on HF (TeleAntiFraud).
- Innovation hook: Hinglish tactic-trajectory early warning (ICFD-31k chunks + tactic labels) inside the live-call agent.

## Human factors
- Lewis, Vu, Duch, Chowdhury (2022), "Do Content Warnings Help People Spot a Deepfake? Evidence from Two Experiments" (Royal Society report): no warning 10.7% spotted the deepfake; with warning 21.6%. Warnings double detection but most people still fail; warnings mainly raise general distrust. -> UI must give a concrete ACTION (callback, hold) and verifiable facts, not "look closely at the video". Grounds H4.
- Somoray 2025 systematic review of human deepfake detection (Wiley, Human Behavior and Emerging Technologies) — to read.
- Arup Hong Kong case also reported in India as "Rs 200 crore" loss (BusinessToday, Feb 2024).
