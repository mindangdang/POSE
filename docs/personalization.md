# Personalization

## Preference records

Preferences contain an attribute, value, polarity, weight, confidence, scope (`session`, `domain`, `global`), source (`explicit`, `inferred`), timestamps, and optional embedding/evidence IDs. Users can list, create, patch, and delete long-term preferences through `/api/v2/preferences`. Session preferences are held only in the active search process.

The search retrieves up to five query-relevant preferences. Selection considers lexical overlap with a small synonym map, scope compatibility, weight, confidence, and recency decay for inferred preferences. BGE-M3 query-to-preference similarity is used when the optional model server responds. Unrelated preferences are not sent to the intent LLM.

## Query-conditioned representation

`QueryEncoder` combines a normalized original query vector with a weighted preference vector. The temperature-softmax weights preferences by query relevance. Current explicit criteria remain ahead of preference memory, inferred preferences remain soft, and a conflicting explicit query is allowed to override memory. When the BGE server is unavailable, a stable hashing vector keeps the path deterministic. This is a training-free representation, not a learned two-tower model.

## Ranking and opt-out

Personalization uses both query-conditioned dense retrieval and a soft utility feature. Disabling personalization removes preferences before preference retrieval, does not build a personalized vector, and rebalances RRF weights. The same candidate/query inputs therefore use a profile-independent ranking path.

Ranking scores are bounded utility scores, not calibrated relevance probabilities. Hard violations are excluded. Unknown hard criteria are not marked verified. Reasons shown in the UI are generated from actual matching and evidence features.

## Feedback rules

Feedback is tied to an owned search and a result actually exposed in that search. The API enforces client idempotency keys per authenticated user. Ordinary click, like, dislike, and dismiss events are recorded but do not by themselves infer an attribute preference. `PREFERENCE_UPDATE` requires an explicit typed preference; session scope remains local to that search and related-search scope persists the explicit preference. Preference weight updates are not yet automatically learned from criterion-correction events.

The result impression table records displayed results, but no-click is never used as a negative label. Document vectors are cached by model, version, and content hash. The database has an optional 1024-dimensional preference embedding column, but the application does not yet persist or reuse those preference vectors across requests.
