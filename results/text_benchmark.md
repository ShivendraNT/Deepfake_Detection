# Text benchmark: scam / phishing / fraud messages (research/text/bench.py)

Open datasets, template-deduplicated, leakage-safe splits; C chosen by 5-fold GroupKFold CV on train; thresholds frozen on val (tau_hi = 1% FPR on legitimate val texts); every test split scored once. AUC/AP: 95% template-cluster bootstrap; rates: Wilson 95%. Protocol: docs/TEXT_BENCHMARK.md.

Shipped model (tfidf_union): C = 32.0, CV AUC 0.9977 ± 0.0005; tau_hi = 0.4271.

## Test AUC per dataset

| Dataset | n (fraud) | tfidf_union | tfidf_spec | tfidf_lodo | asks_product | asks_frozen |
|---|---|---|---|---|---|---|
| phish_email | 2576 (952) | 0.994 [0.991, 0.996] | 0.998 [0.997, 0.999] | 0.693 [0.671, 0.713] | 0.517 [0.508, 0.526] | 0.514 [0.506, 0.523] |
| clair_fraud | 1496 (609) | 1.000 [0.999, 1.000] | 1.000 [1.000, 1.000] | 0.982 [0.977, 0.988] | 0.627 [0.610, 0.646] | 0.608 [0.592, 0.626] |
| uci_sms | 765 (98) | 0.989 [0.976, 0.997] | 0.997 [0.991, 1.000] | 0.856 [0.815, 0.893] | 0.509 [0.498, 0.525] | 0.509 [0.498, 0.526] |
| india_sms | 795 (84) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.850 [0.815, 0.881] | 0.500 [0.500, 0.500] | 0.499 [0.498, 0.500] |
| india_14lang | 513 (216) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.753 [0.708, 0.796] | 0.575 [0.548, 0.601] | 0.582 [0.555, 0.609] |
| hinglish_calls | 112 (95) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.995 [0.983, 1.000] | 0.516 [0.500, 0.536] | 0.516 [0.500, 0.536] |
| scam_dialogue | 319 (159) | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.725 [0.665, 0.780] | 0.742 [0.703, 0.782] | 0.689 [0.653, 0.727] |

## Operating point of the shipped model (threshold frozen on val, 1% FPR target)

| Dataset | caught (TPR) | false alarms (FPR) | F1 at val max-F1 thr |
|---|---|---|---|
| phish_email | 95.0% [93.4, 96.2] | 2.6% [2.0, 3.5] | 0.9529 |
| clair_fraud | 98.2% [96.8, 99.0] | 0.4% [0.2, 1.1] | 0.9876 |
| uci_sms | 91.8% [84.7, 95.8] | 1.2% [0.6, 2.4] | 0.9368 |
| india_sms | 100.0% [95.6, 100.0] | 0.0% [0.0, 0.5] | 1.0 |
| india_14lang | 100.0% [98.2, 100.0] | 0.0% [0.0, 1.3] | 1.0 |
| hinglish_calls | 100.0% [96.1, 100.0] | 0.0% [0.0, 18.4] | 1.0 |
| scam_dialogue | 100.0% [97.6, 100.0] | 0.0% [0.0, 2.3] | 1.0 |

## Zero-shot ask lexicon (>= 1 ask = flag)

| Dataset | asks_product TPR | asks_product FPR | asks_frozen TPR | asks_frozen FPR |
|---|---|---|---|---|
| phish_email | 6.1% [4.7, 7.8] | 2.7% [2.0, 3.6] | 5.8% [4.5, 7.4] | 2.9% [2.2, 3.8] |
| clair_fraud | 26.1% [22.8, 29.7] | 0.7% [0.3, 1.5] | 22.3% [19.2, 25.8] | 0.7% [0.3, 1.5] |
| uci_sms | 2.0% [0.6, 7.1] | 0.3% [0.1, 1.1] | 2.0% [0.6, 7.1] | 0.1% [0.0, 0.8] |
| india_sms | 0.0% [0.0, 4.4] | 0.0% [0.0, 0.5] | 0.0% [0.0, 4.4] | 0.1% [0.0, 0.8] |
| india_14lang | 16.7% [12.3, 22.2] | 1.7% [0.7, 3.9] | 18.1% [13.5, 23.7] | 1.7% [0.7, 3.9] |
| hinglish_calls | 3.2% [1.1, 8.9] | 0.0% [0.0, 18.4] | 3.2% [1.1, 8.9] | 0.0% [0.0, 18.4] |
| scam_dialogue | 49.1% [41.4, 56.8] | 0.6% [0.1, 3.5] | 38.4% [31.2, 46.1] | 0.6% [0.1, 3.5] |

## Evasion robustness (2213 fraud test texts attacked; 4363 clean legitimate texts)

| Attack | TPR @ tau_hi, with de-obfuscation | TPR, without | AUC with | AUC without | asks_product TPR |
|---|---|---|---|---|---|
| clean | 97.0% [96.2, 97.6] | 96.6% [95.8, 97.3] | 0.9977 | 0.9976 | 15.2% [13.8, 16.7] |
| homoglyph | 97.0% [96.2, 97.6] | 72.9% [71.0, 74.7] | 0.9977 | 0.9878 | 4.3% [3.5, 5.2] |
| leet | 96.9% [96.1, 97.6] | 82.5% [80.8, 84.0] | 0.9977 | 0.9913 | 3.2% [2.5, 4.0] |
| zero_width | 97.0% [96.2, 97.6] | 95.8% [94.9, 96.6] | 0.9977 | 0.997 | 9.7% [8.6, 11.0] |
| spacing | 96.8% [96.0, 97.5] | 95.4% [94.4, 96.2] | 0.9978 | 0.9963 | 14.8% [13.4, 16.3] |
| combined | 96.2% [95.4, 97.0] | 40.1% [38.1, 42.2] | 0.9973 | 0.9759 | 0.5% [0.3, 0.9] |
