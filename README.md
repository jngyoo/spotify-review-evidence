# Spotify Review Evidence

A saved partial analysis of historical Spotify app reviews.

## Submission scope

476,154 of 660,609 nonempty reviews were classified (72.08%). Another 184,455 nonempty reviews remain unprocessed; 13 empty texts are separately recorded. The full-corpus requirement is not met. Rankings describe completed records only, which are not a random sample.

Read [the report](REPORT-SUBMISSION.md), [scope and checks](evidence/partial-submission), and [status](STATUS.md). The local course submission package contains the larger row-level export. Public originals are limited to the 500-review development checkpoint.

Dashboard: https://spotify-review-evidence-yj.yujin-jeong125754.chatgpt.site/

The dashboard is backed by a database. Its ranking uses the partial run; displayed quotes come only from the approved 500-review checkpoint. Viewer access is configured separately.

## Method

Pinned local DeBERTa NLI enrichment uses text only, bounded batches, exact-text caching and saved checkpoints. Separate Gemma prompts verify labels, describe issues and choose recommendations from saved aggregates. Ranking is severity sum for complaint/cancellation records, with deterministic ties. Calls and failures are recorded. No paid API is required.

The 50 reference labels remain provisional. Independent model disagreement is not ground-truth accuracy. Read the report for measured results and limitations.

## Reproduction

Use Python 3.12, requirements-nli.txt, Ollama with gemma4:e2b, and the course dataset in data/. No API keys are needed. Full dataset and model weights are not included here.

```sh
python -m pip install -r requirements-nli.txt
python pipeline.py run --classifier nli --input data/cost_100.csv --full data/spotify_reviews_18months.csv --out runs/replay100 --batch 25 --verify 10
python cost/replay.py --pilot evidence/pilot100 --rates cost/rates.csv --out cost-replay.json
```

The saved 100-review cold/warm experiment and actual interruption recording are in evidence/pilot100. The 500-review development evidence is in evidence/checkpoint500. Official checks use vendor/check_submission.py and require the course input files. A passing structural check does not certify complete coverage or label accuracy.

Dashboard source is in dashboard/. Run its standard package scripts using the Sites hosting environment. Source, prompts and configuration are included; credentials and model caches are excluded.
