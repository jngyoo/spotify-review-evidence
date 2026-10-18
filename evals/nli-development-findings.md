# Development findings before scaling

The xsmall NLI v3 classifier completed all 500 development records, but manual inspection of model outputs identified unsupported topics and severity. This inspection did not use the held-out golden labels.

Examples from the fixed development samples:

- `94c9f2f9-36fa-4c11-936e-660514fe7a35`: criticism of the new home screen was labeled downloads/severity 4. The text supports usability and does not establish a blocked core task.
- `23de7958-ccb0-4356-bc12-094935e6857d`: general praise was labeled downloads; no download feature is mentioned.
- `4ab2089a-ffa8-49e7-a8a3-aeb583a96796`: Wi-Fi playback/connectivity and audio-quality criticism was labeled downloads, unsupported by the text.

The deterministic 100-record audit passed, which validates export consistency, not semantic accuracy. We therefore did not scale this configuration to 10,000 or the full corpus. A larger free local NLI model is being compared on development inputs before choosing a final configuration.

The 500-run verifier separately failed ID-set validation twice with 25 reviews per request. These real failed calls remain in its logs. Verification requests are now capped at five reviews, independent of enrichment batch size. Previously committed enrichment remains reusable under the same configuration.
