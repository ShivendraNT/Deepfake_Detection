# Photo check after a WhatsApp-style re-encode (research/video/photo_whatsapp.py)

FF++ c23 test frames, seeded 200 (half real); 200 had a usable face both times. Product photo check, frozen thresholds. Re-encode: longest side <= 1600 px, JPEG quality 60.

| Version | AUC [95% CI] | fakes flagged (>= tau_lo) | reals flagged (>= tau_lo) | fakes >= tau_hi | reals >= tau_hi |
|---|---|---|---|---|---|
| as stored | 0.913 [0.872, 0.949] | 49.0% [39.4, 58.7] (49/100) | 0.0% [0.0, 3.7] (0/100) | 15.0% [9.3, 23.3] (15/100) | 0.0% [0.0, 3.7] (0/100) |
| WhatsApp-style JPEG q60 | 0.872 [0.825, 0.917] | 35.0% [26.4, 44.8] (35/100) | 0.0% [0.0, 3.7] (0/100) | 10.0% [5.5, 17.4] (10/100) | 0.0% [0.0, 3.7] (0/100) |

Paired AUC change (re-encoded - stored): -0.042 [-0.078, -0.008]. Mean logit shift: fakes -0.335, reals +0.439.
