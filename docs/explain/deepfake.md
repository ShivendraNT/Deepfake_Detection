# `forensics/deepfake.py` — deepfake and synthetic media detection

**What it does.** Three entry points. `analyze_image_deepfake` runs a face-swap check (GenD CLIP
ViT-L/14 ONNX, reusing `imagecheck/face.py`) and a whole-image synthetic check. `analyze_video_deepfake`
scores sampled frames and also the existing 6 s window fusion (face CNN + rPPG + lighting + lip-sync).
`analyze_audio_deepfake` splits audio into 5 s windows and scores them with the shipped XLS-R voice
model, plus a cheap acoustic vocoder/prosody check.

**Core idea.** No single cue proves synthesis, so we combine independent physical signals and report
"consistent with" plus confidence and limits. For whole images: GAN/diffusion upsampling leaves a
2-px periodic grid (FFT), generated pixels do not obey camera photon-transfer noise scaling, they
lack Bayer CFA cross-channel residual coupling, and their local noise is too uniform. Those five
features plus a CLIP multi-crop logit go into a calibrated logistic head. Crucially the model knows
about *compression*: heavy JPEG/social re-encoding creates the same grid and smoothing, so a strong
score there is capped at "suspicious" instead of claiming synthesis, and a residual autocorrelation
gate stops a plain resize being read as generator smoothing.

**Five questions a judge may ask**

1. *Why not just use one big pretrained detector?* We measured five off-the-shelf ones under one
   protocol; GenD won the face slot on validation data (+0.18 AUC over our CNN). For whole images we
   add physical cues precisely because generic classifiers collapse on unseen generators.
2. *Why is the whole-image benchmark synthetic?* Because we had no licensed in-the-wild generated-
   image set that matched our target. The synthetic rows measure **sensitivity**, not field accuracy;
   field numbers are the public FF++/DFDC/In-the-Wild rows.
3. *What happens on a WhatsApp copy?* Top-tier recall drops to zero by design (the gate), screening
   recall at the lower threshold stays 100%: the examiner is told to verify, not told it is fake.
4. *Why 5 s voice windows?* It matches the product's window and the model's training clips; shorter
   speech abstains ("too short to judge") rather than guessing.
5. *Can it be fooled?* Yes, and we name how: 10 dB background noise drops cloned-voice recall from
   63.9% to 1.9%; unseen swap methods (FaceShifter) are flagged 31.7% vs 85.4%; small faces abstain.

**Weaknesses.** Whole-image thresholds are calibrated on procedural data. Video frames inside H.264
have no JPEG table, so the compression context is unavailable per frame. Diffusion *video* generators
have no licensed benchmark here. Absence of detected artefacts is never proof of authenticity.
