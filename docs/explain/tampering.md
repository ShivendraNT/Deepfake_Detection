# `forensics/tamper.py` — image, video and audio tampering detection

**What it does.** Image: `ela_analysis` (error level analysis), `double_jpeg_analysis` (quantization
tables + 8x8 DCT histogram comb + block-grid consistency), `copy_move_analysis` (cloned regions),
`noise_residual_analysis` (sensor-noise inconsistency). Each produces a heatmap; the suite produces a
4-panel composite. Video: duplicated/frozen frames, dropped-frame/temporal-splice jumps, macroblock
re-encoding signs, plus a timeline chart. Audio: waveform splice transients and room noise-floor step
shifts, plus a spectrogram with markers. All use non-absolutist language.

**Core idea.** Compression and sensor noise are *fingerprints of the last operation*. If one region
of a JPEG was re-saved, pasted, cloned or airbrushed, its residual statistics stop matching the rest
of the frame. So the detectors are all "local statistics versus the frame's own baseline", with two
guards learned the hard way: relative z-scores alone fire on smooth, heavily quantised images, so we
require **absolute** evidence (mean ELA energy; a real gap between the noisiest region and the median
noise floor). And copy-move matching must survive JPEG shifting pixel values, so the absolute patch
difference allowance scales with block texture energy while high-pass correlation must stay >= 0.88.

**Five questions a judge may ask**

1. *Why ELA if everyone says ELA is unreliable?* Because it is one vote, not the verdict. It only
   contributes when the absolute residual energy and a spatially coherent block outlier agree, and
   the combined score needs corroboration from an independent check.
2. *How does copy-move matching work?* Overlapping 16x16 blocks, pooled descriptors, lexicographic
   sort for candidate pairs, then verification by patch difference plus high-pass correlation, then
   clustering by displacement vector. A dense cluster with one dominant shift = a cloned region.
   ±2 px search handles non-stride offsets.
3. *Why the ±2 px search and the adaptive difference?* A clone is rarely aligned to my 4 px stride,
   and re-saving changes pixels by several levels inside texture. Without both, real clones were
   missed; with them, the demo clone is found at shift [116, 116].
4. *What about video?* Real edits show as near-zero inter-frame difference during motion (freeze),
   or as robust outliers in inter-frame difference (drop/splice). Static talkings heads are excluded
   by gating on the median motion.
5. *And audio?* A cut leaves a 1-2 sample transient (peak-to-RMS z-spike) and/or a step change in
   the 0.5 s background floor. A DAW crossfade with matched room tone defeats both, which we state.

**Weaknesses.** PNG screenshots and flat regions; copy-move over untextured areas; cross-faded
splices; strong scene cuts look like dropped frames (the examiner must look at the timestamp); all
numbers are on synthetic constructions, so they measure sensitivity.
