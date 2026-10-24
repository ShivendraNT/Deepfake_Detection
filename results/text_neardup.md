# Near-duplicate audit of the text test splits (research/text/neardup.py)

Max cosine similarity (shipped model's TF-IDF space) of each test text to any training text. 'Novel' = max cos < 0.8. Same frozen model and threshold.

| Dataset | test n | near-copies (cos >= 0.9) | (>= 0.8) | AUC all test | novel n (fraud) | AUC novel only | TPR novel @ tau_hi | FPR novel @ tau_hi |
|---|---|---|---|---|---|---|---|---|
| phish_email | 2576 | 9.0% | 16.2% | 0.994 [0.991, 0.996] | 2159 (693) | 0.991 [0.988, 0.994] | 93.4% | 2.9% |
| clair_fraud | 1496 | 6.2% | 11.6% | 1.000 [0.999, 1.000] | 1323 (455) | 1.000 [0.999, 1.000] | 97.6% | 0.5% |
| uci_sms | 765 | 1.2% | 2.1% | 0.989 [0.976, 0.997] | 749 (85) | 0.987 [0.973, 0.997] | 90.6% | 1.2% |
| india_sms | 795 | 0.0% | 3.4% | 1.000 [1.000, 1.000] | 768 (84) | 1.000 [1.000, 1.000] | 100.0% | 0.0% |
| india_14lang | 513 | 37.8% | 68.2% | 1.000 [1.000, 1.000] | 163 (80) | 1.000 [1.000, 1.000] | 100.0% | 0.0% |
| hinglish_calls | 112 | 39.3% | 96.4% | 1.000 [1.000, 1.000] | 4 (4) | n/a | 100.0% | n/a |
| scam_dialogue | 319 | 2.2% | 6.6% | 1.000 [1.000, 1.000] | 298 (159) | 1.000 [1.000, 1.000] | 100.0% | 0.0% |
