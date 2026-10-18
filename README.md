# Spotify Review Evidence

This repository contains the reproducible local pipeline, a database-backed dashboard, and measured development evidence. **Full-corpus processing is still in progress.**

- [500-review report](REPORT-500.md)
- [Selected 100-review pilot](evidence/pilot100/) with actual interruption recording and passing deterministic audit
- [500-review checkpoint](evidence/checkpoint500/) with saved verification, ranking and citations
- [Current status](STATUS.md)
- [Hosted dashboard](https://spotify-review-evidence-yj.yujin-jeong125754.chatgpt.site) — currently owner-private; grader access is pending.

Source data and model weights are downloaded separately. This repository does not contain API keys or model weights. API charges in the saved runs are $0; electricity and hardware costs were not measured.

## Data and scope

Source: [course dataset ZIP](https://drive.google.com/file/d/1P0rUoAS_wVjp3BYKqXMEyD4u0uJP1Bvf/view). Extract the 11 files into `data/`. Full CSV SHA-256: `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.

Full ingestion has been verified: 660,622 original IDs, 13 empty texts, 159,701 missing app versions, 484,189 distinct nonempty texts. See `grading/ingestion.json` and `data/validation.json`. **Ingested does not mean classified.** The selected 100-review pilot is complete and larger checkpoints are in progress.

## Run

Core tools require Python 3.9+; the selected NLI path uses Python 3.12 and `requirements-nli.txt`. Ollama must be installed with `gemma4:e2b` available at localhost:11434. Model execution is explicit; importing code, reranking and cost replay do not call a model.

```sh
python3 pipeline.py ingest --input data/spotify_reviews_18months.csv --db data/source.sqlite
python3 pipeline.py run --input data/cost_100.csv --full data/spotify_reviews_18months.csv --out cost/pilot --batch 5 --verify 10
# Repeat the identical command for the warm run.
python3 cost/replay.py
python3 pipeline.py rank --db cost/pilot/state.sqlite --out cost/pilot/recomputed
python3 -m unittest discover -s tests -v
```

Use a fresh output folder for changed model/prompt/schema/output settings. The default limit is 1,800 seconds of enrichment admission. An in-flight call and downstream work may continue beyond that limit. One worker, maximum 50 reviews/request, one invalid-output retry, no fallback and no paid provider. Model output truncation is a failure. Every original ID remains separate even when exact text is reused. Valid results commit atomically in SQLite. Failed records are visible quarantines; existing quarantines are not automatically retried on resume.

For a controlled checkpoint, use `--max-new 10 --enrich-only`, then resume the same folder with `--phase resume`. This is a stop/resume exercise; the required genuine interruption recording must be captured separately. Do not present generated checkpoints as a recording.

## Architecture

CSV → source SQLite → enrichment → independent verification → topic-level issue grouping → deterministic ranking → constrained model recommendation.

- **Enricher:** text only, fixed rubric, exact ID-set and field checks. Code supplies the full original text as the exact evidence quote and empty entity lists (conservative extraction). These decisions require qualitative evaluation.
- **Verifier:** a declared seeded random sample, original text and rubric only; never sees enrichment predictions. Separate instructions and saved call evidence. The selected NLI path uses a different verifier model (Gemma); earlier generative pilots use the same model in both roles. Agreement between models is not ground truth.
- **Grouping:** code maps complaint/cancellation to stable primary-topic issue IDs; a model names/describes each issue from bounded examples. This is a coarse baseline.
- **Ranking:** severity sum, descending; ascending issue ID on ties. Means use six-decimal half-up rounding. Praise/request/unclear excluded. No paid call required.
- **Memo:** saved aggregates and bounded examples only. Code validates issue/claim/review references and renders numbers from saved claims. Human review of the argument remains required.

Roles and prompts are in `prompts/`. SQLite `calls` stores full requests, responses, attempts and actual token counts; `artifacts` stores saved downstream handoffs. Source fields and row hashes preserve the grading contract. Golden answers are never read by this pipeline.

## Evaluation and evidence

- `golden_50_to_label.csv` in the linked dataset: blank human-label template; **must be completed by the student** before final evaluation.
- `tests/`: ID-set rejection, invalid numerical outputs, source mutation detection, ranking exclusion and stable ties.
- `cost/pilot/verification.json`: independent labels and disagreements, once run completes.
- `cost/pilot/grading/`: pilot records, calls, membership, ranking and claims; explicitly not a full-corpus export.
- `cost/replay.py`: offline repricing and stage-specific projections. Electricity, hardware and hosting costs are unknown, not zero.

## Submission blockers

1. Human golden labels and per-field evaluation/error analysis.
2. Final-model injection/planted-error experiments. The earlier Gemma injection test failed and remains documented; a genuine interruption/resume recording is saved under `cost/nli-final/`.
3. 500 / 10,000 checkpoints and an affordable final-scale run with honest completion counts.
4. Update the deployed database-backed pilot dashboard with final results and configure grader access.
5. Final evidence-backed recommendation, clean-environment checks, public repository and submission URL.

Historical self-selected reviews cannot establish revenue risk, confirmed churn or causal retention improvements. The brief mentions a 100,000 minimum in some places; the supplied contract and coverage formula still use the full corpus. Disclose reduced scope rather than claiming equivalent full coverage.

## Selected free local classifier

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-nli.txt
export SPOTIFY_MODEL_CACHE="$PWD/model-cache"
.venv/bin/python pipeline.py run --classifier nli --input data/cost_100.csv --full data/spotify_reviews_18months.csv --out cost/new-nli-pilot --batch 5 --verify 10
python3 cost/replay.py --pilot cost/nli-final --out cost/nli-final/cost-report.json
```

The first NLI run downloads model weights. The exact downloaded revision, hypotheses and configuration digest are saved in `nli_model.json`. Subsequent runs reuse local weights. Original review text is evaluated against fixed label hypotheses. Long texts are processed in overlapping chunks without truncating the source. Entailment scores are diagnostic scores, not calibrated correctness probabilities. English-model limitations and ambiguous results are marked for review. Gold labels are never model inputs. Hypotheses were developed using only the development sample.

NLI output tokens are zero because this is a discriminative model; input usage counts all nonpadding premise/hypothesis tokens actually processed. These counts are not directly comparable to generative-model token usage. The cost replay prices each model separately and leaves electricity/hardware costs unknown.

## Frozen staged execution

`run_staged.py` records a fresh 100-row pilot and then resumes into the 500 and 10,000 subsets. It checks completed counts and stops if more than half of the independent verification sample disagrees on any of topic, intent or severity. This is an operational stop condition, not an accuracy target or a human benchmark. `--through full` continues to the whole input only after those gates pass. Processing files and prompts are fingerprinted; changing them during execution stops the next stage.

The selected v6 classifier uses a pinned base-model revision, short hypotheses, and a conservative English lexical evidence guard. The guard can reject an unsupported specific topic but does not supply sentiment or intent labels. Explicit premium restrictions take precedence over controls when model support for billing is high. Nonmatching terminology and other languages can be missed; this is a documented precision/recall tradeoff. Ineligible topic hypotheses are not evaluated, reducing computation. Every input still goes through the model.

Selected execution evidence is under `runs/selected-v6/`. Earlier folders named `nli-final` and `nli-v5-final` are historical experiment names, not claims of final submission status. The v5 experiment was invalidated by a configuration change during its warm replay and is not the selected cost pilot.

`prepare_dashboard.py` imports saved aggregate metrics and at most three exact evidence reviews per issue into the dashboard seed. The deployed backend stores and serves those metrics and evidence in its database. It does not pretend that the small evidence subset contains all classified reviews. Full grading exports remain separate.

The public package excludes the 50 held-out review texts and provisional answer rows. Only aggregate provisional evaluation metrics are included. The displayed/saved original review excerpts come from the 500-row development subset. Synthetic test cases are separate.
