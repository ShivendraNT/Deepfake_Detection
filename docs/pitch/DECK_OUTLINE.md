<!-- STUB(T23) — see docs/tasks/T23-pitch-deck.md. Remove this marker when the outline is filled. -->
# Deck outline (5 slides)

## Slide 1 — The problem: verification fails where it matters
- Arup: HK$200M (reported in India as ~₹200 crore) after a deepfake-CFO video call.
- Deepfake-Eval-2024 (arXiv 2503.02857): open-source detectors lose ~50% AUC on video, 48% audio, 45% image in the wild.
- DF26 (arXiv 2609.07369): best detector 69.7% AUROC; 34.5% on commercial generators; humans 52.6%.
- AIForge-Doc (arXiv 2602.20569): AI-edited invoice amounts — TruFor 0.751 AUC, GPT-4o 0.509.
- TODO: one verified Indian loss statistic (I4C / RBI) with source.

## Slide 2 — Our insight: anchor on the payment; detectors decide who verifies
- Floor table + raise-only signals + OOB-Confirm. Diagram: ARCHITECTURE §4. R1-R3 table.

## Slide 3 — Live demo (docs/DEMO_SCRIPT.md)

## Slide 4 — Evidence it works, honestly
- Voice detector through Meet/Opus/AMR: EER __ (n=__) — from results/audio_eval.csv
- Paraphrase robustness chart — figures/money.png (n=__)
- "0/30 prompt injections lowered a band" — results/redteam.json
- Decision relevance 8/12 (illustrative, n=12) — results/decision_relevance.md

## Slide 5 — India + AWS + roadmap
- UTR-first NCRP/1930 pack, `.bank.in`, Hinglish asks, GST invoices.
- AWS ap-south-1: S3 Object Lock, Bedrock in-country Claude Haiku 4.5, Transcribe hi-IN, SES.
- Roadmap: citizen Scam Check, vendor bank-detail attestation standard (GST QR extension), bank integration.
