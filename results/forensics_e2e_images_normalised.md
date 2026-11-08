# Image pipeline end to end (Defactify test shard, held out) — normalised

`python -m research.forensics.e2e_images 40 --normalise` — all image techniques and models, shipped verdict rules (every image centre-cropped to 512 px, JPEG q90 first).

| Set | n | SYNTHETIC | MANIPULATED | SUSPICIOUS | NO_INDICATORS | INCONCLUSIVE |
|---|---|---|---|---|---|---|
| Genuine MS COCO photos | 40 | 0 | 0 | 2 | 38 | 0 |
| AI-generated images | 40 | 0 | 0 | 39 | 1 | 0 |

False alarms (SYNTHETIC or MANIPULATED on a genuine photo): **0 of 40**.
