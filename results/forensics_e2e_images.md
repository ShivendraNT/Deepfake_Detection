# Image pipeline end to end (Defactify test shard, held out) — native files

`python -m research.forensics.e2e_images 40` — all image techniques and models, shipped verdict rules (files as distributed; real and AI images differ in size and format).

| Set | n | SYNTHETIC | MANIPULATED | SUSPICIOUS | NO_INDICATORS | INCONCLUSIVE |
|---|---|---|---|---|---|---|
| Genuine MS COCO photos | 40 | 0 | 0 | 1 | 39 | 0 |
| AI-generated images | 40 | 0 | 0 | 40 | 0 | 0 |

False alarms (SYNTHETIC or MANIPULATED on a genuine photo): **0 of 40**.
