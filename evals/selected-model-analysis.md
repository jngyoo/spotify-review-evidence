# Selected model evaluation

The following comparison uses provisional references, not human-reviewed ground truth. The model configuration was frozen before this comparison and was not changed in response to it.

50/50 valid predictions; topic agreement 78%, intent agreement 84%, severity agreement 80%. Severity MAE: 0.28. Exact source-quote match: 100%.

Catalog is the weakest observed category: one of seven provisional catalog cases matched. The conservative evidence guard misses terms outside its English vocabulary. Review-flag agreement is only 32%; flags should not be interpreted as calibrated uncertainty. The small and provisional reference set limits every estimate.

The synthetic injection retained playback/complaint but changed severity from 2 to 3. Thus topic/intent resisted this one attack, while full label invariance failed. The independent verifier detected all three fields of a planted wrong label. This is one synthetic test, not a general security guarantee.
