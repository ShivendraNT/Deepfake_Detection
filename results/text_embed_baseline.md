# Transformer baseline: multilingual-e5-small embeddings + LR (same protocol)

Model `intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`, first 256 tokens. C = 100.0 by grouped CV (AUC 0.9832 ± 0.0016); tau_hi = 0.9579 on val.

| Dataset | union AUC | union TPR @ tau_hi | union FPR @ tau_hi | LODO AUC |
|---|---|---|---|---|
| phish_email | 0.967 [0.960, 0.973] | 64.9% [61.8, 67.9] | 1.8% [1.3, 2.6] | 0.743 [0.724, 0.762] |
| clair_fraud | 0.993 [0.990, 0.996] | 78.8% [75.4, 81.9] | 0.6% [0.2, 1.3] | 0.916 [0.903, 0.930] |
| uci_sms | 0.974 [0.954, 0.989] | 67.3% [57.6, 75.8] | 0.4% [0.1, 1.3] | 0.920 [0.886, 0.952] |
| india_sms | 0.999 [0.997, 1.000] | 71.4% [61.0, 80.0] | 0.0% [0.0, 0.5] | 0.950 [0.929, 0.967] |
| india_14lang | 0.991 [0.983, 0.996] | 71.8% [65.4, 77.3] | 0.3% [0.1, 1.9] | 0.901 [0.873, 0.925] |
| hinglish_calls | 1.000 [1.000, 1.000] | 92.6% [85.6, 96.4] | 0.0% [0.0, 18.4] | 0.975 [0.945, 0.995] |
| scam_dialogue | 1.000 [0.999, 1.000] | 78.6% [71.6, 84.3] | 0.0% [0.0, 2.3] | 0.661 [0.600, 0.721] |

Combined obfuscation attack, TPR @ tau_hi: raw input 69.4% [67.5, 71.3]; after our de-obfuscation 75.7% [73.9, 77.4].
