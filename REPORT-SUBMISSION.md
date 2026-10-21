# Spotify review analysis

This run classified 476,154 of 660,622 loaded reviews. It retained 13 quarantined records. The complete source contains 660,622 reviews from May 2022 through November 2023. This is a partial submission: 184,455 nonempty reviews remain unclassified and are excluded from all rankings. The completed records are not a random sample; the missing portion may change the conclusion.

Prioritize investigation of disruptive ads and playback-control friction within usability. Usability is the highest-scoring specific topic: 36,964 complaint/cancellation reviews and a severity sum of 87,427 (ISSUE-usability-priority_score). Treat this as a scoped discovery priority, not evidence that a particular fix will improve retention.

Billing is the next specific topic by score (30,590; ISSUE-billing-priority_score). The broader other category ranks first overall (187,684; ISSUE-other-priority_score), so inspect and subdivide that category before committing a quarter of engineering work. Access has higher mean severity but much lower frequency; it does not lead the baseline ranking.

## Results

| Rank | Issue | Complaints/cancellations | Mean severity | Priority score |
|---:|---|---:|---:|---:|
| 1 | ISSUE-other | 87,227 | 2.151673 | 187,684 |
| 2 | ISSUE-usability | 36,964 | 2.365193 | 87,427 |
| 3 | ISSUE-billing | 12,915 | 2.368564 | 30,590 |
| 4 | ISSUE-playback | 10,323 | 2.448319 | 25,274 |
| 5 | ISSUE-downloads | 4,549 | 2.568257 | 11,683 |
| 6 | ISSUE-access | 4,412 | 2.641659 | 11,655 |
| 7 | ISSUE-catalog | 4,141 | 2.449650 | 10,144 |
| 8 | ISSUE-support | 295 | 2.477966 | 731 |

Each priority score is the sum of severity across complaint and cancellation records. This is equivalent to count multiplied by the unrounded mean severity. Praise and feature requests do not enter this ranking. Ties are resolved by issue ID. All issue-level numbers are exported in `grading/claims.csv`.

## Evidence

Full partial-run evidence is supplied in the local course submission package. Public review texts are restricted to the 500-review development checkpoint in evidence/checkpoint500.

## Method and checks

The pipeline reads only review text for classification. Ratings and dates remain source metadata. A pinned local NLI model evaluates short label hypotheses. A conservative English evidence guard rejects specific topics with no matching feature terminology. Separate local generative roles verify original text, describe groups, and choose a recommendation from saved aggregates. Every request and model result is saved.

The independent verifier differed on at least one of topic, intent or severity for 6 of 10 sampled reviews. This is model disagreement, not a measured error rate. The 50 reference labels remain provisional; no human-reviewed accuracy claim is made.

The recorded 100-review pilot took 51.84 seconds including interruption and resume. Its warm replay took 7.50 seconds. API charges were $0. Electricity and hardware costs were not measured.

Exact duplicate texts reuse one saved result under the same configuration while preserving separate original IDs and direct provenance. Empty text and failed processing remain visible in the export. Saved progress is committed after each bounded request.

## Limits and next action

Scope: 476,154 completed records from 660,622 loaded source records. Historical, self-selected reviews with coarse topic-level groups do not measure revenue, confirmed churn or causal retention effects. Human-reviewed label evaluation is not complete.

Broad topics hide distinct root causes. English lexical guards and the English model can miss other languages, unusual wording, and indirect references. Sentiment scores are not calibrated probabilities. Cancellation statements are not confirmed churn, and review frequency does not measure revenue impact.

Before committing the next quarter of engineering effort, inspect the leading issue’s examples and validate the suspected failure with product telemetry. A useful next experiment is to define the exact affected workflow, measure its failure rate, ship a targeted fix, and compare that failure rate and retention against a holdout. The current data does not establish the effect of that fix.
