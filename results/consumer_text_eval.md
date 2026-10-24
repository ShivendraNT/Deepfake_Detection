# The consumer path on open data (research/text/consumer_eval.py)

Held-out TEST texts of the 7 open sets (n = 6576), each sent through the Scam Check page's path: quick check (scam-text model + asks, band from the policy engine) and the impossible-claim rules, higher band wins. Nothing fitted here. Flagged = VERIFY or HOLD. Wilson 95 %. 11.2 ms per text on this CPU.

| Dataset | scams n | scams flagged | scams HOLD | genuine n | genuine flagged | genuine HOLD |
|---|---|---|---|---|---|---|
| clair_fraud | 609 | 97.2% [95.6, 98.2] | 2.3% [1.4, 3.8] | 887 | 0.9% [0.5, 1.8] | 0.2% [0.1, 0.8] |
| hinglish_calls | 95 | 100.0% [96.1, 100.0] | 6.3% [2.9, 13.1] | 17 | 0.0% [0.0, 18.4] | 0.0% [0.0, 18.4] |
| india_14lang | 216 | 100.0% [98.2, 100.0] | 19.0% [14.3, 24.7] | 297 | 1.7% [0.7, 3.9] | 0.3% [0.1, 1.9] |
| india_sms | 84 | 100.0% [95.6, 100.0] | 1.2% [0.2, 6.4] | 711 | 0.6% [0.2, 1.4] | 0.6% [0.2, 1.4] |
| phish_email | 952 | 94.8% [93.1, 96.0] | 4.4% [3.3, 5.9] | 1624 | 5.4% [4.4, 6.6] | 1.9% [1.4, 2.7] |
| scam_dialogue | 159 | 100.0% [97.6, 100.0] | 31.4% [24.7, 39.0] | 160 | 1.2% [0.3, 4.4] | 1.2% [0.3, 4.4] |
| uci_sms | 98 | 91.8% [84.7, 95.8] | 2.0% [0.6, 7.1] | 667 | 1.4% [0.7, 2.5] | 0.1% [0.0, 0.8] |
| ALL | 2213 | 96.6% [95.8, 97.3] | 7.0% [6.1, 8.2] | 4363 | 2.7% [2.2, 3.2] | 0.9% [0.7, 1.3] |

By language (whole path): Other Indian languages = Bengali, Gujarati, Marathi, Punjabi, Kashmiri, Kannada, Malayalam, Telugu, Assamese.

| Language | scams n | scams flagged | genuine n | genuine flagged |
|---|---|---|---|---|
| English | 1846 | 95.9% [94.9, 96.8] | 3375 | 3.2% [2.6, 3.8] |
| English/Hindi SMS | 84 | 100.0% [95.6, 100.0] | 711 | 0.6% [0.2, 1.4] |
| Hindi | 27 | 100.0% [87.5, 100.0] | 35 | 0.0% [0.0, 9.9] |
| Hinglish | 128 | 100.0% [97.1, 100.0] | 64 | 6.2% [2.5, 15.0] |
| Other Indian languages | 128 | 100.0% [97.1, 100.0] | 178 | 0.6% [0.1, 3.1] |

What each part adds (ALL sets): flagged scams / flagged genuine

- policy path only (text model + asks): 96.6% [95.8, 97.3] / 2.4% [2.0, 2.9]
- impossible-claim rules only: 14.7% [13.3, 16.2] / 1.4% [1.1, 1.8]
- both (what the person sees): 96.6% [95.8, 97.3] / 2.7% [2.2, 3.2]
