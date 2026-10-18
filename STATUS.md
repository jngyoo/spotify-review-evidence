# Current status

- Selected classifier: local DeBERTa base NLI v6, pinned model revision and frozen source. Verifier/group/memo: local Gemma 4 E2B.
- Full source: 660,622 rows ingested and checksum verified.
- Selected 100-row pilot: official deterministic checker passed; 100 completed, zero quarantined.
- Actual interrupted/resumed pilot: 51.84 seconds; warm replay: 7.50 seconds, no new calls. API charges: $0; electricity/hardware unmeasured.
- Selected 500-row checkpoint: 500 completed; independent disagreement on 21/50 samples. This is not a ground-truth error rate.
- 10,000/10,000 reviews classified. Downstream issue naming failed ID validation; saved classifications are intact. Recovery is in progress before full-source execution.
- Execution status: `runs/selected-v6/progress.json`. Evidence: `runs/selected-v6/pilot100/`, `runs/selected-v6/500/`.
- Live dashboard updated to the selected 500-row checkpoint and verified. The site remains owner-private.
- The user explicitly approved publishing the source and 500-review development evidence. Larger-run original texts are excluded from this public package.

Remaining work: larger-run checks, final dashboard publication, grader access, final report/package, and human-reviewed golden evaluation. Provisional labels are not a human-reviewed benchmark.
