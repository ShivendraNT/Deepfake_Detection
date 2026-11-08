# Forensic Lab on the investigation dataset

`make lab-benchmark` — 11 exhibits, 50 s wall time on this machine. Correct 9, flagged-but-not-conclusive 0, cautious (inconclusive on a genuine item) 0, missed 2, false alarms 0.

| Exhibit | File | Ground truth | Verdict | Risk | Grade | Strongest findings |
|---|---|---|---|---|---|---|
| Q1 | `IMG-20261021-WA0011.jpg` | manipulated | **MANIPULATED** | 92 | correct | [strong support] Cloned region: 54 matching keypoints move together; [moderate support] Compression error level differs in 2 region(s) |
| Q2 | `IMG-20261021-WA0012.jpg` | synthetic | **SYNTHETIC** | 80 | correct | [moderate support] AI-generated image classifier: above its strict threshold; [moderate support] Copy of a synthetic picture (Q7) |
| Q3 | `PTT-20261021-WA0007.opus` | synthetic | **NO_INDICATORS** | 10 | missed |  |
| Q4 | `PTT-20261021-WA0009.opus` | synthetic | **NO_INDICATORS** | 14 | missed | [weak support] 1 possible edit point(s); [weak support] Voice partly suspicious: 3 of 4 windows elevated |
| Q5 | `VID-20261021-WA0003.mp4` | synthetic | **SYNTHETIC** | 88 | correct | [strong support] Face replaced: footage of R2 with another person's face; [weak support] Face score elevated in 1 window(s) |
| Q6 | `call_recording_20261021_1412.wav` | manipulated | **MANIPULATED** | 84 | correct | [strong support] Mains-frequency trace breaks at 16.5 s |
| Q7 | `officer_id_photo_original.png` | synthetic | **SYNTHETIC** | 80 | correct | [moderate support] Content Credentials declare generative AI; [moderate support] AI-generated image classifier: above its strict threshold |
| R1 | `daughter_known_voice_sample.m4a` | authentic | **NO_INDICATORS** | 10 | correct |  |
| R2 | `laptop_seized_clip_0193.mp4` | authentic | **NO_INDICATORS** | 3 | correct | [moderate support] Mains-frequency trace is continuous |
| R3 | `notice_template_from_laptop.jpg` | authentic | **NO_INDICATORS** | 14 | correct | [weak support] JPEG grid is shifted from the file's own grid |
| R4 | `profile_photo_source.jpg` | authentic | **NO_INDICATORS** | 10 | correct |  |

Cross-exhibit links found: 9 (near_duplicate, same_face, same_speaker, shares_content).
