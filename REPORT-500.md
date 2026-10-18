# Spotify review analysis

This run classified 500 of 500 loaded reviews. It retained 0 quarantined records. The complete source contains 660,622 reviews from May 2022 through November 2023.

Fix playback interruptions and failures. Prioritize ISSUE-playback based on higher severity.

Compare this with ISSUE-access before allocating the next quarter of product effort.

## Results

| Rank | Issue | Complaints/cancellations | Mean severity | Priority score |
|---:|---|---:|---:|---:|
| 1 | ISSUE-other | 97 | 2.216495 | 215 |
| 2 | ISSUE-usability | 46 | 2.347826 | 108 |
| 3 | ISSUE-billing | 39 | 2.307692 | 90 |
| 4 | ISSUE-playback | 19 | 2.578947 | 49 |
| 5 | ISSUE-catalog | 10 | 2.400000 | 24 |
| 6 | ISSUE-downloads | 7 | 2.285714 | 16 |
| 7 | ISSUE-access | 5 | 3.000000 | 15 |

Each priority score is the sum of severity across complaint and cancellation records. This is equivalent to count multiplied by the unrounded mean severity. Praise and feature requests do not enter this ranking. Ties are resolved by issue ID. All issue-level numbers are exported in `grading/claims.csv`.

## Evidence

**ISSUE-playback** — claim `ISSUE-playback-priority_score`, review `1cdc5bb2-8e8d-4267-8853-6c1dd4c7ef13`

> So this app has become unusable on ipads. It stops randomly. Sometimes 10 minutes, sometimes 2 hours. I've tried all the"fixes". It's an app issue. Cmon, get it fixed. I'll be canceling my account if it's not corrected soon.

**ISSUE-access** — claim `ISSUE-access-priority_score`, review `f6f9c680-0970-443f-b422-b1a6ad85e7ce`

> @spotifyindia worst one ever my premium account got logged out automatically which was linked with my phone number now when I try to log in using my phone number it shows check your number and try again even though my number is correct. What the hell...

## Method and checks

The pipeline reads only review text for classification. Ratings and dates remain source metadata. A pinned local NLI model evaluates short label hypotheses. A conservative English evidence guard rejects specific topics with no matching feature terminology. Separate local generative roles verify original text, describe groups, and choose a recommendation from saved aggregates. Every request and model result is saved.

The independent verifier differed on at least one of topic, intent or severity for 21 of 50 sampled reviews. This is model disagreement, not a measured error rate. The 50 reference labels remain provisional; no human-reviewed accuracy claim is made.

The recorded 100-review pilot took 51.84 seconds including interruption and resume. Its warm replay took 7.50 seconds. API charges were $0. Electricity and hardware costs were not measured.

Exact duplicate texts reuse one saved result under the same configuration while preserving separate original IDs and direct provenance. Empty text and failed processing remain visible in the export. Saved progress is committed after each bounded request.

## Limits and next action

Scope: 500 completed records from 500 loaded source records. Historical, self-selected reviews with coarse topic-level groups do not measure revenue, confirmed churn or causal retention effects. Human-reviewed label evaluation is not complete.

Broad topics hide distinct root causes. English lexical guards and the English model can miss other languages, unusual wording, and indirect references. Sentiment scores are not calibrated probabilities. Cancellation statements are not confirmed churn, and review frequency does not measure revenue impact.

Before committing the next quarter of engineering effort, inspect the leading issue’s examples and validate the suspected failure with product telemetry. A useful next experiment is to define the exact affected workflow, measure its failure rate, ship a targeted fix, and compare that failure rate and retention against a holdout. The current data does not establish the effect of that fix.
